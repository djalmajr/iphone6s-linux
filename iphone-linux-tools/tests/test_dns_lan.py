"""Wire boundaries and opt-in real DNS/SSH LAN proxy integration."""
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import dns_transport as wire  # noqa: E402

QUERY = bytes.fromhex('123401000001000000000000') + b'\x0aiphone-usb\x04home\x04arpa\x00\x00\x01\x00\x01'
ANSWER = QUERY[:2] + b'\x81\x80' + QUERY[4:]


@contextmanager
def upstream(reply):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        listener.settimeout(4)

        def respond():
            with listener.accept()[0] as connection:
                wire.receive_frame(connection)
                connection.sendall(reply)

        worker = threading.Thread(target=respond)
        worker.start()
        try:
            yield listener.getsockname()
        finally:
            worker.join(timeout=5)
            if worker.is_alive():
                raise AssertionError('Upstream fixture survived cleanup')


class DnsWireTests(unittest.TestCase):
    def test_real_upstream_replies_require_identity_size_and_complete_frame(self):
        # Mutations captured: accepting mismatched ID or an oversized reply forwards invalid data.
        cases = [struct.pack('!H', len(ANSWER)) + b'\x43\x21' + ANSWER[2:],
                 struct.pack('!H', len(QUERY)) + QUERY,
                 struct.pack('!H', wire.MAX_MESSAGE + 1) + ANSWER
                 + b'\x00' * (wire.MAX_MESSAGE + 1 - len(ANSWER)),
                 struct.pack('!H', len(ANSWER)) + ANSWER[:5]]
        for reply in cases:
            with upstream(reply) as endpoint:
                with self.assertRaises((ValueError, EOFError)):
                    wire.exchange(QUERY, endpoint)
        with upstream(struct.pack('!H', len(ANSWER)) + ANSWER) as endpoint:
            self.assertEqual(wire.exchange(QUERY, endpoint), ANSWER)

    def test_cli_refuses_wildcard_public_clients_and_privileged_ports(self):
        # Mutation captured: dropping CLI scope checks permits public/global listeners.
        command = [sys.executable, str(ROOT / 'scripts/host/dns.py'), 'lan']
        cases = [[], ['--bind', '0.0.0.0', '--allow', '10.1.2.3'],
                 ['--bind', '127.0.0.1', '--allow', '8.8.8.8'],
                 ['--bind', '127.0.0.1', '--allow', '0.0.0.0'],
                 ['--bind', '127.0.0.1', '--allow', '172.16.42.2'],
                 ['--bind', '127.0.0.1', '--allow', '127.0.0.1', '--port', '53'],
                 ['--bind', '127.0.0.1', '--allow', '127.0.0.1', '--port', '1054']]
        for arguments in cases:
            result = subprocess.run(command + arguments, capture_output=True, text=True, timeout=4)
            self.assertEqual(result.returncode, 2, result.stderr)


def namespace_case():
    from test_lan import assert_closed, copy_binary, wait_socket
    with tempfile.TemporaryDirectory(prefix='iphone-dns-lan-test-') as folder:
        base = Path(folder)
        phone = base / 'phone'
        project = base / 'project'
        for name in ('bin', 'dev', 'proc', 'run', 'etc/dropbear', 'root/.ssh'):
            (phone / name).mkdir(parents=True, exist_ok=True)
        (project / 'scripts/host').mkdir(parents=True)
        (project / 'keys').mkdir()
        for source in (ROOT / 'scripts/host').glob('*.py'):
            shutil.copy(source, project / 'scripts/host' / source.name)
        shutil.copy('/usr/bin/busybox', phone / 'bin/busybox')
        copy_binary('/usr/sbin/dropbear', phone)
        with tarfile.open(os.environ['IPHONE_DNS_BUNDLE'], 'r:gz') as archive:
            archive.extractall(phone, filter='data')
        shutil.copy(ROOT / 'phone/dns/manage-dns.sh', phone / 'srv/data/dns/manage-dns.sh')
        (phone / 'etc/passwd').write_text('root:x:0:0:fixture:/root:/bin/sh\n')
        (phone / 'etc/group').write_text('root:x:0:\n')
        (phone / 'etc/shadow').write_text('root:*:20000:0:99999:7:::\n')
        (phone / 'etc/shells').write_text('/bin/sh\n')
        for name, minor in [('null', 3), ('urandom', 9)]:
            os.mknod(phone / 'dev' / name, 0o20666, os.makedev(1, minor))
        subprocess.run(['mount', '--bind', '/proc', str(phone / 'proc')], check=True)
        subprocess.run(['chroot', str(phone), '/bin/busybox', '--install', '-s', '/bin'], check=True)
        subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
        for address in ('172.16.42.1', '10.240.0.1', '10.240.0.2', '10.240.0.3'):
            subprocess.run(['ip', 'addr', 'add', address + '/32', 'dev', 'lo'], check=True)
        key = project / 'keys/iphone_ed25519'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
        (phone / 'root/.ssh/authorized_keys').write_bytes(key.with_suffix('.pub').read_bytes())
        for name in ('root', 'root/.ssh'):
            (phone / name).chmod(0o700)
        (phone / 'root/.ssh/authorized_keys').chmod(0o600)
        hostkey = phone / 'etc/dropbear/key'
        subprocess.run(['dropbearkey', '-t', 'ed25519', '-f', str(hostkey)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        public = subprocess.check_output(['dropbearkey', '-y', '-f', str(hostkey)], text=True)
        line = next(value for value in public.splitlines() if value.startswith('ssh-ed25519 '))
        known = project / 'keys/known_hosts'
        known.write_text('172.16.42.1 ' + line + '\n')
        log = (base / 'ssh.log').open('w+')
        daemon = subprocess.Popen(['chroot', str(phone), '/usr/sbin/dropbear', '-F', '-E',
                                   '-s', '-p', '172.16.42.1:22', '-r', '/etc/dropbear/key'],
                                  stdout=log, stderr=log)
        processes = []
        dns_pid = None
        command = [sys.executable, str(project / 'scripts/host/dns.py'), 'lan',
                   '--bind', '10.240.0.1', '--allow', '10.240.0.2',
                   '--port', '11053', '--tunnel-port', '11054']

        def start():
            output = tempfile.TemporaryFile()
            process = subprocess.Popen(command, stdout=output, stderr=output)
            processes.append((process, output))
            return process, output

        def ready(process, output):
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                output.seek(0)
                content = output.read()
                if b'DNS_LAN_READY\n' in content:
                    return
                if process.poll() is not None:
                    raise AssertionError('Proxy failed before ready: ' + content.decode())
                time.sleep(0.05)
            raise AssertionError('Proxy readiness timed out')

        def rejected_start():
            process, output = start()
            deadline = time.monotonic() + 12
            while process.poll() is None and time.monotonic() < deadline:
                output.seek(0)
                if b'DNS_LAN_READY\n' in output.read():
                    raise AssertionError('Failed startup published a proxy')
                time.sleep(0.05)
            if process.poll() is None:
                raise AssertionError('Failed startup did not terminate')
            output.seek(0)
            if process.returncode == 0 or b'DNS_LAN_READY\n' in output.read():
                raise AssertionError('Failed startup published a proxy')

        def query(tcp=False, client='10.240.0.2', name='iphone-usb.home.arpa'):
            args = ['dig', '-b', client, '@10.240.0.1', '-p', '11053',
                    '+time=1', '+tries=1', '+noall', '+answer', '+comments', name]
            if tcp:
                args.append('+tcp')
            return subprocess.run(args, capture_output=True, text=True, timeout=4)

        try:
            wait_socket(('172.16.42.1', 22), daemon)
            result = subprocess.run(['chroot', str(phone), '/bin/sh',
                                     '/srv/data/dns/manage-dns.sh', 'start'],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            dns_pid = int((phone / 'run/iphone-dns/state').read_text().split()[0])
            process, output = start()
            ready(process, output)
            for protocol in ('udp', 'tcp'):
                bindings = [row.split()[1].split(':')[0] for row in
                            Path('/proc/net/' + protocol).read_text().splitlines()[1:]
                            if int(row.split()[1].split(':')[1], 16) == 11053]
                if bindings != ['0100F00A']:
                    raise AssertionError('Unexpected proxy kernel bind: ' + repr(bindings))
            for tcp in (False, True):
                positive = query(tcp)
                if positive.returncode or 'IN\tA\t172.16.42.1' not in positive.stdout:
                    raise AssertionError('Permitted DNS client failed: ' + positive.stdout)
                negative = query(tcp, name='external.example.com')
                if negative.returncode or 'status: NXDOMAIN' not in negative.stdout:
                    raise AssertionError('External name unexpectedly resolved')
                denied = query(tcp, client='10.240.0.3')
                if denied.returncode == 0:
                    raise AssertionError('Disallowed ' + ('TCP' if tcp else 'UDP') + ' client received DNS')
            holders = []
            try:
                for _ in range(8):
                    connection = socket.socket()
                    connection.bind(('10.240.0.2', 0))
                    connection.connect(('10.240.0.1', 11053))
                    connection.sendall(b'\x00\x30\x01')
                    holders.append(connection)
                time.sleep(0.2)
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                    client.bind(('10.240.0.2', 0))
                    client.settimeout(3.6)
                    client.sendto(QUERY, ('10.240.0.1', 11053))
                    try:
                        client.recvfrom(4096)
                    except socket.timeout:
                        pass
                    else:
                        raise AssertionError('Excess request queued instead of refused')
            finally:
                for connection in holders:
                    connection.close()
            children = Path(f'/proc/{process.pid}/task/{process.pid}/children').read_text().split()
            if len(children) != 1:
                raise AssertionError('Unexpected owned SSH child count')
            os.kill(int(children[0]), signal.SIGTERM)
            process.wait(timeout=8)
            if process.returncode == 0:
                raise AssertionError('Proxy hid lost tunnel')
            for address in [('10.240.0.1', 11053), ('127.0.0.1', 11054)]:
                assert_closed(address)
            for address in [('10.240.0.1', 11053), ('127.0.0.1', 11054)]:
                with socket.socket() as occupied:
                    occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    occupied.bind(address)
                    occupied.listen()
                    rejected_start()
                    with socket.create_connection(address, timeout=1):
                        pass
                assert_closed(('10.240.0.1', 11053))
                assert_closed(('127.0.0.1', 11054))
            original = known.read_text()
            known.write_text('')
            rejected_start()
            known.write_text(original)
            other = base / 'other_key'
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(other)], check=True)
            known.write_text('172.16.42.1 ' + other.with_suffix('.pub').read_text())
            rejected_start()
            known.write_text(original)
            assert_closed(('10.240.0.1', 11053))
            assert_closed(('127.0.0.1', 11054))
            print('DNS_LAN_REAL_UDP_TCP_ACL_BIND_CAPACITY_FAILURE_CLEANUP_OK')
        finally:
            for process, output in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=8)
                output.close()
            if dns_pid and Path(f'/proc/{dns_pid}').exists():
                os.kill(dns_pid, signal.SIGTERM)
            daemon.terminate()
            daemon.wait(timeout=3)
            log.close()
            subprocess.run(['umount', str(phone / 'proc')], check=True)


class DnsLanVmTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0 and
                         os.environ.get('IPHONE_DNS_VM_TESTS') == '1',
                         'requires explicit dedicated Linux VM/root opt-in')
    def test_real_dns_lan_allowlist_binding_tunnel_loss_and_failed_startup(self):
        # Mutations captured: removing either ACL, bind, capacity, trust or fail-on-forward.
        result = subprocess.run(['unshare', '--net', '--mount', '--', sys.executable,
                                 str(Path(__file__).resolve()), '--namespace'],
                                capture_output=True, text=True, timeout=55)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('DNS_LAN_REAL_UDP_TCP_ACL_BIND_CAPACITY_FAILURE_CLEANUP_OK', result.stdout)


if __name__ == '__main__':
    if sys.argv[1:] == ['--namespace']:
        namespace_case()
    else:
        unittest.main()
