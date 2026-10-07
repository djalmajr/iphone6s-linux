"""Bind qualified module/kernel records to real bounded gzip/payload files."""
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
SOURCE = ROOT / 'scripts/host/n71_iommu_build.py'
SPEC = importlib.util.spec_from_file_location('iommu_build_under_test', os.environ.get('N71_IOMMU_BUILD_SCRIPT', SOURCE))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
RELEASE = '7.2.0-iphone6s-dart-serdev-power2'


class IommuBuildTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name); self.folder = self.root / 'docs/evidence'; self.folder.mkdir(parents=True)
        self.proof = json.loads((ROOT / 'docs/evidence/n71-dma-topology-qualification.json').read_text())
        self.kernel = json.loads((ROOT / 'docs/evidence/kernel-n71-binding-build.json').read_text())
        self.image = bytes(range(256)) * 4
        self.compressed = gzip.compress(self.image, mtime=0)
        digest = hashlib.sha256(self.image).hexdigest()
        self.proof['kernel_build']['baseline_sha256']['arch/arm64/boot/Image'] = digest
        self.kernel['build']['outputs']['Image'] = {'bytes': len(self.image), 'sha256': digest}
        self.set_gzip(self.compressed)
        self.save()
        self.prefix = b'FIXTURE_PREFIX'.ljust(64, b'_')
        self.dtb = struct.pack('>II', 0xd00dfeed, 40) + b'FIXTURE_DTB'.ljust(32, b'_')
        self.tail = b'FIXTURE_INITRAMFS_SUFFIX'
        self.metadata = {'dtb_sha256': hashlib.sha256(self.dtb).hexdigest()}
        self.profile = {'payload': self.root / 'payload.bin', 'initramfs': self.root / 'initramfs.gz'}
        self.profile['initramfs'].write_bytes(self.tail)
        self.payload(self.dtb, self.compressed, self.tail)

    def set_gzip(self, raw):
        self.kernel['build']['outputs']['Image.gz'] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    def save(self):
        for name, value in (('n71-dma-topology-qualification.json', self.proof), ('kernel-n71-binding-build.json', self.kernel)):
            (self.folder / name).write_text(json.dumps(value))

    def payload(self, dtb, kernel, tail):
        self.profile['payload'].write_bytes(self.prefix + dtb + kernel + tail)

    def accepted(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ValueError, KeyError) as error:
            self.fail('Valid kernel binding refused: ' + str(error))

    def verify_payload(self):
        return BUILD.payload_image(self.root, self.profile, self.metadata, prefix_bytes=len(self.prefix), release=RELEASE)

    def test_exact_gzip_and_payload_select_the_same_qualified_image(self):
        # Mutations killed: return an invented Image ID, or skip payload/kernel boundary verification.
        expected = hashlib.sha256(self.image).hexdigest()
        self.assertEqual(self.accepted(BUILD.kernel_image, self.root, self.compressed, release=RELEASE), expected)
        self.assertEqual(self.accepted(self.verify_payload), expected)
        self.assertEqual(BUILD.qualified(self.root, release=RELEASE)['module_bytes'], 114008)
        self.payload(self.dtb, self.compressed, self.tail + b'extra')
        with self.assertRaises(ValueError): self.verify_payload()

    def test_compressed_and_uncompressed_identity_are_independently_checked(self):
        # Mutations killed: skip gzip digest/size or Image digest/size while the ABI remains identical.
        for key, value in (('sha256', 'f' * 64), ('bytes', len(self.compressed) + 1)):
            baseline = copy.deepcopy(self.kernel); self.kernel['build']['outputs']['Image.gz'][key] = value; self.save()
            with self.subTest(key=key), self.assertRaises(ValueError):
                BUILD.kernel_image(self.root, self.compressed, release=RELEASE)
            self.kernel = baseline
        wrong = gzip.compress(bytes(reversed(self.image)), mtime=0)
        self.set_gzip(wrong); self.save()
        with self.assertRaises(ValueError): BUILD.kernel_image(self.root, wrong, release=RELEASE)
        wrong = gzip.compress(self.image[:-1], mtime=0)
        digest = hashlib.sha256(self.image[:-1]).hexdigest()
        self.proof['kernel_build']['baseline_sha256']['arch/arm64/boot/Image'] = digest
        self.kernel['build']['outputs']['Image']['sha256'] = digest
        self.set_gzip(wrong); self.save()
        with self.assertRaises(ValueError): BUILD.kernel_image(self.root, wrong, release=RELEASE)

    def test_only_one_complete_gzip_stream_is_accepted(self):
        # Mutations killed: omit EOF/unused-data checks after a forged compressed descriptor matches.
        for raw in (self.compressed[:-4], self.compressed + gzip.compress(b'', mtime=0), b'not-gzip'.ljust(64, b'_')):
            self.set_gzip(raw); self.save()
            with self.subTest(raw_len=len(raw)), self.assertRaises(ValueError):
                BUILD.kernel_image(self.root, raw, release=RELEASE)

    def test_kernel_source_config_exports_and_release_must_match_module_proof(self):
        # Mutations killed: accept a foreign source/config/Image/exports or unqualified Image build.
        changes = [(('source', 'commit'), 'f' * 40), (('build', 'kernel_release'), 'foreign'),
                   (('build', 'full_image_linked'), False), (('build', 'vmlinux_modpost_verified'), False),
                   (('build', 'exit_code'), False), (('status',), 'not-built'),
                   (('build', 'vmlinux_symvers_sha256'), 'f' * 64),
                   (('build', 'outputs', 'config', 'sha256'), 'f' * 64),
                   (('build', 'outputs', 'Image', 'sha256'), 'f' * 64)]
        for keys, value in changes:
            baseline = copy.deepcopy(self.kernel); target = self.kernel
            for key in keys[:-1]: target = target[key]
            target[keys[-1]] = value; self.save()
            with self.subTest(keys=keys), self.assertRaises(ValueError): BUILD.image_record(self.root, release=RELEASE)
            self.kernel = baseline
        self.save()
        with self.assertRaises(ValueError): BUILD.qualified(self.root, release='same-prefix-wrong-ABI')

    def test_module_records_and_image_bounds_refuse_bool_or_invalid_values(self):
        # Mutations killed: omit exact record types, SHA shape or size boundaries.
        for key, value in (('module_bytes', True), ('module_bytes', 114008.0), ('module_bytes', 63), ('module_bytes', 256 * 1024 + 1),
                           ('module_sha256', 'A' * 64), ('vermagic', 'wrong')):
            baseline = copy.deepcopy(self.proof); self.proof['kernel_build'][key] = value; self.save()
            with self.subTest(key=key), self.assertRaises(ValueError): BUILD.qualified(self.root, release=RELEASE)
            self.proof = baseline
        self.save()
        for key, value in (('bytes', True), ('bytes', float(len(self.compressed))), ('bytes', 63),
                           ('bytes', BUILD.profile_image.MAX_IMAGE_BYTES + 1), ('sha256', 'A' * 64)):
            baseline = copy.deepcopy(self.kernel); self.kernel['build']['outputs']['Image.gz'][key] = value; self.save()
            with self.subTest(key=key), self.assertRaises(ValueError): BUILD.image_record(self.root, release=RELEASE)
            self.kernel = baseline

    def test_payload_fdt_prefix_hash_and_suffix_boundaries_are_exact(self):
        # Mutations killed: trust a wrong FDT frame/hash, short header or unprotected initramfs boundary.
        for dtb in (b'bad', struct.pack('>II', 0, 40) + self.dtb[8:],
                    struct.pack('>II', 0xd00dfeed, 39) + self.dtb[8:-1],
                    struct.pack('>II', 0xd00dfeed, 4 * 1024 * 1024 + 1) + self.dtb[8:],
                    self.dtb[:-1] + b'X'):
            if dtb[:4] != struct.pack('>I', 0xd00dfeed) or dtb[4:8] == struct.pack('>I', 39):
                self.metadata['dtb_sha256'] = hashlib.sha256(dtb).hexdigest()
            else:
                self.metadata['dtb_sha256'] = hashlib.sha256(self.dtb).hexdigest()
            self.payload(dtb, self.compressed, self.tail)
            with self.subTest(length=len(dtb)), self.assertRaises(ValueError): self.verify_payload()
        self.metadata['dtb_sha256'] = hashlib.sha256(self.dtb).hexdigest()
        self.payload(self.dtb, self.compressed, b'X' * len(self.tail))
        with self.assertRaises(ValueError): self.verify_payload()
        self.payload(self.dtb, self.compressed, self.tail)
        for prefix in (True, -1, 2 * 1024 * 1024 + 1):
            with self.assertRaises(ValueError):
                BUILD.payload_image(self.root, self.profile, self.metadata, prefix_bytes=prefix, release=RELEASE)
        self.profile['initramfs'].write_bytes(b'')
        with self.assertRaises(ValueError): self.verify_payload()

    def test_evidence_must_be_a_bounded_regular_file(self):
        # Mutations killed: follow evidence symlinks or parse an oversized otherwise valid JSON.
        path = self.folder / 'n71-dma-topology-qualification.json'; raw = path.read_text()
        path.write_text(raw + ' ' * (256 * 1024))
        with self.assertRaises(ValueError): BUILD.qualified(self.root, release=RELEASE)
        target = self.folder / 'private-fixture.json'; target.write_text(raw); path.unlink(); path.symlink_to(target)
        with self.assertRaises(ValueError): BUILD.qualified(self.root, release=RELEASE)


class IommuBuildMutations(unittest.TestCase):
    @unittest.skipIf(os.environ.get('N71_IOMMU_BUILD_MUTATION_CHILD'), 'Parent mutation gate only')
    def test_compiled_variants_fail_by_assertion(self):
        variants = {
            'module-byte-type': ("type(build['module_bytes']) is int", 'True'),
            'module-lower-bound': ("64 <= build['module_bytes']", "63 <= build['module_bytes']"),
            'module-sha-shape': ("re.fullmatch(r'[0-9a-f]{64}', build['module_sha256'])", 'True'),
            'kernel-source': ("kernel['source']['commit'] == qualified_build['source_commit']", 'True'),
            'kernel-config': ("outputs['config']['sha256'] == baseline['.config']", 'True'),
            'kernel-exports': ("build['vmlinux_symvers_sha256'] == baseline['vmlinux.symvers']", 'True'),
            'kernel-image-record': ("outputs['Image']['sha256'] == baseline['arch/arm64/boot/Image']", 'True'),
            'kernel-link': ("build['full_image_linked'] is True", 'True'),
            'kernel-modpost': ("build['vmlinux_modpost_verified'] is True", 'True'),
            'kernel-exit-type': ("type(build['exit_code']) is int", 'True'),
            'image-record-type': ("type(outputs[name]['bytes']) is int", 'True'),
            'image-record-upper-bound': ("<= profile_image.MAX_IMAGE_BYTES\n                and isinstance", "<= profile_image.MAX_IMAGE_BYTES + 1\n                and isinstance"),
            'gzip-sha': ("hashlib.sha256(raw).hexdigest() == outputs['Image.gz']['sha256']", 'True'),
            'gzip-size': ("len(raw) == outputs['Image.gz']['bytes']", 'True'),
            'gzip-eof': ('and decoder.eof', 'and True'),
            'gzip-unused-data': ('and not decoder.unused_data', 'and True'),
            'image-sha': ("hashlib.sha256(image).hexdigest() == outputs['Image']['sha256']", 'True'),
            'image-size': ("len(image) == outputs['Image']['bytes']", 'True'),
            'fdt-magic': ('magic == 0xd00dfeed', 'True'),
            'fdt-lower-bound': ('40 <= total', '39 <= total'),
            'fdt-sha': ("hashlib.sha256(dtb).hexdigest() == metadata.get('dtb_sha256')", 'True'),
            'initramfs-boundary': ('stream.read(tail + 1) == suffix', 'True'),
            'evidence-symlink': ('not path.is_symlink()', 'True'),
            'evidence-bound': ('path.stat().st_size <= 256 * 1024', 'True'),
        }
        source = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-iommu-build-mutations-') as directory:
            for name, (before, after) in variants.items():
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                env = dict(os.environ, N71_IOMMU_BUILD_MUTATION_CHILD='1', N71_IOMMU_BUILD_SCRIPT=str(path), PYTHONDONTWRITEBYTECODE='1')
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                                         '-p', 'test_n71_iommu_build.py', '-k', 'IommuBuildTests'],
                                        env=env, capture_output=True, text=True, timeout=30)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_IOMMU_BUILD_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
