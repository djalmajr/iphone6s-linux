"""Select only a qualified module hash while preserving the legacy rollback build."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import test_n71_resource_result as fixture

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71_resource_build.py'
SPEC = importlib.util.spec_from_file_location('resource_build_under_test', os.environ.get('N71_RESOURCE_BUILD_SCRIPT', SOURCE))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
fixture.RESOURCE.n71_resource_build = BUILD
EVIDENCE = ROOT / 'docs/evidence/n71-pci-resource-readback.json'


class ResourceBuildTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.folder = self.root / 'docs/evidence'; self.folder.mkdir(parents=True)
        self.evidence = json.loads(EVIDENCE.read_text())
        self.release = self.evidence['real_module_build']['release']
        self.previous = fixture.RESOURCE.selected_records(ROOT, release=self.release)
        self.digest = self.evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']
        (self.folder / 'n71-pci-resource-assignment.json').write_bytes((ROOT / 'docs/evidence/n71-pci-resource-assignment.json').read_bytes())

    def select(self, evidence=None, digest=None):
        (self.folder / EVIDENCE.name).write_text(json.dumps(evidence if evidence is not None else self.evidence))
        return BUILD.select(self.root, self.previous, release=self.release, pcie_sha256=digest if digest is not None else self.digest)

    def test_explicit_module_selects_required_record_and_preserves_reg_on(self):
        # Mutations killed: select a different hash, erase the required record or change the retained REG_ON module.
        records = self.select()
        self.assertIs(records[0].get('assignment_readback'), True)
        self.assertEqual(records[0]['sha256'], self.digest)
        self.assertEqual(records[1], self.previous[1])
        self.assertEqual(fixture.RESOURCE.selected_records(ROOT, release=self.release, pcie_sha256=self.digest), records)
        for digest in ('0' * 64, self.previous[0]['sha256']):
            with self.assertRaises(ValueError):
                self.select(digest=digest)
        for digest in (1, '', 'A' * 64, 'a' * 63):
            with self.assertRaises(ValueError):
                BUILD.select(self.root, self.previous, release=self.release, pcie_sha256=digest)

    def test_default_and_explicit_legacy_selection_stay_identical(self):
        # Mutation killed: force the new build or add a fictitious readback requirement to the old profile.
        records = fixture.RESOURCE.selected_records(ROOT, release=self.release, pcie_sha256=self.previous[0]['sha256'])
        self.assertEqual(records, self.previous)
        self.assertNotIn('assignment_readback', records[0])

    def test_qualification_flags_base_and_interface_are_exact(self):
        # Mutations killed: accept truthy flags, a changed base, unqualified compilation or missing allocator/getter APIs.
        for flag in BUILD.FLAGS:
            for value in (False, 1, 'true'):
                bad = copy.deepcopy(self.evidence); bad['contract'][flag] = value
                with self.assertRaises(ValueError):
                    self.select(bad)
        for field in ('werror', 'modpost_passed', 'elf_vermagic_verified', 'source_config_image_exports_preserved', 'first_write_readback_report_compiled'):
            for value in (False, 1):
                bad = copy.deepcopy(self.evidence); bad['real_module_build'][field] = value
                with self.assertRaises(ValueError):
                    self.select(bad)
        bad = copy.deepcopy(self.evidence); bad['base_assignment_evidence_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.select(bad)
        for field, value in (('format', True), ('format', 2)):
            bad = copy.deepcopy(self.evidence); bad[field] = value
            with self.assertRaises(ValueError):
                self.select(bad)
        for value in (False, 1):
            bad = copy.deepcopy(self.evidence); bad['real_module_build']['exit_code'] = value
            with self.assertRaises(ValueError):
                self.select(bad)
        for field in ('allocator_exports_linked', 'parameters'):
            bad = copy.deepcopy(self.evidence); bad['real_module_build']['module_interface'][field] = []
            with self.assertRaises(ValueError):
                self.select(bad)

    def test_module_bytes_abi_and_scope_refuse_unqualified_records(self):
        # Mutations killed: lower the size bound, erase the ABI, accept physical claims or replace REG_ON.
        for field, value in (('bytes', 63), ('bytes', True), ('bytes', 256 * 1024 + 1), ('sha256', 'a' * 63), ('vermagic', 'wrong')):
            bad = copy.deepcopy(self.evidence); bad['real_module_build']['modules']['n71-pcie-diagnostic.ko'][field] = value
            with self.assertRaises(ValueError):
                self.select(bad)
        bad = copy.deepcopy(self.evidence); bad['real_module_build']['modules']['n71-wlan-power-diagnostic.ko']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.select(bad)
        for field in self.evidence['limits']:
            for value in (True, 0):
                bad = copy.deepcopy(self.evidence); bad['limits'][field] = value
                with self.assertRaises(ValueError):
                    self.select(bad)


class ResourceBuildMutationsTests(unittest.TestCase):
    def test_compiled_guard_mutations_fail_by_assertion(self):
        variants = {
            'base-evidence-lost': ("evidence.get('base_assignment_evidence_sha256') == hashlib.sha256(base.read_bytes()).hexdigest()", 'True'),
            'truthy-contract': ("evidence.get('contract', {}).get(name) is True", "bool(evidence.get('contract', {}).get(name))"),
            'truthy-build': ('build.get(name) is True', 'bool(build.get(name))'),
            'boolean-build-exit': ("type(build.get('exit_code')) is int", "isinstance(build.get('exit_code'), int)"),
            'physical-scope-lost': ('limits.get(name) is False', 'not limits.get(name)'),
            'module-size-boundary': ("64 <= row['bytes']", "63 <= row['bytes']"),
            'reg-on-replaced': ('records[1] == previous[1]', 'True'),
            'requested-module-lost': ("records[0]['sha256'] == pcie_sha256", 'True'),
            'required-record-lost': ("records[0]['assignment_readback'] = True", "records[0]['assignment_readback'] = False"),
        }
        source = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-readback-build-') as directory:
            for name, (before, after) in variants.items():
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', N71_RESOURCE_BUILD_SCRIPT=str(path))
                run = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                      '-p', 'test_n71_resource_build.py', '-k', 'ResourceBuildTests'],
                                     cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
                output = run.stdout + run.stderr
                self.assertNotEqual(run.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_RESOURCE_BUILD_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
