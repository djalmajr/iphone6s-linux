"""Public input validation and opt-in real SSH install/snapshot recovery."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DnsInputTests(unittest.TestCase):
    def test_record_rejects_names_and_addresses_before_ssh(self):
        # Mutation captured: accepting foreign domains/public IPs expands the service contract.
        cases = [('outside.example.com', '10.1.2.3'), ('bad_name.home.arpa', '10.1.2.3'),
                 ('-bad.home.arpa', '10.1.2.3'), ('ok.home.arpa', '8.8.8.8'),
                 ('ok.home.arpa', '127.0.0.1'), ('ok.home.arpa', '::1')]
        for name, address in cases:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/host/dns.py'),
                                     'record', name, address], capture_output=True, text=True,
                                    timeout=4)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn('usage:', result.stderr)


def namespace_case():
    from test_lan import copy_binary, wait_socket
    with tempfile.TemporaryDirectory(prefix='iphone-dns-install-test-') as folder:
        base = Path(folder)
        phone = base / 'phone'
        project = base / 'project'
        for directory in ('bin', 'dev', 'etc/dropbear', 'root/.ssh', 'proc', 'run', 'var/run', 'srv/data'):
            (phone / directory).mkdir(parents=True, exist_ok=True)
        for directory in ('scripts/host', 'phone/dns', 'docs/evidence', 'keys', 'runtime'):
            (project / directory).mkdir(parents=True, exist_ok=True)
        for item in (ROOT / 'scripts/host').glob('*.py'):
            shutil.copy(item, project / 'scripts/host' / item.name)
        shutil.copy(ROOT / 'phone/dns/manage-dns.sh', project / 'phone/dns/manage-dns.sh')
        shutil.copy(ROOT / 'docs/evidence/dns-provenance.json', project / 'docs/evidence/dns-provenance.json')
        shutil.copy(os.environ['IPHONE_DNS_BUNDLE'], project / 'runtime/iphone6s-dns-runtime.tar.gz')
        shutil.copy('/usr/bin/busybox', phone / 'bin/busybox')
        copy_binary('/usr/sbin/dropbear', phone)
        copy_binary('/bin/bash', phone)
        (phone / 'etc/passwd').write_text('root:x:0:0:fixture:/root:/bin/sh\n')
        (phone / 'etc/group').write_text('root:x:0:\n')
        (phone / 'etc/shadow').write_text('root:*:20000:0:99999:7:::\n')
        (phone / 'etc/shells').write_text('/bin/sh\n')
        for name, minor in [('null', 3), ('urandom', 9)]:
            os.mknod(phone / 'dev' / name, 0o20666, os.makedev(1, minor))
        subprocess.run(['mount', '--bind', '/proc', str(phone / 'proc')], check=True)
        subprocess.run(['chroot', str(phone), '/bin/busybox', '--install', '-s', '/bin'], check=True)
        subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
        subprocess.run(['ip', 'addr', 'add', '172.16.42.1/32', 'dev', 'lo'], check=True)
        key = project / 'keys/iphone_ed25519'
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
        authorized = phone / 'root/.ssh/authorized_keys'
        authorized.write_bytes(key.with_suffix('.pub').read_bytes())
        authorized.chmod(0o600)
        (phone / 'root').chmod(0o700)
        (phone / 'root/.ssh').chmod(0o700)
        hostkey = phone / 'etc/dropbear/key'
        subprocess.run(['dropbearkey', '-t', 'ed25519', '-f', str(hostkey)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        public = subprocess.check_output(['dropbearkey', '-y', '-f', str(hostkey)], text=True)
        line = next(line for line in public.splitlines() if line.startswith('ssh-ed25519 '))
        (project / 'keys/known_hosts').write_text('172.16.42.1 ' + line + '\n')
        output = (base / 'ssh.log').open('w+')
        daemon = subprocess.Popen(['chroot', str(phone), '/usr/sbin/dropbear', '-F', '-E',
                                   '-s', '-p', '172.16.42.1:22', '-r', '/etc/dropbear/key'],
                                  stdout=output, stderr=output)
        dns_pid = None

        def command(script, *args):
            return subprocess.run([sys.executable, str(project / 'scripts/host' / script),
                                   *args], capture_output=True, text=True, timeout=20)

        def require_ok(result):
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            return result.stdout

        def answer():
            result = subprocess.run(['dig', '+tcp', '+time=1', '+tries=1', '-p', '5353',
                                     '@172.16.42.1', 'saved.home.arpa', '+short'],
                                    capture_output=True, text=True, timeout=4)
            if result.returncode or result.stdout.strip() != '10.8.9.10':
                raise AssertionError('Persisted record not served: ' + result.stdout)

        try:
            wait_socket(('172.16.42.1', 22), daemon)
            bundle_path = project / 'runtime/iphone6s-dns-runtime.tar.gz'
            original_bundle = bundle_path.read_bytes()
            changed = bytearray(original_bundle)
            # Gzip header time can change without corrupting size or tar contents.
            changed[4] ^= 1
            bundle_path.write_bytes(changed)
            rejected = command('dns.py', 'install')
            if (rejected.returncode == 0 or 'Hash/tamanho' not in rejected.stderr
                    or (phone / 'srv/data/dns').exists()):
                raise AssertionError('Bundle identity change accepted')
            bundle_path.write_bytes(original_bundle)
            preserved = phone / 'srv/data/dns'
            preserved.mkdir()
            (preserved / 'existing').write_text('preserve')
            refused = command('dns.py', 'install')
            if refused.returncode == 0 or (preserved / 'existing').read_text() != 'preserve':
                raise AssertionError('Install overwrote existing configuration')
            shutil.rmtree(preserved)
            (phone / 'srv/other').mkdir()
            (phone / 'srv/other/marker').write_text('untouched')
            (phone / 'srv/data').rmdir()
            (phone / 'srv/data').symlink_to('/srv/other')
            refused = command('dns.py', 'install')
            if refused.returncode == 0 or (phone / 'srv/other/marker').read_text() != 'untouched':
                raise AssertionError('Install followed symlink parent')
            (phone / 'srv/data').unlink()
            (phone / 'srv/data').mkdir()
            require_ok(command('dns.py', 'install'))
            if list((phone / 'run').glob('iphone-dns-install*')):
                raise AssertionError('Install lock/archive survived success')
            if list((phone / 'srv/data').glob('.iphone-dns-install-*')):
                raise AssertionError('Install staging survived success')
            require_ok(command('dns.py', 'record', 'saved.home.arpa', '10.8.9.10'))
            require_ok(command('dns.py', 'start'))
            dns_pid = int((phone / 'run/iphone-dns/state').read_text().split()[0])
            answer()
            require_ok(command('dns.py', 'stop'))
            dns_pid = None
            saved = require_ok(command('persist.py', 'backup'))
            snapshot = saved.strip().split('Snapshot: ', 1)[1]
            shutil.rmtree(phone / 'srv/data/dns')
            (phone / 'etc/passwd').write_text('root:x:0:0:fixture:/root:/bin/sh\n')
            (phone / 'etc/group').write_text('root:x:0:\n')
            require_ok(command('persist.py', 'restore', snapshot))
            if (phone / 'run/iphone-dns/state').exists():
                raise AssertionError('Restore recovered live process state')
            if authorized.read_bytes() != key.with_suffix('.pub').read_bytes():
                raise AssertionError('Restore altered SSH identity')
            require_ok(command('dns.py', 'start'))
            dns_pid = int((phone / 'run/iphone-dns/state').read_text().split()[0])
            answer()
            require_ok(command('dns.py', 'stop'))
            dns_pid = None
            print('DNS_SSH_INSTALL_SNAPSHOT_RESTORE_OK')
        finally:
            if dns_pid and Path(f'/proc/{dns_pid}').exists():
                os.kill(dns_pid, 15)
            daemon.terminate()
            daemon.wait(timeout=3)
            output.close()
            subprocess.run(['umount', str(phone / 'proc')], check=True)


class DnsInstallVmTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0 and
                         os.environ.get('IPHONE_DNS_VM_TESTS') == '1',
                         'requires explicit dedicated Linux VM/root opt-in')
    def test_real_ssh_install_preservation_and_snapshot_recovery(self):
        # Mutations captured: ignoring existing files, parent symlinks or bundle identity.
        result = subprocess.run(['unshare', '--net', '--mount', '--', sys.executable,
                                 str(Path(__file__).resolve()), '--namespace'],
                                capture_output=True, text=True, timeout=55)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('DNS_SSH_INSTALL_SNAPSHOT_RESTORE_OK', result.stdout)


if __name__ == '__main__':
    if sys.argv[1:] == ['--namespace']:
        namespace_case()
    else:
        unittest.main()
