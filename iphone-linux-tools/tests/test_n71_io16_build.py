"""Select the qualified IO16 bytes and preserve all older rollback contracts."""
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
SPEC = importlib.util.spec_from_file_location('io16_build_under_test', os.environ.get('N71_IO16_BUILD_SCRIPT', SOURCE))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
EVIDENCE = ROOT / 'docs/evidence/n71-pci-io16-build.json'


class IO16BuildTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name); self.folder = self.root / 'docs/evidence'; self.folder.mkdir(parents=True)
        for name in ('n71-pci-resource-assignment.json', 'n71-pci-resource-readback.json', 'n71-pci-optional-build.json'):
            (self.folder / name).write_bytes((ROOT / 'docs/evidence' / name).read_bytes())
        self.evidence = json.loads(EVIDENCE.read_text()); self.release = self.evidence['real_module_build']['release']
        self.previous = fixture.RESOURCE.selected_records(ROOT, release=self.release)
        self.digest = self.evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']

    def select(self, evidence=None, digest=None):
        (self.folder / EVIDENCE.name).write_text(json.dumps(self.evidence if evidence is None else evidence))
        return BUILD.select(self.root, self.previous, release=self.release,
                            pcie_sha256=self.digest if digest is None else digest)

    def test_known_bytes_select_all_three_reports_and_preserve_reg_on(self):
        records = self.select()
        for key in ('assignment_readback', 'assignment_optional_windows', 'assignment_io16_upper'):
            self.assertIs(records[0].get(key), True)
        self.assertEqual(records[0]['sha256'], self.digest); self.assertEqual(records[1], self.previous[1])
        self.assertEqual(fixture.RESOURCE.selected_records(ROOT, release=self.release, pcie_sha256=self.digest), records)
        with self.assertRaises(ValueError):
            self.select(digest='0' * 64)

    def test_older_bytes_keep_their_original_report_contracts(self):
        for name, optional in (('n71-pci-resource-readback.json', False), ('n71-pci-optional-build.json', True)):
            digest = json.loads((self.folder / name).read_text())['real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']
            records = self.select(digest=digest)
            self.assertIs(records[0].get('assignment_readback'), True)
            self.assertEqual(records[0].get('assignment_optional_windows', False), optional)
            self.assertNotIn('assignment_io16_upper', records[0]); self.assertEqual(records[1], self.previous[1])

    def test_io16_contract_and_compilation_require_exact_qualified_booleans(self):
        for field in BUILD.IO16_FLAGS:
            for value in (False, 1):
                bad = copy.deepcopy(self.evidence); bad['io16_contract'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.select(bad)
        for field in ('native_policy_adapter_qualified', 'host_contract_qualified'):
            for value in (False, 1):
                bad = copy.deepcopy(self.evidence); bad[field] = value
                with self.assertRaises(ValueError):
                    self.select(bad)
        for value in (False, 1):
            bad = copy.deepcopy(self.evidence); bad['real_module_build']['io16_upper_report_compiled'] = value
            with self.assertRaises(ValueError):
                self.select(bad)

    def test_base_abi_bytes_reg_on_and_proof_scope_remain_bound(self):
        for field in ('base_optional_evidence_sha256', 'base_readback_evidence_sha256'):
            bad = copy.deepcopy(self.evidence); bad[field] = '0' * 64
            with self.assertRaises(ValueError):
                self.select(bad)
        for field, value in (('bytes', 63), ('bytes', True), ('vermagic', 'wrong')):
            bad = copy.deepcopy(self.evidence); bad['real_module_build']['modules']['n71-pcie-diagnostic.ko'][field] = value
            with self.assertRaises(ValueError):
                self.select(bad)
        bad = copy.deepcopy(self.evidence); bad['real_module_build']['modules']['n71-wlan-power-diagnostic.ko']['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.select(bad)
        for field in self.evidence['limits']:
            bad = copy.deepcopy(self.evidence); bad['limits'][field] = True
            with self.assertRaises(ValueError):
                self.select(bad)

    def test_missing_or_linked_evidence_does_not_select_the_new_bytes(self):
        with self.assertRaises(ValueError):
            BUILD.select(self.root, self.previous, release=self.release, pcie_sha256=self.digest)
        target = self.folder / 'saved-io16.json'; target.write_bytes(EVIDENCE.read_bytes())
        (self.folder / EVIDENCE.name).symlink_to(target)
        with self.assertRaises(ValueError):
            BUILD.select(self.root, self.previous, release=self.release, pcie_sha256=self.digest)


class IO16BuildMutationTests(unittest.TestCase):
    def test_io16_selection_guards_die_by_assertion(self):
        variants = {
            'optional-base-lost': ("candidate.get('base_optional_evidence_sha256') == hashlib.sha256(base.read_bytes()).hexdigest()", 'True'),
            'truthy-io16-contract': ('io16_contract.get(name) is True', 'bool(io16_contract.get(name))'),
            'compiled-report-lost': ("build.get('io16_upper_report_compiled') is True", 'True'),
            'required-io16-record-lost': ("records[0]['assignment_io16_upper'] = True", "records[0]['assignment_io16_upper'] = False"),
            'io16-selection-lost': ('io16 = candidate is not None', 'io16 = False'),
            'linked-candidate-accepted': ("path.is_file() and not path.is_symlink() and path.stat().st_size <= 256 * 1024,\n            'Optional build", "path.is_file() and path.stat().st_size <= 256 * 1024,\n            'Optional build"),
            'readback-base-lost': ("candidate.get('base_readback_evidence_sha256') == hashlib.sha256(original.read_bytes()).hexdigest()", 'True'),
            'truthy-native-proof': ("evidence.get('native_policy_adapter_qualified') is True", "bool(evidence.get('native_policy_adapter_qualified'))"),
            'truthy-host-proof': ("evidence.get('host_contract_qualified') is True", "bool(evidence.get('host_contract_qualified'))"),
        }
        source = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-io16-build-') as directory:
            for name, (old, new) in variants.items():
                self.assertEqual(source.count(old), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(old, new, 1))
                compile(path.read_text(), str(path), 'exec')
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', N71_IO16_BUILD_SCRIPT=str(path))
                p = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                    '-p', 'test_n71_io16_build.py', '-k', 'IO16BuildTests'],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
                text = p.stdout + p.stderr
                self.assertNotEqual(p.returncode, 0, name)
                self.assertIn('AssertionError', text, name + text); self.assertNotIn('ERROR:', text, name + text)
                print('N71_IO16_BUILD_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
