"""Real descriptor handoff; privileged cases require the project's isolated VM namespace."""
import array
from contextlib import ExitStack
from dataclasses import replace
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import dns_activation as activation  # noqa: E402
import dns_privileged as privileged  # noqa: E402


def fd_count():
    return len(os.listdir('/proc/self/fd' if sys.platform == 'linux' else '/dev/fd'))


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.udp = self.stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
        self.udp.bind(('127.0.0.1', 0))
        self.tcp = self.stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        self.tcp.bind(self.udp.getsockname())
        self.expected = activation.Expected('127.0.0.1', os.getgid(), b'n' * 32,
                                            self.udp.getsockname()[1], os.getuid())
        self.frame = activation.FRAME.pack(b'DNS1', os.getuid(), os.getgid(), 0, b'n' * 32)

    def handoff(self, payload=None, descriptors=None, fragment=False, hold=False):
        sender, receiver = socket.socketpair()
        self.stack.enter_context(sender)
        self.stack.enter_context(receiver)
        values = [self.udp.fileno(), self.tcp.fileno()] if descriptors is None else descriptors
        payload = self.frame if payload is None else payload
        errors = []

        def transmit():
            try:
                rights = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', values))]
                sender.sendmsg([payload[:1] if fragment else payload], rights)
                if fragment:
                    sender.sendall(payload[1:])
                if not hold:
                    sender.shutdown(socket.SHUT_WR)
            except BaseException as error:
                errors.append(error)

        worker = threading.Thread(target=transmit)
        worker.start()
        try:
            return activation.receive_sockets(receiver, self.expected)
        finally:
            worker.join(2)
            self.assertFalse(worker.is_alive(), 'Sender survived cleanup')
            if errors:
                raise errors[0]

    def refuse(self, **kwargs):
        # Create/close the transport before comparing descriptor counts.
        before = fd_count()
        old = self.stack
        self.stack = ExitStack()
        try:
            with self.assertRaises((ValueError, TimeoutError)):
                self.handoff(**kwargs)
        finally:
            self.stack.close()
            self.stack = old
        self.assertEqual(fd_count(), before, 'Rejected descriptors leaked')

    def test_valid_fragmented_transfer_carries_udp_tcp_data(self):
        udp, tcp = self.handoff(fragment=True)
        self.stack.enter_context(udp)
        self.stack.enter_context(tcp)
        self.assertFalse(udp.get_inheritable())
        self.assertFalse(tcp.get_inheritable())
        udp.settimeout(1)
        tcp.settimeout(1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(b'udp-data', udp.getsockname())
            self.assertEqual(udp.recvfrom(64)[0], b'udp-data')
        tcp.listen(1)
        with socket.create_connection(tcp.getsockname(), timeout=1) as client:
            with tcp.accept()[0] as connection:
                client.sendall(b'tcp-data')
                self.assertEqual(connection.recv(64), b'tcp-data')
                client.shutdown(socket.SHUT_WR)
                self.assertEqual(connection.recv(64), b'')

    def test_peer_identity_matches_real_unix_connection(self):
        first, second = socket.socketpair()
        with first, second:
            self.assertEqual(activation.peer_identity(first), (os.getuid(), os.getgid()))

    def test_wrong_peer_refused(self):
        self.expected = replace(self.expected, uid=os.getuid() + 1)
        self.frame = activation.FRAME.pack(b'DNS1', self.expected.uid, self.expected.gid, 0, b'n' * 32)
        self.refuse()

    def test_wrong_nonce_refused(self):
        self.expected = replace(self.expected, nonce=b'x' * 32)
        self.refuse()

    def test_frame_identity_and_groups_refused(self):
        for uid, gid, groups, magic in [(os.getuid() + 1, os.getgid(), 0, b'DNS1'),
                                        (os.getuid(), os.getgid() + 1, 0, b'DNS1'),
                                        (os.getuid(), os.getgid(), 1, b'DNS1'),
                                        (os.getuid(), os.getgid(), 0, b'EVIL')]:
            with self.subTest(uid=uid, gid=gid, groups=groups, magic=magic):
                self.refuse(payload=activation.FRAME.pack(magic, uid, gid, groups, b'n' * 32))

    def test_short_or_trailing_frame_refused(self):
        for payload in (self.frame[:-1], self.frame + b'x', self.frame + b'xx'):
            with self.subTest(size=len(payload)):
                self.refuse(payload=payload)

    def test_descriptor_count_and_truncation_refused(self):
        for count in (0, 1, 3, 17, 65):
            with self.subTest(count=count):
                self.refuse(descriptors=[self.udp.fileno()] * count)

    def test_extra_descriptor_refused(self):
        self.refuse(descriptors=[self.udp.fileno(), self.tcp.fileno(), self.udp.fileno()])

    def test_reversed_types_refused(self):
        self.refuse(descriptors=[self.tcp.fileno(), self.udp.fileno()])

    def test_wrong_first_type_refused(self):
        self.refuse(descriptors=[self.tcp.fileno(), self.tcp.fileno()])

    def test_wrong_address_and_port_refused(self):
        original = self.expected
        for expected in (replace(original, bind='127.0.0.2'),
                         replace(original, port=original.port + 1)):
            self.expected = expected
            self.refuse()

    def test_rejected_adopted_fds_close_even_with_references_held(self):
        original, observed = socket.socket, []

        def track(*args, **kwargs):
            value = original(*args, **kwargs)
            if 'fileno' in kwargs:
                observed.append(value)
            return value

        self.expected = replace(self.expected, port=self.expected.port + 1)
        with patch.object(activation.socket, 'socket', side_effect=track):
            self.refuse()
        self.assertTrue(observed, 'No real adopted descriptors observed')
        self.assertTrue(all(value.fileno() == -1 for value in observed))

    def test_ipv6_refused(self):
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as udp:
            udp.bind(('::1', 0))
            self.refuse(descriptors=[udp.fileno(), self.tcp.fileno()])

    def test_listening_tcp_refused(self):
        self.tcp.listen(1)
        self.refuse()

    def test_connected_udp_refused(self):
        self.udp.connect(('127.0.0.1', 9))
        self.refuse()

    def test_reuse_options_refused(self):
        for option in (socket.SO_REUSEADDR, socket.SO_REUSEPORT):
            with self.subTest(option=option):
                self.udp.setsockopt(socket.SOL_SOCKET, option, 1)
                self.refuse()
                self.udp.setsockopt(socket.SOL_SOCKET, option, 0)

    def test_open_sender_times_out_and_closes_received_fds(self):
        start = time.monotonic()
        self.refuse(hold=True)
        self.assertLess(time.monotonic() - start, 4)

    def test_bootstrap_bind_scope(self):
        for value in ('0.0.0.0', '127.0.0.1', '8.8.8.8', '172.16.42.2', '010.1.2.3', '::1'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    privileged.private_bind(value)
        for value in ('10.1.2.3', '172.20.1.2', '192.168.1.2'):
            self.assertEqual(privileged.private_bind(value), value)

    def test_private_channel_refuses_permissions_symlinks_and_owner(self):
        with tempfile.TemporaryDirectory(prefix='idns-test-') as folder:
            path = Path(folder).resolve() / 's'
            options = SimpleNamespace(channel=str(path), uid=os.getuid())
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(path))
                os.chmod(path, 0o600)
                privileged.private_channel(options)
                os.chmod(path, 0o666)
                with self.assertRaises(ValueError):
                    privileged.private_channel(options)
                os.chmod(path, 0o600)
                os.chmod(folder, 0o755)
                with self.assertRaises(ValueError):
                    privileged.private_channel(options)
                os.chmod(folder, 0o700)
                with self.assertRaises(ValueError):
                    privileged.private_channel(replace_namespace(options, uid=os.getuid() + 1))
                link = path.with_name('link')
                link.symlink_to(path)
                with self.assertRaises(ValueError):
                    privileged.private_channel(replace_namespace(options, channel=str(link)))

    def test_root_controller_refused_before_launch(self):
        with patch.object(activation.os, 'getuid', return_value=0):
            with patch.object(activation.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(ValueError, 'ordinary non-root'):
                    activation.acquire('10.1.2.3')
                launch.assert_not_called()

    def test_nonce_exact_length_and_eof(self):
        code = ('import sys; sys.path.insert(0, sys.argv[1]); '
                'import dns_privileged; print(len(dns_privileged.read_nonce()))')
        for value in (b'', b'n' * 31, b'n' * 32, b'n' * 33):
            result = subprocess.run([sys.executable, '-I', '-c', code,
                                     str(ROOT / 'scripts/host')], input=value,
                                    capture_output=True, timeout=4)
            self.assertEqual(result.returncode == 0, len(value) == 32)
            if len(value) == 32:
                self.assertEqual(result.stdout, b'32\n')


class ActivationBootstrapTests(unittest.TestCase):
    """Run explicitly as ubuntu inside a root-created private network namespace."""
    def setUp(self):
        self.assertEqual(sys.platform, 'linux', 'Privileged fixture is Linux VM only')
        self.bind = os.environ['IPHONE_ACTIVATION_TEST_BIND']
        self.assertNotEqual(os.geteuid(), 0)
        initial = subprocess.check_output(['/usr/bin/sudo', '-n', '--', '/usr/bin/readlink',
                                           '/proc/1/ns/net'], timeout=4).decode().strip()
        self.assertNotEqual(os.readlink('/proc/self/ns/net'), initial,
                            'Private network namespace required')
        self.assertEqual(Path('/proc/sys/net/ipv4/ip_unprivileged_port_start').read_text().strip(), '1024')

    def assert_free(self):
        with ExitStack() as stack:
            for kind in (socket.SOCK_DGRAM, socket.SOCK_STREAM):
                sock = stack.enter_context(socket.socket(socket.AF_INET, kind))
                # A free privileged port still refuses the ordinary controller.
                with self.assertRaises(PermissionError):
                    sock.bind((self.bind, 53))
        code = ('import socket,sys; a=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); '
                'b=socket.socket(); a.bind((sys.argv[1],53)); b.bind((sys.argv[1],53))')
        result = subprocess.run(['/usr/bin/sudo', '-n', '--', '/usr/bin/python3', '-I', '-S',
                                 '-c', code, self.bind], capture_output=True, timeout=4)
        self.assertEqual(result.returncode, 0, 'Privileged sockets survived cleanup')

    def test_actual_root_bind_drop_handoff_data_and_cleanup(self):
        before = fd_count()
        temp_before = set(Path(tempfile.gettempdir()).glob('idns-*'))
        with ExitStack() as stack:
            try:
                udp, tcp = activation.acquire(self.bind)
            except (ValueError, OSError) as error:
                self.fail('Actual bootstrap handshake failed: ' + str(error))
            stack.enter_context(udp)
            stack.enter_context(tcp)
            self.assertEqual(udp.getsockname(), (self.bind, 53))
            self.assertEqual(tcp.getsockname(), (self.bind, 53))
            self.assertFalse(udp.get_inheritable())
            self.assertFalse(tcp.get_inheritable())
            udp.settimeout(1)
            tcp.settimeout(1)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.sendto(b'privileged-udp', (self.bind, 53))
                self.assertEqual(udp.recvfrom(64)[0], b'privileged-udp')
            tcp.listen(1)
            with socket.create_connection((self.bind, 53), timeout=1) as client:
                with tcp.accept()[0] as connection:
                    client.sendall(b'privileged-tcp')
                    self.assertEqual(connection.recv(64), b'privileged-tcp')
                    client.shutdown(socket.SHUT_WR)
                    self.assertEqual(connection.recv(64), b'')
        self.assertEqual(fd_count(), before)
        self.assertEqual(set(Path(tempfile.gettempdir()).glob('idns-*')), temp_before)
        self.assert_free()

    def test_bootstrap_refuses_wrong_original_identity(self):
        with tempfile.TemporaryDirectory(prefix='idns-test-') as folder:
            path = str(Path(folder).resolve() / 's')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as channel:
                channel.bind(path)
                os.chmod(path, 0o600)
                helper = ROOT / 'scripts/host/dns_privileged.py'
                command = ['/usr/bin/sudo', '-n', '--', '/usr/bin/python3', '-I', '-S',
                           str(helper), '--bind', self.bind, '--channel', path,
                           '--uid', str(os.getuid() + 1), '--gid', str(os.getgid())]
                result = subprocess.run(command, input=b'n' * 32,
                                        capture_output=True, timeout=4)
                self.assertEqual(result.returncode, 1)
                self.assertIn(b'original sudo identity', result.stderr)
        self.assert_free()

    def test_tcp_conflict_closes_first_udp_and_child(self):
        code = ('import socket,sys; s=socket.socket(); s.bind((sys.argv[1],53)); '
                'print("READY",flush=True); sys.stdin.buffer.read()')
        process = subprocess.Popen(['/usr/bin/sudo', '-n', '--', '/usr/bin/python3', '-I', '-S',
                                    '-c', code, self.bind], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertEqual(process.stdout.readline(), b'READY\n')
            start, before = time.monotonic(), fd_count()
            with self.assertRaises(ValueError):
                activation.acquire(self.bind)
            self.assertLess(time.monotonic() - start, 3)
            self.assertEqual(fd_count(), before)
        finally:
            process.communicate(input=b'', timeout=4)
        self.assertEqual(process.returncode, 0)
        self.assert_free()


def replace_namespace(options, **changes):
    return SimpleNamespace(**(vars(options) | changes))


def load_tests(loader, _tests, _pattern):
    # Discovery never launches sudo; the VM class must be explicitly selected.
    return loader.loadTestsFromTestCase(ActivationTests)


if __name__ == '__main__':
    unittest.main(defaultTest='ActivationTests')
