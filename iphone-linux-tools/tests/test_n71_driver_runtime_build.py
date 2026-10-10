"""Qualified caller/WCC selection must reject a mixed kernel or unproved input set."""
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import ModuleType
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_build as BUILD
import n71_iommu_build as IOMMU
import n71_resource_result as RESOURCES
import n71_driver_modules as WLAN
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_build.py'
CALLER = 'n71-brcmfmac-caller-qualified.json'
WCC = 'n71-brcmfmac-pcie-modules-qualified.json'


class RuntimeBuildTests(unittest.TestCase):
    subject = BUILD

    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.root = Path(directory.name); self.folder = self.root / 'docs/evidence'; self.folder.mkdir(parents=True)
        for path in (ROOT / 'docs/evidence').glob('*.json'): shutil.copyfile(path, self.folder / path.name)
        self.proof = json.loads((self.folder / CALLER).read_text()); self.wcc = json.loads((self.folder / WCC).read_text())
        for name in self.proof['inputs']:
            target = self.root / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT / name, target)
        self.request = {'release':WLAN.RELEASE, 'pcie_sha256':self.proof['module']['sha256']}

    def save(self):
        for name, value in ((CALLER,self.proof),(WCC,self.wcc)): (self.folder / name).write_text(json.dumps(value))

    def selected(self):
        try: return self.subject.select(self.root, self.request)
        except ValueError as error: self.fail('Qualified runtime build refused: ' + str(error))

    def test_exact_selection_preserves_assignment_reg_on_and_ordered_wcc_without_writing(self):
        # Mutations: retain the old diagnostic, lose existing assignment flags or widen the WCC stack.
        original = {str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        parent = IOMMU.qualified(self.root, release=WLAN.RELEASE)
        legacy = RESOURCES.selected_records(self.root, release=WLAN.RELEASE, pcie_sha256=parent['module_sha256'], iommu_parent=True)
        expected = copy.deepcopy(legacy); expected[0].update({k:self.proof['module'][k] for k in ('bytes','sha256','vermagic')}, driver_runtime=True)
        result = self.selected()
        self.assertEqual(result['diagnostics'], expected); self.assertEqual(result['drivers'], WLAN.qualified(self.root))
        self.assertEqual(result['kernel_outputs'], IOMMU.image_record(self.root, release=WLAN.RELEASE))
        self.assertEqual([record['name'] for record in result['drivers']], list(WLAN.NAMES))
        self.assertEqual(result['diagnostics'][1], legacy[1]); self.assertNotEqual(result['diagnostics'][0]['sha256'], legacy[0]['sha256'])
        self.assertEqual(original, {str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()})

    def test_explicit_hash_release_and_request_schema_have_no_legacy_fallback(self):
        # Mutation: skip explicit selection or accept the old IOMMU hash as a runtime caller.
        parent = IOMMU.qualified(self.root, release=WLAN.RELEASE)
        bad = [dict(self.request, pcie_sha256='f'*64), dict(self.request, pcie_sha256=parent['module_sha256']),
            dict(self.request, release='foreign'), dict(self.request, pcie_sha256=None), dict(self.request, extra=True)]
        for request in bad:
            with self.subTest(request=request), self.assertRaises(ValueError): self.subject.select(self.root, request)

    def test_runtime_scope_defaults_getter_and_first_cause_cannot_widen(self):
        # Mutation: trust qualification while changing runtime defaults, actions, owners or first-cause rules.
        original = copy.deepcopy(self.proof)
        for name, value in [('default_driver_runtime',True),('automatic_prepare_or_firmware_load',True),
            ('getter_has_no_effects',False),('first_async_error_preserved',False),('publication_is_intent_only',0),
            ('actions',['driver-publish']),('partial_owners',[]),('driver_status_fields',[]),('cleanup_before',['power'])]:
            self.proof = copy.deepcopy(original); self.proof['scope'][name] = value; self.save()
            with self.subTest(name=name), self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)

    def test_caller_and_wcc_kernel_bases_are_independently_bound(self):
        # Mutations: omit either caller/base equality or the WCC source/config/Image/exports/gzip binding.
        original = copy.deepcopy(self.proof); wcc = copy.deepcopy(self.wcc)
        for name, value in original['preserved_kernel'].items():
            self.proof = copy.deepcopy(original); self.proof['preserved_kernel'][name] = 'f' * len(value); self.save()
            with self.subTest(caller=name), self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)
        self.proof = original
        for name in ('source_head','source_diff_sha256','.config','vmlinux.symvers','arch/arm64/boot/Image','full-link-v1-20261005/Image.gz'):
            self.wcc = copy.deepcopy(wcc); self.wcc['baseline'][name] = 'f' * len(self.wcc['baseline'][name]); self.save()
            with self.subTest(wcc=name), self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)

    def test_input_hash_bytes_leaf_and_parent_links_are_rejected(self):
        # Mutations: skip input integrity, accept a link or resolve a redirected input directory.
        name = 'phone/kernel/n71-brcmfmac-config.h'; path = self.root / name; raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        with self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)
        path.write_bytes(raw + b'changed')
        with self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)
        backup = self.root / 'original-input.h'; backup.write_bytes(raw); path.unlink(); path.symlink_to(backup)
        with self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)
        path.unlink(); path.write_bytes(raw)
        directory = self.root / 'phone/kernel'; moved = self.root / 'redirected-kernel'; directory.rename(moved); directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)

    def test_compiled_path_set_and_bounded_records_cannot_be_substituted(self):
        # Mutations: let an unrelated file replace a compiled input or drop record count/type/budget checks.
        original = copy.deepcopy(self.proof); old = 'tests/n71_pcie_scan_host.c'; new = 'tests/n71_other.c'
        (self.root / new).write_bytes((self.root / old).read_bytes())
        self.proof['inputs'][new] = self.proof['inputs'].pop(old); self.save()
        with self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)
        self.proof = copy.deepcopy(original); self.proof['inputs']['tests/../private.c'] = self.proof['inputs'].pop(old); self.save()
        with self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)
        for changes in [('count',69.0),('bytes',True),('budget',2*1024*1024+1),('hash','F'*64)]:
            self.proof = copy.deepcopy(original); key,value = changes
            if key=='count': self.proof['input_count'] = value
            else: self.proof['inputs'][old]['sha256' if key=='hash' else 'bytes'] = value
            self.save()
            with self.subTest(key=key), self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)

    def test_module_abi_imports_and_getter_require_complete_qualification(self):
        # Mutations: trust a foreign ELF/vermagic/size or omit import/getter qualification.
        original = copy.deepcopy(self.proof)
        for key,value in [('elf64_aarch64',False),('vermagic','foreign'),('bytes',False),('bytes',63),
            ('imports',[]),('parameters',[]),('sha256','f'*64)]:
            self.proof = copy.deepcopy(original); self.proof['module'][key] = value; self.save()
            with self.subTest(key=key), self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)

    def test_platform_proof_and_wcc_variant_cannot_claim_unqualified_builds(self):
        # Mutations: skip audit/platform qualification or allow unrelated WCC configuration and vendors.
        original = copy.deepcopy(self.proof)
        for key,value in [('format',True),('status','unqualified'),('input_hashes_verified_on_vm_and_mac',False),('module_bytes_and_hash_verified_on_mac',False)]:
            self.proof = copy.deepcopy(original); self.proof[key] = value; self.save()
            with self.subTest(key=key), self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)
        self.proof = copy.deepcopy(original); self.proof['gates']['ubuntu_arm64']['total_cases'] = 575.0; self.save()
        with self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)
        self.proof = original; self.wcc['variant_config_changes']['CONFIG_BRCMFMAC_USB'] = ['n','y']; self.save()
        with self.assertRaises(ValueError): self.subject.qualified(self.root, self.request)


class RuntimeBuildMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeBuildTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        source = SOURCE.read_text(); exact = 'test_exact_selection_preserves_assignment_reg_on_and_ordered_wcc_without_writing'
        mutations = [
            ('caller-replacement', "records[0].update(selected['diagnostic'], driver_runtime=True)", 'pass', exact),
            ('explicit-runtime', 'driver_runtime=True', 'driver_runtime=False', exact),
            ('explicit-hash', "record.get('sha256') == request['pcie_sha256']", 'True', 'test_explicit_hash_release_and_request_schema_have_no_legacy_fallback'),
            ('runtime-scope', 'scope == SCOPE', 'True', 'test_runtime_scope_defaults_getter_and_first_cause_cannot_widen'),
            ('input-revalidation', 'inputs(root, proof)\n    record', 'pass\n    record', 'test_input_hash_bytes_leaf_and_parent_links_are_rejected'),
            ('compiled-paths', "hashlib.sha256('\\n'.join(sorted(records)).encode()).hexdigest() == INPUT_PATHS_SHA256", 'True', 'test_compiled_path_set_and_bounded_records_cannot_be_substituted'),
            ('parent-link', 'path.resolve() == root.resolve() / name', 'True', 'test_input_hash_bytes_leaf_and_parent_links_are_rejected'),
            ('input-content', "hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']", 'True', 'test_input_hash_bytes_leaf_and_parent_links_are_rejected'),
            ('caller-kernel-base', "proof.get('source_commit') == parent['source_commit'] and proof.get('preserved_kernel') == preserved", 'True', 'test_caller_and_wcc_kernel_bases_are_independently_bound'),
            ('wcc-source-base', "wcc.get('source_head') == preserved['source_commit']", 'True', 'test_caller_and_wcc_kernel_bases_are_independently_bound'),
            ('wcc-image-base', "wcc.get('arch/arm64/boot/Image') == outputs['Image']['sha256']", 'True', 'test_caller_and_wcc_kernel_bases_are_independently_bound'),
            ('module-elf', "record.get('elf64_aarch64') is True", 'True', 'test_module_abi_imports_and_getter_require_complete_qualification'),
            ('complete-imports', 'len(imports) == 135', 'True', 'test_module_abi_imports_and_getter_require_complete_qualification'),
            ('mac-module-audit', "proof.get('module_bytes_and_hash_verified_on_mac') is True", 'True', 'test_platform_proof_and_wcc_variant_cannot_claim_unqualified_builds'),
        ]
        for name, before, after, method in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(before), 1, name)
                subject = ModuleType('runtime_build_mutant')
                exec(compile(ast.parse(source.replace(before, after, 1)), str(SOURCE), 'exec'), subject.__dict__)
                case = type('MutatedRuntimeBuildTests', (RuntimeBuildTests,), {'subject':subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name); self.assertGreater(len(result.failures), 0, name)
                print('N71_RUNTIME_BUILD_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
