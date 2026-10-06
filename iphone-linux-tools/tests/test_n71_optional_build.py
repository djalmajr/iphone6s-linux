"""Select the optional-range build while retaining both older rollback records."""
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
SPEC = importlib.util.spec_from_file_location('optional_build_under_test', os.environ.get('N71_OPTIONAL_BUILD_SCRIPT', SOURCE))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
EVIDENCE = ROOT / 'docs/evidence/n71-pci-optional-build.json'


class OptionalBuildTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name); self.folder = self.root / 'docs/evidence'; self.folder.mkdir(parents=True)
        for name in ('n71-pci-resource-assignment.json', 'n71-pci-resource-readback.json'):
            (self.folder / name).write_bytes((ROOT / 'docs/evidence' / name).read_bytes())
        self.evidence = json.loads(EVIDENCE.read_text()); self.release = self.evidence['real_module_build']['release']
        self.previous = fixture.RESOURCE.selected_records(ROOT, release=self.release)
        self.digest = self.evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']
        self.old_digest = json.loads((self.folder / 'n71-pci-resource-readback.json').read_text())['real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']

    def select(self, evidence=None, digest=None):
        (self.folder / EVIDENCE.name).write_text(json.dumps(self.evidence if evidence is None else evidence))
        return BUILD.select(self.root, self.previous, release=self.release,
                            pcie_sha256=self.digest if digest is None else digest)

    def test_known_build_selects_both_required_reports_and_preserves_reg_on(self):
        records = self.select()
        self.assertIs(records[0].get('assignment_readback'), True)
        self.assertIs(records[0].get('assignment_optional_windows'), True)
        self.assertEqual(records[0]['sha256'], self.digest); self.assertEqual(records[1], self.previous[1])
        self.assertEqual(fixture.RESOURCE.selected_records(ROOT, release=self.release, pcie_sha256=self.digest), records)
        with self.assertRaises(ValueError):
            self.select(digest='0' * 64)

    def test_older_profiles_keep_their_original_contracts(self):
        records = self.select(digest=self.old_digest)
        self.assertIs(records[0].get('assignment_readback'), True)
        self.assertNotIn('assignment_optional_windows', records[0])
        self.assertEqual(fixture.RESOURCE.selected_records(ROOT, release=self.release,
                         pcie_sha256=self.previous[0]['sha256']), self.previous)
        self.assertEqual(fixture.RESOURCE.selected_records(ROOT, release=self.release), self.previous)

    def test_optional_flags_and_qualification_are_exact_booleans(self):
        for field in BUILD.OPTIONAL_FLAGS:
            for value in (False, 1, 'true'):
                bad = copy.deepcopy(self.evidence); bad['optional_contract'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.select(bad)
        for field in ('native_policy_adapter_qualified', 'host_contract_qualified'):
            for value in (False, 1):
                bad = copy.deepcopy(self.evidence); bad[field] = value
                with self.assertRaises(ValueError):
                    self.select(bad)
        for field in ('optional_windows_report_compiled', 'patched_source_files_verified'):
            for value in (False, 1):
                bad = copy.deepcopy(self.evidence); bad['real_module_build'][field] = value
                with self.assertRaises(ValueError):
                    self.select(bad)

    def test_base_bytes_abi_scope_and_reg_on_refuse_changed_records(self):
        bad = copy.deepcopy(self.evidence); bad['base_readback_evidence_sha256'] = '0' * 64
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


class OptionalBuildMutationTests(unittest.TestCase):
    def test_optional_guards_fail_by_assertion(self):
        variants = {
            'readback-base-lost': ("candidate.get('base_readback_evidence_sha256') == hashlib.sha256(original.read_bytes()).hexdigest()", 'True'),
            'truthy-optional-contract': ('optional_contract.get(name) is True', 'bool(optional_contract.get(name))'),
            'native-proof-lost': ("evidence.get('native_policy_adapter_qualified') is True", 'True'),
            'host-proof-lost': ("evidence.get('host_contract_qualified') is True", 'True'),
            'truthy-report-build': ("build.get('optional_windows_report_compiled') is True", "bool(build.get('optional_windows_report_compiled'))"),
            'patched-source-proof-lost': ("build.get('patched_source_files_verified') is True", 'True'),
            'required-optional-record-lost': ("records[0]['assignment_optional_windows'] = True", "records[0]['assignment_optional_windows'] = False"),
        }
        source = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-optional-build-') as directory:
            for name, (old, new) in variants.items():
                self.assertEqual(source.count(old), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(old, new, 1))
                compile(path.read_text(), str(path), 'exec')
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', N71_OPTIONAL_BUILD_SCRIPT=str(path))
                p = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                    '-p', 'test_n71_optional_build.py', '-k', 'OptionalBuildTests'],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
                text = p.stdout + p.stderr
                self.assertNotEqual(p.returncode, 0, name)
                self.assertIn('AssertionError', text, name + text); self.assertNotIn('ERROR:', text, name + text)
                print('N71_OPTIONAL_BUILD_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
