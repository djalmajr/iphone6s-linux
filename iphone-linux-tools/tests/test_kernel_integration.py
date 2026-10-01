"""Real filesystem/profile contracts with synthetic nonbootable kernel inputs."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from test_device_profile import entry

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get('KERNEL_INTEGRATION_SCRIPT', ROOT / 'scripts/build/integrate-source-kernel.py'))
OLD_LOAD = b'insmod /lib/modules/usb_f_ncm.ko || echo "usb_f_ncm module load failed"\n'


def archive_chunks(raw):
    result, offset = {}, 0
    while True:
        start = offset
        fields = [int(raw[offset + 6 + i * 8:offset + 14 + i * 8], 16) for i in range(13)]
        size, namesize = fields[6], fields[11]
        name = raw[offset + 110:offset + 110 + namesize - 1].decode()
        offset = ((offset + 110 + namesize + 3) & ~3)
        offset = (offset + size + 3) & ~3
        if name == 'TRAILER!!!':
            return result
        result[name] = raw[start:offset]


class KernelIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='kernel-integration-synthetic-')
        self.root = Path(self.work.name).resolve()
        for name in ('scripts/build', 'scripts/host', 'runtime/source', 'runtime/kernel',
                     'docs/evidence', 'artifacts'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        for folder in (self.root / 'runtime', self.root / 'runtime/source', self.root / 'runtime/kernel'):
            folder.chmod(0o700)
        self.script = self.root / 'scripts/build/integrate-source-kernel.py'
        shutil.copyfile(SCRIPT, self.script)
        for name in ('device_profile.py', 'profile_image.py'):
            shutil.copyfile(ROOT / 'scripts/host' / name, self.root / 'scripts/host' / name)
        self.source = self.root / 'runtime/source'
        self.kernel = self.root / 'runtime/kernel'
        self.output = self.root / 'runtime/candidate'
        for name in ('client', 'server'):
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '',
                            '-C', 'synthetic-integration', '-f', str(self.source / name)], check=True)
        server = (self.source / 'server.pub').read_text().split()[:2]
        host = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 64)
        host += b's' * 32 + base64.b64decode(server[1])[-32:]
        self.members = [
            {'name': 'root', 'mode': stat.S_IFDIR | 0o700},
            {'name': 'root/.ssh', 'mode': stat.S_IFDIR | 0o700},
            {'name': 'root/.ssh/authorized_keys', 'mode': stat.S_IFREG | 0o600,
             'body': (self.source / 'client.pub').read_bytes()},
            {'name': 'etc/dropbear/dropbear_ed25519_host_key', 'mode': stat.S_IFREG | 0o600, 'body': host},
            {'name': 'init', 'mode': stat.S_IFREG | 0o755,
             'body': b'#!/bin/sh\nip link set lo up\n' + OLD_LOAD + b'/usr/local/sbin/start-terminal\n'},
            {'name': 'lib/modules/usb_f_ncm.ko', 'mode': stat.S_IFREG | 0o644, 'body': b'OLD_MODULE_SENTINEL'},
            {'name': 'srv/data/keep', 'mode': stat.S_IFREG | 0o600, 'body': b'KEEP_BYTES_AND_METADATA'},
        ]
        self.profile = {'format': 1, 'payload': 'payload.bin', 'sha256': '',
                        'initramfs': 'initramfs.gz', 'initramfs_sha256': '', 'client_key': 'client',
                        'known_hosts': 'known_hosts', 'host_key_alias': 'synthetic-source'}
        self.save(self.source / 'known_hosts', ('synthetic-source ' + ' '.join(server) + '\n').encode())
        self.save_source()
        image = bytearray(64)
        image[56:60] = b'ARM\x64'
        struct.pack_into('<Q', image, 24, 4)
        self.save(self.kernel / 'Image', image)
        self.save(self.kernel / 'Image.gz', gzip.compress(image, mtime=0))
        self.save(self.kernel / 's8000-n71.dtb', b'SYNTHETIC_DTB_NOT_BOOTABLE')
        config = b'CONFIG_ARM64_16K_PAGES=y\nCONFIG_USB_F_NCM=y\nCONFIG_USB_CONFIGFS_NCM=y\nCONFIG_APPLE_WATCHDOG=y\n'
        self.save(self.kernel / 'config', config)
        self.save(self.kernel / 'config-embedded', config)
        self.record = {'status': 'compiled_verified', 'source': {'commit': 'synthetic'},
                       'build': {'exit_code': 0, 'outputs': {}, 'dtb_compatible': 'apple,n71',
                                 'kernel_release': 'synthetic-source'}}
        self.save_kernel_record()
        m1n1 = b'SYNTHETIC_M1N1_NONEXECUTABLE'
        self.save(self.root / 'artifacts/m1n1.bin', m1n1)
        (self.root / 'docs/evidence/m1n1-rebuild.json').write_text(json.dumps(
            {'shallow_clone': {'matches_original': True, 'sha256': hashlib.sha256(m1n1).hexdigest()}}))
        self.environment = dict(os.environ, IPHONE_LINUX_PROFILE=str(self.source / 'deployment.json'))

    def tearDown(self):
        self.work.cleanup()

    def save(self, path, data):
        path.write_bytes(data)
        path.chmod(0o600)

    def save_source(self):
        chunks = [entry(member) for member in self.members]
        # Regression: rebuilding the init header changed uppercase hex bytes in the real archive.
        raw = b''.join(chunk[:110].upper() + chunk[110:] for chunk in chunks)
        raw += entry({'name': 'TRAILER!!!'})
        compressed = gzip.compress(raw, mtime=0)
        payload = b'SYNTHETIC_PREFIX' + compressed
        self.save(self.source / 'initramfs.gz', compressed)
        self.save(self.source / 'payload.bin', payload)
        self.profile.update(sha256=hashlib.sha256(payload).hexdigest(),
                            initramfs_sha256=hashlib.sha256(compressed).hexdigest())
        self.save(self.source / 'deployment.json', json.dumps(self.profile).encode())

    def save_kernel_record(self):
        self.record['build']['outputs'] = {
            file.name: {'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'bytes': file.stat().st_size}
            for file in self.kernel.iterdir()}
        (self.root / 'docs/evidence/kernel-source-build.json').write_text(json.dumps(self.record))

    def run_cli(self):
        return subprocess.run([sys.executable, str(self.script), '--kernel-dir', str(self.kernel),
                               '--output-dir', str(self.output)], env=self.environment,
                              capture_output=True, text=True, timeout=15)

    def refuse(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn('KERNEL_INTEGRATION_VERIFIED', result.stdout)
        self.assertFalse((self.output / 'deployment.json').exists())

    def test_candidate_migrates_only_ncm_and_preserves_keys_and_inputs(self):
        before = {file: file.read_bytes() for file in self.source.iterdir()}
        original = archive_chunks(gzip.decompress((self.source / 'initramfs.gz').read_bytes()))
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('KERNEL_INTEGRATION_VERIFIED', result.stdout)
        raw = gzip.decompress((self.output / 'initramfs.gz').read_bytes())
        self.assertNotIn(b'OLD_MODULE_SENTINEL', raw)
        self.assertNotIn(OLD_LOAD, raw)
        self.assertIn(b'KEEP_BYTES_AND_METADATA', raw)
        chunks = archive_chunks(raw)
        self.assertEqual(set(chunks), set(original) - {'lib/modules/usb_f_ncm.ko'})
        for name in original.keys() - {'init', 'lib/modules/usb_f_ncm.ko'}:
            self.assertEqual(chunks[name], original[name])
        # Init preserves its header metadata except the necessary content size.
        self.assertEqual(chunks['init'][:54], original['init'][:54])
        self.assertEqual(chunks['init'][62:110], original['init'][62:110])
        for file, data in before.items():
            self.assertEqual(file.read_bytes(), data)
        for target, source in (('client_ed25519', 'client'), ('known_hosts', 'known_hosts')):
            self.assertEqual((self.output / target).read_bytes(), (self.source / source).read_bytes())
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o700)
        for file in self.output.iterdir():
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
        report = json.loads((self.output / 'provenance.json').read_text())
        self.assertEqual(report['initramfs_changed_paths'], ['init', 'lib/modules/usb_f_ncm.ko'])
        self.assertFalse(report['physical_boot_tested'])
        self.assertFalse((self.output / 'deployment.pending.json').exists())
        # A source already migrated updates without another init/module delta.
        self.environment['IPHONE_LINUX_PROFILE'] = str(self.output / 'deployment.json')
        self.output = self.root / 'runtime/next-version'
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.output / 'provenance.json').read_text())['initramfs_changed_paths'], [])

    def test_valid_gzip_with_changed_hash_is_rejected_before_output(self):
        data = bytearray((self.kernel / 'Image.gz').read_bytes())
        data[4] = 1  # Valid gzip with a changed timestamp still violates the trusted digest.
        self.save(self.kernel / 'Image.gz', data)
        self.refuse()
        self.assertFalse(self.output.exists())

    def test_private_module_mode_matches_actual_candidate(self):
        # Regression: the real validated archive stores its old module with mode 600.
        self.members[5]['mode'] = stat.S_IFREG | 0o600
        self.save_source()
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(b'OLD_MODULE_SENTINEL', gzip.decompress((self.output / 'initramfs.gz').read_bytes()))

    def test_four_kib_header_in_consistent_manifest_is_rejected(self):
        image = bytearray((self.kernel / 'Image').read_bytes())
        struct.pack_into('<Q', image, 24, 2)
        self.save(self.kernel / 'Image', image)
        self.save(self.kernel / 'Image.gz', gzip.compress(image, mtime=0))
        self.save_kernel_record()
        self.refuse()
        self.assertFalse(self.output.exists())

    def test_ncm_module_config_and_config_mismatch_are_rejected(self):
        config = (self.kernel / 'config').read_bytes()
        self.save(self.kernel / 'config', config.replace(b'CONFIG_USB_F_NCM=y', b'CONFIG_USB_F_NCM=m'))
        self.save_kernel_record()
        self.refuse()
        self.save(self.kernel / 'config-embedded', (self.kernel / 'config').read_bytes())
        self.save_kernel_record()
        self.refuse()

    def test_destination_and_source_identity_boundaries(self):
        self.output.mkdir(mode=0o700)
        sentinel = self.output / 'untouched'
        sentinel.write_bytes(b'UNRELATED_WORK')
        self.refuse()
        self.assertEqual(sentinel.read_bytes(), b'UNRELATED_WORK')
        self.output = self.root / 'outside-runtime'
        self.refuse()
        self.assertFalse(self.output.exists())
        self.output = self.root / 'runtime/new-private'
        (self.source / 'client').chmod(0o644)
        self.refuse()
        self.assertFalse(self.output.exists())

    def test_changed_m1n1_and_missing_old_module_are_rejected(self):
        m1n1 = self.root / 'artifacts/m1n1.bin'
        original = m1n1.read_bytes()
        self.save(m1n1, original + b'changed')
        self.refuse()
        self.save(m1n1, original)
        self.members = [member for member in self.members if member['name'] != 'lib/modules/usb_f_ncm.ko']
        self.save_source()
        self.refuse()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
