"""Opt-in DNS server proof using real dnsmasq/BusyBox in an isolated namespace."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'phone/dns/manage-dns.sh'


def namespace_case():
    # Regression: a bound, unprivileged service must answer both DNS transports.
    # Mutations: wildcard bind, root user, external upstream or PID identity bypass.
    bundle = Path(os.environ['IPHONE_DNS_BUNDLE'])
    with tempfile.TemporaryDirectory(prefix='iphone-dns-server-') as folder:
        base = Path(folder)
        root = base / 'phone'
        root.mkdir()
        for directory in ('bin', 'etc', 'dev', 'proc', 'run', 'lib'):
            (root / directory).mkdir()
        shutil.copy('/usr/bin/busybox', root / 'bin/busybox')
        for name in ('sh', 'awk', 'cat', 'chmod', 'false', 'grep', 'id', 'kill',
                     'mkdir', 'readlink', 'rm', 'sleep'):
            (root / 'bin' / name).symlink_to('busybox')
        shutil.copy('/lib/ld-linux-aarch64.so.1', root / 'lib/ld-linux-aarch64.so.1')
        (root / 'etc/passwd').write_text('root:x:0:0:fixture:/root:/bin/sh\n')
        (root / 'etc/group').write_text('root:x:0:\n')
        (root / 'etc/resolv.conf').write_text('nameserver 172.16.42.2\n')
        os.mknod(root / 'dev/null', 0o20666, os.makedev(1, 3))
        os.mknod(root / 'dev/urandom', 0o20666, os.makedev(1, 9))
        with tarfile.open(bundle, 'r:gz') as archive:
            for member in archive:
                if not (member.isfile() and member.name.startswith('srv/data/dns/runtime/')
                        and '..' not in Path(member.name).parts):
                    raise AssertionError('Unexpected DNS bundle member')
            archive.extractall(root, filter='data')
        launcher = root / 'srv/data/dns/manage-dns.sh'
        shutil.copy(SOURCE, launcher)
        launcher.chmod(0o755)
        subprocess.run(['mount', '--bind', '/proc', str(root / 'proc')], check=True)
        subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
        for address in ('172.16.42.1/32', '172.16.42.2/32'):
            subprocess.run(['ip', 'addr', 'add', address, 'dev', 'lo'], check=True)
        upstream = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        upstream.bind(('172.16.42.2', 53))
        upstream.settimeout(0.2)
        owned_pid = None
        foreign = None

        def manage(action):
            return subprocess.run(['chroot', str(root), '/bin/sh',
                                   '/srv/data/dns/manage-dns.sh', action],
                                  capture_output=True, text=True, timeout=9)

        def query(name, tcp=False, address='172.16.42.1'):
            command = ['dig', '+time=1', '+tries=1', '-p', '5353', '@' + address,
                       name, 'A', '+noall', '+answer', '+comments']
            if tcp:
                command.append('+tcp')
            return subprocess.run(command, capture_output=True, text=True, timeout=4)

        try:
            started = manage('start')
            if started.returncode:
                raise AssertionError(started.stdout + started.stderr)
            state = root / 'run/iphone-dns/state'
            initial_state = state.read_text()
            owned_pid = int(initial_state.split()[0])
            status = Path(f'/proc/{owned_pid}/status').read_text()
            uid = next(line for line in status.splitlines() if line.startswith('Uid:'))
            if uid.split()[1:] != ['65534'] * 4:
                raise AssertionError('DNS retained root privileges')
            repeated = manage('start')
            if repeated.returncode or state.read_text() != initial_state:
                raise AssertionError('Start was not idempotent')
            for protocol in ('tcp', 'udp'):
                bindings = []
                for line in Path('/proc/net/' + protocol).read_text().splitlines()[1:]:
                    address, port = line.split()[1].split(':')
                    if int(port, 16) == 5353:
                        bindings.append(socket.inet_ntoa(bytes.fromhex(address)[::-1]))
                if bindings != ['172.16.42.1']:
                    raise AssertionError('Unexpected kernel bind: ' + repr(bindings))
                for line in Path('/proc/net/' + protocol + '6').read_text().splitlines()[1:]:
                    if int(line.split()[1].split(':')[1], 16) == 5353:
                        raise AssertionError('Unexpected IPv6 DNS listener')
            for tcp in (False, True):
                positive = query('iphone-usb.home.arpa', tcp)
                if positive.returncode or 'IN\tA\t172.16.42.1' not in positive.stdout:
                    raise AssertionError(positive.stdout + positive.stderr)
                for name in ('missing.home.arpa', 'not-forwarded.example.com'):
                    negative = query(name, tcp)
                    if negative.returncode or 'status: NXDOMAIN' not in negative.stdout:
                        raise AssertionError('Unexpected negative DNS behavior: ' + negative.stdout)
                outside = query('iphone-usb.home.arpa', tcp, '127.0.0.1')
                if outside.returncode == 0:
                    raise AssertionError('DNS bound outside its USB address')
            try:
                upstream.recvfrom(4096)
            except socket.timeout:
                pass
            else:
                raise AssertionError('DNS forwarded an external query')

            state.write_text(str(owned_pid) + ' 0\n')
            stale = manage('stop')
            if stale.returncode == 0 or not Path(f'/proc/{owned_pid}').exists():
                raise AssertionError('Stale start-time record signaled process')
            state.write_text(initial_state)
            stopped = manage('stop')
            if stopped.returncode or state.exists():
                raise AssertionError(stopped.stdout + stopped.stderr)
            owned_pid = None
            if query('iphone-usb.home.arpa', True).returncode == 0:
                raise AssertionError('DNS listener survived stop')

            foreign = subprocess.Popen(['sleep', '30'])
            ticks = Path(f'/proc/{foreign.pid}/stat').read_text().split()[21]
            state.write_text(f'{foreign.pid} {ticks}\n')
            refused = manage('stop')
            if refused.returncode == 0 or foreign.poll() is not None:
                raise AssertionError('Foreign executable received signal')
            state.unlink()
            occupied = socket.socket()
            occupied.bind(('172.16.42.1', 5353))
            occupied.listen()
            try:
                failed = manage('start')
                if failed.returncode == 0 or state.exists():
                    raise AssertionError('Occupied port accepted partial startup')
                if query('iphone-usb.home.arpa').returncode == 0:
                    raise AssertionError('UDP listener survived failed startup')
                with socket.create_connection(('172.16.42.1', 5353), timeout=1):
                    pass
            finally:
                occupied.close()
            print('DNS_VM_UDP_TCP_LOCAL_PRIVILEGE_CLEANUP_OK')
        finally:
            if owned_pid and Path(f'/proc/{owned_pid}').exists():
                os.kill(owned_pid, 15)
            if foreign is not None:
                foreign.terminate()
                foreign.wait(timeout=3)
            upstream.close()
            subprocess.run(['umount', str(root / 'proc')], check=True)


class DnsServerVmTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0 and
                         os.environ.get('IPHONE_DNS_VM_TESTS') == '1',
                         'requires explicit dedicated Linux VM/root opt-in')
    def test_real_dns_transports_privilege_binding_and_cleanup(self):
        result = subprocess.run(['unshare', '--net', '--mount', '--', sys.executable,
                                 str(Path(__file__).resolve()), '--namespace'],
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('DNS_VM_UDP_TCP_LOCAL_PRIVILEGE_CLEANUP_OK', result.stdout)


if __name__ == '__main__':
    if sys.argv[1:] == ['--namespace']:
        namespace_case()
    else:
        unittest.main()
