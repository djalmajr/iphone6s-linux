"""Real filesystem/record binding probes; no kernel or phone is operated."""
import gzip
from functools import lru_cache
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_iommu_build
import n71_pmd_source_reference


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SOURCE = ROOT / 'scripts/host/n71_pmd_runtime_build.py'
SUBJECT = load('pmd_under_test', Path(os.environ.get('N71_PMD_RUNTIME_BUILD_SCRIPT', SOURCE)))
IOMMU = load('pmd_iommu_under_test', Path(os.environ.get('N71_PMD_IOMMU_SCRIPT',
                                                    ROOT / 'scripts/host/n71_iommu_build.py')))
RESOURCES = load('pmd_resources_under_test', Path(os.environ.get('N71_PMD_RESOURCE_SCRIPT',
                                                              ROOT / 'scripts/host/n71_resource_result.py')))
KERNEL = 'kernel-n71-pmd-build.json'
DIAGNOSTICS = 'n71-pmd-diagnostics-build.json'
MANIFEST = 'n71-pmd-diagnostic-inputs.json'
REUSE = 'n71-pmd-caller-reuse.json'
NATIVE = 'n71-brcmfmac-caller-qualified.json'


@lru_cache(maxsize=1)
def compiled_inputs():
    """Read the old build's exact data; never execute an archived test or script."""
    folder = ROOT / 'docs/evidence'
    records = json.loads((folder / NATIVE).read_text())['inputs']
    records.update(json.loads((folder / MANIFEST).read_text())['inputs'])
    digest = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if digest != n71_pmd_source_reference.INPUTS_PIN:
        raise ValueError('Compiled fixture input manifest changed')
    prefix = ROOT.name + '/'
    raw = subprocess.check_output(['git', 'archive', '--format=tar',
        n71_pmd_source_reference.COMMIT, '--', *[prefix + name for name in sorted(records)]],
        cwd=ROOT.parent, timeout=30)
    if len(raw) > 1024 * 1024:
        raise ValueError('Compiled fixture archive exceeds budget')
    result = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            if member.isdir():
                continue
            name = member.name.removeprefix(prefix)
            if not member.isfile() or name not in records or name in result:
                raise ValueError('Compiled fixture archive entry differs')
            stream = archive.extractfile(member)
            with stream:
                data = stream.read()
            if len(data) != records[name]['bytes'] or hashlib.sha256(data).hexdigest() != records[name]['sha256']:
                raise ValueError('Compiled fixture source bytes differ')
            result[name] = data
    if set(result) != set(records):
        raise ValueError('Full local Git history with the compiled source commit required')
    return result


def compiled_source(name):
    historical = compiled_inputs()
    return historical[name] if name in historical else (ROOT / name).read_bytes()


class PmdRuntime(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='n71-pmd-runtime-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.folder = self.root / 'docs/evidence'; self.folder.mkdir(parents=True)
        names = [KERNEL, DIAGNOSTICS, MANIFEST, REUSE, NATIVE, 'kernel-n71-binding-build.json',
                 'n71-dma-topology-qualification.json', 'n71-pci-held-caller.json',
                 'n71-pci-resource-assignment.json', 'n71-pci-resource-readback.json',
                 'n71-pci-optional-build.json', 'n71-pci-io16-build.json', 'n71-pci-pref64-build.json',
                 'n71-pci-pref64-unsized-build.json', 'n71-pci-pref64-unsized-adapter.json',
                 'n71-pci-pref64-policy.json']
        for name in names:
            shutil.copyfile(ROOT / 'docs/evidence' / name, self.folder / name)
        source_names = set(self.read(MANIFEST)['inputs']) | set(self.read(NATIVE)['inputs'])
        for name in source_names:
            target = self.root / name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(compiled_source(name))
        self.original = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.module_patch = patch.dict(sys.modules, {'n71_pmd_runtime_build': SUBJECT})
        self.module_patch.start(); self.addCleanup(self.module_patch.stop)

    def read(self, name):
        return json.loads((self.folder / name).read_text())

    def write(self, name, data):
        (self.folder / name).write_text(json.dumps(data))

    def restore(self):
        for path, raw in self.original.items():
            if path.is_symlink(): path.unlink()
            path.write_bytes(raw)

    def edit(self, name, keys, value):
        data = self.read(name); target = data
        for key in keys[:-1]: target = target[key]
        target[keys[-1]] = value; self.write(name, data)
        if name == NATIVE:
            reuse = self.read(REUSE)
            reuse['reference_proof']['sha256'] = hashlib.sha256((self.folder / NATIVE).read_bytes()).hexdigest()
            self.write(REUSE, reuse)

    def accepted(self, function, *args, **kwargs):
        try: return function(*args, **kwargs)
        except (ValueError, KeyError, OSError) as error: self.fail('Valid PMD facts refused: ' + str(error))

    def parent(self):
        return IOMMU.qualified(self.root, release=SUBJECT.RELEASE)

    def records(self, **overrides):
        request = dict(release=SUBJECT.RELEASE, pcie_sha256=self.read(DIAGNOSTICS)['modules']['n71_pcie_diagnostic']['sha256'],
                       iommu_parent=True)
        return RESOURCES.selected_records(self.root, **(request | overrides))

    def test_current_records_select_pmd_without_changing_legacy_or_sources(self):
        # Mutations killed: remove either explicit PMD selector route.
        previous = n71_iommu_build.qualified(self.root, release=SUBJECT.LEGACY)
        parent = self.accepted(self.parent)
        self.assertEqual(parent['module_sha256'], self.read(DIAGNOSTICS)['modules']['n71_pcie_diagnostic']['sha256'])
        self.assertNotEqual(parent['module_sha256'], previous['module_sha256'])
        selected = self.accepted(self.records)
        self.assertEqual([r['module'] for r in selected], ['n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko'])
        self.assertTrue(all(selected[0][key] is True for key in (
            'assignment_readback', 'assignment_optional_windows', 'assignment_io16_upper',
            'assignment_pref64_disable', 'iommu_parent')))
        self.assertNotIn('driver_runtime', selected[0])
        self.assertTrue(all(row['vermagic'] == SUBJECT.RELEASE + SUBJECT.ABI for row in selected))
        self.assertEqual(n71_iommu_build.qualified(self.root, release=SUBJECT.LEGACY), previous)
        self.assertEqual({p: p.read_bytes() for p in self.original}, self.original)

    def test_kernel_and_diagnostic_build_facts_are_coupled(self):
        # Mutations killed: drop the source pin, kernel coupling or ABI comparison.
        cases = [(KERNEL, ('build', 'exit_code'), False), (KERNEL, ('build', 'full_image_linked'), False),
                 (KERNEL, ('build', 'serdev_stop_bits_export_verified'), False),
                 (KERNEL, ('build', 'kernel_release'), SUBJECT.LEGACY),
                 (DIAGNOSTICS, ('kernel_hashes', '.config'), 'f' * 64),
                 (DIAGNOSTICS, ('loaded',), True), (DIAGNOSTICS, ('w1_werror',), False),
                 (DIAGNOSTICS, ('modules', 'n71_pcie_diagnostic', 'bytes'), True),
                 (DIAGNOSTICS, ('modules', 'n71_pcie_diagnostic', 'vermagic'), SUBJECT.LEGACY + SUBJECT.ABI)]
        for name, keys, value in cases:
            with self.subTest(name=name, keys=keys):
                self.restore(); self.edit(name, keys, value)
                with self.assertRaises(ValueError): self.parent()
        self.restore()
        patchname = '0009-s5l8960x-dart-pmd.patch'
        self.edit(KERNEL, ('source', 'patches', patchname), 'f' * 64)
        self.edit(DIAGNOSTICS, ('source_bundle', 'patches', patchname), 'f' * 64)
        with self.assertRaises(ValueError): self.parent()

    def test_compiled_inputs_pin_refuses_even_consistent_new_i2c_source(self):
        # Mutation killed: accept a consistently rewritten but unbuilt input manifest.
        path = self.root / SUBJECT.I2C; path.write_bytes(path.read_bytes() + b'\n/* new unbuilt input */\n')
        item = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        self.edit(MANIFEST, ('inputs', SUBJECT.I2C), item)
        self.edit(DIAGNOSTICS, ('inputs_sha256', SUBJECT.I2C), item['sha256'])
        with self.assertRaises(ValueError): self.parent()

    def test_source_bytes_and_aliases_are_checked_with_unchanged_size(self):
        # Mutation killed: trust recorded source size without hashing the actual bytes.
        source = self.root / 'phone/kernel/n71-pcie-diagnostic.c'
        raw = source.read_bytes(); source.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        with self.assertRaises(ValueError): self.parent()
        self.restore()
        alias = self.root / 'same-source.c'; alias.write_bytes(raw); source.unlink(); source.symlink_to(alias)
        with self.assertRaises(ValueError): self.parent()
        self.restore()
        path = self.folder / KERNEL; raw = path.read_bytes(); path.write_bytes(raw + b' ' * (256 * 1024))
        with self.assertRaises(ValueError): self.parent()

    def test_native_scope_interface_binary_and_kernel_bindings_are_required(self):
        # Mutations killed: omit caller scope or new module identity from reuse checks.
        cases = [(NATIVE, ('scope', 'default_driver_runtime'), True),
                 (NATIVE, ('gates', 'mac', 'total_cases'), 574),
                 (REUSE, ('reference_proof', 'sha256'), 'f' * 64),
                 (REUSE, ('binary_comparison', 'new_module_sha256'), 'f' * 64),
                 (REUSE, ('binary_comparison', 'all_executable_progbits_sections_identical'), False),
                 (REUSE, ('binary_comparison', 'modinfo_diff_is_only_selected_vermagic'), False),
                 (REUSE, ('new_kernel_context', 'symbols', 'pci_real_dma_dev'), 'T'),
                 (REUSE, ('new_kernel_context', 'exports_sha256'), 'f' * 64),
                 (DIAGNOSTICS, ('modules', 'n71_pcie_diagnostic', 'parameters'), [])]
        for name, keys, value in cases:
            with self.subTest(name=name, keys=keys):
                self.restore(); self.edit(name, keys, value)
                with self.assertRaises(ValueError): self.parent()

    def test_resource_request_and_historical_contract_refusals_are_preserved(self):
        # Historical guards are also exercised by the focused legacy mutation gates.
        for request in ({'iommu_parent': False}, {'iommu_parent': 1}, {'pcie_sha256': None},
                        {'pcie_sha256': 'f' * 64}, {'pcie_sha256': self.read(NATIVE)['module']['sha256']}):
            with self.subTest(request=request), self.assertRaises(ValueError): self.records(**request)
        for name, keys in [('n71-pci-held-caller.json', ('api', 'default_enabled')),
                           ('n71-pci-resource-assignment.json', ('contract', 'cleanup_failure_retains_bridge_and_owners'))]:
            self.restore(); self.edit(name, keys, name.endswith('held-caller.json'))
            with self.subTest(name=name), self.assertRaises(ValueError): self.records()
        with self.assertRaises(ValueError): SUBJECT.qualified(self.root, release='unrecorded')

    def test_real_gzip_payload_and_crossed_or_extra_streams_are_refused(self):
        # Mutation killed: route the selected PMD Image to the legacy build descriptor.
        # Synthetic nonbootable Image isolates the real gzip/payload reader boundary.
        image = bytes(range(256)) * 4; compressed = gzip.compress(image, mtime=0)
        kernel = self.read(KERNEL); modules = self.read(DIAGNOSTICS)
        kernel['build']['outputs']['Image'] = {'bytes': len(image), 'sha256': hashlib.sha256(image).hexdigest()}
        kernel['build']['outputs']['Image.gz'] = {'bytes': len(compressed), 'sha256': hashlib.sha256(compressed).hexdigest()}
        modules['kernel_hashes']['arch/arm64/boot/Image'] = hashlib.sha256(image).hexdigest()
        self.write(KERNEL, kernel); self.write(DIAGNOSTICS, modules)
        expected = hashlib.sha256(image).hexdigest()
        self.assertEqual(self.accepted(IOMMU.kernel_image, self.root, compressed, release=SUBJECT.RELEASE), expected)
        prefix = b'NONBOOTABLE_PREFIX'.ljust(64, b'_')
        dtb = struct.pack('>II', 0xd00dfeed, 40) + b'SYNTHETIC_FDT'.ljust(32, b'_'); tail = b'PRIVATE_SYNTHETIC_SUFFIX'
        payload, initramfs = self.root / 'payload.bin', self.root / 'initramfs.gz'
        payload.write_bytes(prefix + dtb + compressed + tail); initramfs.write_bytes(tail)
        profile = {'payload': payload, 'initramfs': initramfs}; metadata = {'dtb_sha256': hashlib.sha256(dtb).hexdigest()}
        self.assertEqual(self.accepted(IOMMU.payload_image, self.root, profile, metadata,
                         prefix_bytes=len(prefix), release=SUBJECT.RELEASE), expected)
        payload.write_bytes(prefix + dtb + compressed + tail + b'X')
        with self.assertRaises(ValueError):
            IOMMU.payload_image(self.root, profile, metadata, prefix_bytes=len(prefix), release=SUBJECT.RELEASE)
        extra = compressed + gzip.compress(b'', mtime=0)
        kernel['build']['outputs']['Image.gz'] = {'bytes': len(extra), 'sha256': hashlib.sha256(extra).hexdigest()}
        self.write(KERNEL, kernel)
        with self.assertRaises(ValueError): IOMMU.kernel_image(self.root, extra, release=SUBJECT.RELEASE)


@unittest.skipIf(any(os.environ.get(name) for name in ('N71_PMD_RUNTIME_BUILD_SCRIPT',
                'N71_PMD_IOMMU_SCRIPT', 'N71_PMD_RESOURCE_SCRIPT')), 'Mutation child selects subject')
class PmdRuntimeMutations(unittest.TestCase):
    def test_weakened_new_bindings_and_routes_fail_by_assertion(self):
        variants = [
            ('source', SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT', "digest(kernel['source']) == SOURCE_PIN", 'True', 'kernel_and_diagnostic_build_facts_are_coupled'),
            ('inputs', SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT', "digest(manifest.get('inputs')) == INPUTS_PIN", 'True', 'compiled_inputs_pin_refuses_even_consistent_new_i2c_source'),
            ('kernel-coupling', SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT', "modules.get('kernel_hashes') == hashes", 'True', 'kernel_and_diagnostic_build_facts_are_coupled'),
            ('abi', SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT', "row.get('vermagic') == release + ABI", 'True', 'kernel_and_diagnostic_build_facts_are_coupled'),
            ('bytes', SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT', "hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256']", 'True', 'source_bytes_and_aliases_are_checked_with_unchanged_size'),
            ('scope', SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT', "native.get('scope') == caller.SCOPE", 'True', 'native_scope_interface_binary_and_kernel_bindings_are_required'),
            ('binary', SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT', "comparison.get('new_module_sha256') == pcie['sha256']", 'True', 'native_scope_interface_binary_and_kernel_bindings_are_required'),
            ('iommu-route', ROOT/'scripts/host/n71_iommu_build.py', 'N71_PMD_IOMMU_SCRIPT', 'if release == PMD_RELEASE:', 'if False:', 'current_records_select_pmd_without_changing_legacy_or_sources'),
            ('image-route', ROOT/'scripts/host/n71_iommu_build.py', 'N71_PMD_IOMMU_SCRIPT', "'kernel-n71-pmd-build.json' if release == PMD_RELEASE", "'kernel-n71-binding-build.json' if release == PMD_RELEASE", 'real_gzip_payload_and_crossed_or_extra_streams_are_refused'),
            ('resource-route', ROOT/'scripts/host/n71_resource_result.py', 'N71_PMD_RESOURCE_SCRIPT', 'if release == n71_iommu_build.PMD_RELEASE:', 'if False:', 'current_records_select_pmd_without_changing_legacy_or_sources'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-pmd-runtime-mutations-') as directory:
            for name, source, variable, before, after, method in variants:
                text = source.read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory)/(name+'.py'); path.write_text(body)
                environment = dict(os.environ, **{variable: str(path)}, PYTHONDONTWRITEBYTECODE='1',
                                   PYTHONPATH=str(ROOT/'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                    'test_n71_pmd_runtime_build.PmdRuntime.test_'+method], env=environment,
                    capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name+result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name+result.stderr)
                print('PMD_RUNTIME_ASSERTION_KILL '+name, flush=True)


if __name__ == '__main__':
    unittest.main()
