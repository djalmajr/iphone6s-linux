"""Source boundaries and real isolated DNS file-update transactions."""
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import dev

HOSTS = b'172.16.42.1 iphone-usb.home.arpa\n'
MANAGER = b'''#!/bin/sh
set -eu
printf '%s\\n' "$1" >> /run/dns-events
case "$1" in
start) touch /run/dns-live ;;
stop) rm -f /run/dns-live ;;
status) test -f /run/dns-live ;;
*) exit 2 ;;
esac
'''


class Inputs(unittest.TestCase):
    def test_hosts_health_and_private_record(self):
        records = dev.validate_hosts(HOSTS + b'10.0.0.5 dev.home.arpa\n')
        self.assertEqual(records['dev.home.arpa'], '10.0.0.5')

    def test_reject_duplicate(self):
        with self.assertRaises(ValueError):
            dev.validate_hosts(HOSTS + HOSTS)

    def test_reject_missing_health_record(self):
        with self.assertRaises(ValueError):
            dev.validate_hosts(b'10.0.0.5 dev.home.arpa\n')

    def test_reject_public_address_and_external_name(self):
        for row in (b'8.8.8.8 dev.home.arpa\n', b'10.0.0.5 example.com\n'):
            with self.subTest(row=row), self.assertRaises(ValueError):
                dev.validate_hosts(HOSTS + row)

    def test_reject_large_hosts(self):
        with self.assertRaises(ValueError):
            dev.validate_hosts(HOSTS + b'#' * dev.MAX_BYTES)

    def test_source_links_modes_and_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            file = root / 'hosts'
            file.write_bytes(HOSTS)
            file.chmod(0o600)
            self.assertEqual(dev.read_regular(file), HOSTS)
            link = root / 'linked'
            link.symlink_to(file)
            with self.assertRaises(ValueError):
                dev.read_regular(link)
            link.unlink()
            os.link(file, link)
            with self.assertRaises(ValueError):
                dev.read_regular(file)
            link.unlink()
            file.chmod(0o666)
            with self.assertRaises(ValueError):
                dev.read_regular(file)
            file.chmod(0o600)
            file.write_bytes(b'x' * (dev.MAX_BYTES + 1))
            with self.assertRaises(ValueError):
                dev.read_regular(file)

    def test_parent_link_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / 'real').mkdir()
            (root / 'real/hosts').write_bytes(HOSTS)
            (root / 'alias').symlink_to(root / 'real', target_is_directory=True)
            with self.assertRaises(ValueError):
                dev.read_regular(root / 'alias/hosts')

    def test_bundle_fixed_regular_members_and_exact_bytes(self):
        with tarfile.open(fileobj=io.BytesIO(dev.bundle(MANAGER, HOSTS))) as archive:
            self.assertEqual(archive.getnames(), ['manager', 'hosts', 'update.sh'])
            self.assertTrue(all(x.isfile() and x.mode == 0o600 for x in archive.getmembers()))
            self.assertEqual(archive.extractfile('hosts').read(), HOSTS)

    def test_dns_answer_requires_exact_name_and_address(self):
        answer = 'status: NOERROR\ndev.home.arpa. 0 IN A 10.0.0.5\n'
        self.assertTrue(dev.answer_matches(answer, 'dev.home.arpa', '10.0.0.5'))
        self.assertFalse(dev.answer_matches(answer.replace('10.0.0.5', '10.0.0.50'), 'dev.home.arpa', '10.0.0.5'))
        self.assertFalse(dev.answer_matches(answer.replace('dev.home.arpa.', 'other.home.arpa.'), 'dev.home.arpa', '10.0.0.5'))
        self.assertFalse(dev.answer_matches(answer.replace('NOERROR', 'NXDOMAIN'), 'dev.home.arpa', '10.0.0.5'))

    def test_bundle_rejects_manager_format(self):
        with self.assertRaises(ValueError):
            dev.bundle(b'not a shell manager', HOSTS)


@unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0 and
                     os.environ.get('IPHONE_DEV_VM_TESTS') == '1',
                     'requires explicit isolated root VM fixture')
class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='iphone-dev-chroot-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('bin', 'run', 'dev', 'srv/data/dns/runtime/bin', 'srv/data/.dev-dns-' + 'a' * 32):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        shutil.copyfile('/usr/bin/busybox', self.root / 'bin/busybox')
        (self.root / 'bin/busybox').chmod(0o755)
        for name in ('sh', 'stat', 'sha256sum', 'cut', 'mkdir', 'rmdir', 'cp', 'mv', 'chmod', 'rm', 'touch'):
            (self.root / 'bin' / name).symlink_to('busybox')
        os.mknod(self.root / 'dev/null', 0o20666, os.makedev(1, 3))
        self.base = self.root / 'srv/data/dns'
        self.stage = self.root / ('srv/data/.dev-dns-' + 'a' * 32)
        (self.base / 'manage-dns.sh').write_bytes(MANAGER)
        (self.base / 'manage-dns.sh').chmod(0o755)
        (self.base / 'hosts').write_bytes(HOSTS)
        (self.base / 'hosts').chmod(0o644)
        (self.base / 'runtime/bin/dnsmasq').write_bytes(b'fixture identity only')
        self.new_manager = MANAGER + b'# updated\n'
        self.new_hosts = HOSTS + b'10.0.0.5 dev.home.arpa\n'
        (self.stage / 'manager').write_bytes(self.new_manager)
        (self.stage / 'hosts').write_bytes(self.new_hosts)
        shutil.copyfile(ROOT / 'phone/dev/update-dns.sh', self.root / 'update.sh')
        (self.root / 'run/dns-live').touch()

    def invoke(self, manager_hash=None, old_hash=None):
        command = [shutil.which('chroot'), str(self.root), '/bin/sh', '/update.sh',
                   '/srv/data/.dev-dns-' + 'a' * 32,
                   manager_hash or dev.digest(self.new_manager), dev.digest(self.new_hosts),
                   old_hash or dev.digest(MANAGER), dev.digest(HOSTS)]
        return subprocess.run(command, capture_output=True, text=True, timeout=10,
                              env={'PATH': '/bin'})

    def test_apply_and_lock_cleanup(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('DEV_APPLIED ' + 'a' * 32, result.stdout)
        self.assertEqual((self.base / 'hosts').read_bytes(), self.new_hosts)
        self.assertEqual((self.base / 'manage-dns.sh').read_bytes(), self.new_manager)
        self.assertTrue((self.root / 'run/dns-live').exists())
        self.assertFalse((self.root / 'run/iphone-dev-dns.lock').exists())
        self.assertEqual((self.base / 'hosts').stat().st_mode & 0o777, 0o644)

    def test_start_failure_restores_bytes_modes_and_running_state(self):
        self.new_manager = b'#!/bin/sh\n[ "$1" != start ] || exit 9\nexit 1\n'
        (self.stage / 'manager').write_bytes(self.new_manager)
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DEV_ROLLBACK_VERIFIED', result.stdout)
        self.assertEqual((self.base / 'hosts').read_bytes(), HOSTS)
        self.assertEqual((self.base / 'manage-dns.sh').read_bytes(), MANAGER)
        self.assertTrue((self.root / 'run/dns-live').exists())
        self.assertEqual((self.base / 'manage-dns.sh').stat().st_mode & 0o777, 0o755)
        self.assertFalse((self.root / 'run/iphone-dev-dns.lock').exists())

    def test_hash_divergence_changes_nothing(self):
        for argument in ({'manager_hash': '0' * 64}, {'old_hash': '0' * 64}):
            result = self.invoke(**argument)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((self.base / 'hosts').read_bytes(), HOSTS)
            self.assertEqual((self.base / 'manage-dns.sh').read_bytes(), MANAGER)
            self.assertTrue((self.root / 'run/dns-live').exists())
            self.assertFalse((self.root / 'run/dns-events').exists())

    def test_target_link_and_conflicting_lock_refused(self):
        outside = self.root / 'srv/data/outside'
        outside.write_bytes(HOSTS)
        (self.base / 'hosts').unlink()
        (self.base / 'hosts').symlink_to('/srv/data/outside')
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outside.read_bytes(), HOSTS)
        (self.base / 'hosts').unlink()
        (self.base / 'hosts').write_bytes(HOSTS)
        (self.root / 'run/iphone-dev-dns.lock').mkdir()
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertTrue((self.root / 'run/dns-live').exists())

    def test_temporary_link_preserved(self):
        outside = self.root / 'srv/data/outside'
        outside.write_bytes(b'preserve me')
        temporary = self.base / ('.dev-manager-' + 'a' * 32)
        temporary.symlink_to('/srv/data/outside')
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(outside.read_bytes(), b'preserve me')
        self.assertTrue(temporary.is_symlink())


if __name__ == '__main__':
    unittest.main()
