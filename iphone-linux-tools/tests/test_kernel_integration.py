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
        shutil.copyfile(ROOT / 'scripts/build/kernel_patchset.py',
                        self.root / 'scripts/build/kernel_patchset.py')
        shutil.copyfile(ROOT / 'scripts/build/kernel_bundle.py',
                        self.root / 'scripts/build/kernel_bundle.py')
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

    def run_cli(self, patchset=None):
        extra = ['--kernel-patchset', patchset] if patchset else []
        return subprocess.run([sys.executable, str(self.script), '--kernel-dir', str(self.kernel),
                               '--output-dir', str(self.output)] + extra, env=self.environment,
                              capture_output=True, text=True, timeout=15)

    def save_patch_record(self):
        self.patch_record = json.loads(json.dumps(self.record))
        self.patch_record['source'] = {
            'commit': '958481f87fee0949ff6a9a4af77f7eb6dac8a149',
            'patchset': 'n71-dart-tcr-v1',
            'patch_sha256': 'da321ed0e213a5ab4e3e27691f64d529b186474c556a00a2e7ee90957c785f74'}
        image = (self.kernel / 'Image').read_bytes() + b'PATCHED_IMAGE_SENTINEL'
        self.save(self.kernel / 'Image', image)
        self.save(self.kernel / 'Image.gz', gzip.compress(image, mtime=0))
        config = (self.kernel / 'config').read_bytes() + b'CONFIG_APPLE_DART=y\n'
        for name in ('config', 'config-embedded'):
            self.save(self.kernel / name, config)
        self.update_patch_record()

    def update_patch_record(self):
        self.patch_record['build']['outputs'] = {
            name: {'sha256': hashlib.sha256((self.kernel / name).read_bytes()).hexdigest(),
                   'bytes': (self.kernel / name).stat().st_size}
            for name in ('Image', 'Image.gz', 's8000-n71.dtb', 'config', 'config-embedded')}
        (self.root / 'docs/evidence/kernel-dart-build.json').write_text(json.dumps(self.patch_record))

    def test_patchset_is_explicit_and_preserves_baseline_and_identity(self):
        # Mutation captured: selecting baseline record despite explicit patchset or losing provenance.
        baseline = (self.root / 'docs/evidence/kernel-source-build.json').read_bytes()
        self.save_patch_record()
        refused = self.run_cli()
        self.assertEqual(refused.returncode, 1)
        self.assertFalse(self.output.exists())
        result = self.run_cli('n71-dart-tcr-v1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn((self.kernel / 'Image.gz').read_bytes(), (self.output / 'payload.bin').read_bytes())
        report = json.loads((self.output / 'provenance.json').read_text())
        self.assertEqual(report['kernel_patchset'], 'n71-dart-tcr-v1')
        self.assertFalse(report['physical_boot_tested'])
        self.assertEqual((self.output / 'client_ed25519').read_bytes(), (self.source / 'client').read_bytes())
        self.assertEqual((self.root / 'docs/evidence/kernel-source-build.json').read_bytes(), baseline)

    def test_patchset_rejects_wrong_base_and_patch_digest_before_output(self):
        # Mutation captured: dropping either immutable base or patch digest check.
        self.save_patch_record()
        original = dict(self.patch_record['source'])
        for field in ('commit', 'patch_sha256', 'patchset'):
            with self.subTest(field=field):
                self.patch_record['source'] = dict(original, **{field: 'changed'})
                self.update_patch_record()
                result = self.run_cli('n71-dart-tcr-v1')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse(self.output.exists())

    def test_patchset_requires_builtin_dart_with_consistent_manifest(self):
        # Mutation captured: dropping builtin DART guard accepts an image without the patched driver.
        self.save_patch_record()
        config = (self.kernel / 'config').read_bytes().replace(b'CONFIG_APPLE_DART=y', b'CONFIG_APPLE_DART=m')
        for name in ('config', 'config-embedded'):
            self.save(self.kernel / name, config)
        self.update_patch_record()
        result = self.run_cli('n71-dart-tcr-v1')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(self.output.exists())

    def save_bundle_record(self):
        public_source = json.loads((ROOT / 'docs/evidence/kernel-n71-bundle.json').read_text())['source']
        self.bundle_record = json.loads(json.dumps(self.record))
        self.bundle_record['source'] = {
            'commit': '958481f87fee0949ff6a9a4af77f7eb6dac8a149',
            'bundle': 'n71-dart-serdev-v1', 'required_localversion': '-iphone6s-dart-serdev1',
            'patches': public_source['patches'], 'files': public_source['files']}
        self.bundle_record['build'].update(kernel_release='7.2.0-iphone6s-dart-serdev1',
                                            full_image_linked=True, vmlinux_modpost_verified=True,
                                            serdev_stop_bits_export_verified=True)
        image = (self.kernel / 'Image').read_bytes() + b'BUNDLE_IMAGE_NONBOOTABLE_SENTINEL'
        self.save(self.kernel / 'Image', image)
        self.save(self.kernel / 'Image.gz', gzip.compress(image, mtime=0))
        config = (self.kernel / 'config').read_bytes() + (
            b'CONFIG_APPLE_DART=y\nCONFIG_SERIAL_DEV_BUS=y\nCONFIG_SERIAL_DEV_CTRL_TTYPORT=y\n'
            b'CONFIG_LOCALVERSION="-iphone6s-dart-serdev1"\n# CONFIG_LOCALVERSION_AUTO is not set\n')
        for name in ('config', 'config-embedded'):
            self.save(self.kernel / name, config)
        self.update_bundle_record()

    def update_bundle_record(self):
        self.bundle_record['build']['outputs'] = {
            name: {'sha256': hashlib.sha256((self.kernel / name).read_bytes()).hexdigest(),
                   'bytes': (self.kernel / name).stat().st_size}
            for name in ('Image', 'Image.gz', 's8000-n71.dtb', 'config', 'config-embedded')}
        (self.root / 'docs/evidence/kernel-n71-bundle-build.json').write_text(json.dumps(self.bundle_record))

    def test_bundle_requires_explicit_selection_preserving_profile_and_legacy_record(self):
        baseline_record = (self.root / 'docs/evidence/kernel-source-build.json').read_bytes()
        self.save_bundle_record()
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.output.exists())
        result = self.run_cli('n71-dart-serdev-v1')
        self.assertEqual(result.returncode, 0, result.stderr)
        provenance = json.loads((self.output / 'provenance.json').read_text())
        self.assertEqual(provenance['kernel_patchset'], 'n71-dart-serdev-v1')
        self.assertEqual(provenance['kernel_release'], '7.2.0-iphone6s-dart-serdev1')
        self.assertFalse(provenance['physical_boot_tested'])
        self.assertFalse(provenance['default_payload_changed'])
        self.assertEqual((self.output / 'client_ed25519').read_bytes(), (self.source / 'client').read_bytes())
        self.assertEqual((self.output / 'known_hosts').read_bytes(), (self.source / 'known_hosts').read_bytes())
        self.assertEqual((self.source / 'deployment.json').read_bytes(), json.dumps(self.profile).encode())
        self.assertEqual((self.root / 'docs/evidence/kernel-source-build.json').read_bytes(), baseline_record)
        self.assertNotIn('lib/modules/usb_f_ncm.ko', archive_chunks(
            gzip.decompress((self.output / 'initramfs.gz').read_bytes())))

    def test_bundle_rejects_inconsistent_source_full_link_and_release(self):
        self.save_bundle_record()
        original = json.loads(json.dumps(self.bundle_record))
        changes = [('source', key, 'altered') for key in ('commit', 'bundle', 'required_localversion')]
        changes += [('source', 'patches', {}), ('source', 'files', {})]
        changes += [('build', key, False) for key in (
            'full_image_linked', 'vmlinux_modpost_verified', 'serdev_stop_bits_export_verified')]
        changes += [('build', 'kernel_release', '7.2.0-iphone6s-source')]
        for section, key, value in changes:
            with self.subTest(section=section, key=key):
                self.bundle_record = json.loads(json.dumps(original))
                self.bundle_record[section][key] = value
                self.update_bundle_record()
                result = self.run_cli('n71-dart-serdev-v1')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse(self.output.exists())

    def test_bundle_requires_distinct_embedded_config_and_builtin_serdev(self):
        self.save_bundle_record()
        original = (self.kernel / 'config').read_bytes()
        for before, after in (
                (b'-iphone6s-dart-serdev1', b'-iphone6s-source'),
                (b'# CONFIG_LOCALVERSION_AUTO is not set', b'CONFIG_LOCALVERSION_AUTO=y'),
                (b'CONFIG_SERIAL_DEV_BUS=y', b'CONFIG_SERIAL_DEV_BUS=m'),
                (b'CONFIG_SERIAL_DEV_CTRL_TTYPORT=y', b'CONFIG_SERIAL_DEV_CTRL_TTYPORT=m')):
            with self.subTest(before=before):
                config = original.replace(before, after)
                for name in ('config', 'config-embedded'):
                    self.save(self.kernel / name, config)
                self.update_bundle_record()
                result = self.run_cli('n71-dart-serdev-v1')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse(self.output.exists())

    def test_bundle_refuses_old_modules_before_creating_output(self):
        self.save_bundle_record()
        original = list(self.members)
        for name in ('lib/modules/n71-diagnostic.ko', 'run/n71-diagnostic.ko.gz',
                     'lib/modules/modules.dep', 'lib/modules/nested/driver.ko.zst'):
            with self.subTest(name=name):
                self.members = original + [{'name': name, 'mode': stat.S_IFREG | 0o600,
                                             'body': b'OLD_KERNEL_ABI_SENTINEL'}]
                self.save_source()
                result = self.run_cli('n71-dart-serdev-v1')
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertFalse(self.output.exists())

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
