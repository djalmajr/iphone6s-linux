"""Select only qualified PREF64 bytes and preserve every older rollback path."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import test_n71_io16_build as io16

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71_resource_build.py'
SPEC = importlib.util.spec_from_file_location('pref64_build_under_test', os.environ.get('N71_PREF64_BUILD_SCRIPT', SOURCE))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
EVIDENCE = ROOT / 'docs/evidence/n71-pci-pref64-build.json'


class Pref64BuildTests(unittest.TestCase):
    def setUp(self):
        io16.IO16BuildTests.setUp(self)
        for name in ('n71-pci-io16-build.json', 'n71-pci-pref64-policy.json'):
            (self.folder / name).write_bytes((ROOT / 'docs/evidence' / name).read_bytes())
        self.evidence = json.loads(EVIDENCE.read_text())
        self.digest = self.evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']

    def select(self, evidence=None, digest=None):
        (self.folder / EVIDENCE.name).write_text(json.dumps(self.evidence if evidence is None else evidence))
        return BUILD.select(self.root, self.previous, release=self.release,
                            pcie_sha256=self.digest if digest is None else digest)

    def test_known_bytes_require_four_reports_and_preserve_reg_on(self):
        records = self.select()
        for key in ('assignment_readback', 'assignment_optional_windows', 'assignment_io16_upper', 'assignment_pref64_disable'):
            self.assertIs(records[0].get(key), True)
        self.assertEqual(records[0]['sha256'], self.digest); self.assertEqual(records[1], self.previous[1])
        self.assertEqual(io16.fixture.RESOURCE.selected_records(ROOT, release=self.release, pcie_sha256=self.digest), records)
        with self.assertRaises(ValueError):
            self.select(digest='0' * 64)

    def test_older_hashes_keep_their_original_contracts(self):
        for name, optional, upper in (('n71-pci-resource-readback.json', False, False),
                                     ('n71-pci-optional-build.json', True, False), ('n71-pci-io16-build.json', True, True)):
            digest = json.loads((self.folder / name).read_text())['real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']
            records = self.select(digest=digest)
            self.assertIs(records[0].get('assignment_readback'), True)
            self.assertEqual(records[0].get('assignment_optional_windows', False), optional)
            self.assertEqual(records[0].get('assignment_io16_upper', False), upper)
            self.assertNotIn('assignment_pref64_disable', records[0]); self.assertEqual(records[1], self.previous[1])

    def test_pref64_contract_and_compilation_require_exact_booleans(self):
        for field in BUILD.PREF64_FLAGS:
            for value in (False, 1):
                bad = copy.deepcopy(self.evidence); bad['pref64_contract'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.select(bad)
        for field in ('native_policy_adapter_qualified', 'host_contract_qualified'):
            for value in (False, 1):
                bad = copy.deepcopy(self.evidence); bad[field] = value
                with self.assertRaises(ValueError):
                    self.select(bad)
        for value in (False, 1):
            bad = copy.deepcopy(self.evidence); bad['real_module_build']['pref64_disable_report_compiled'] = value
            with self.assertRaises(ValueError):
                self.select(bad)

    test_abi_bytes_reg_on_and_proof_scope_remain_bound = io16.IO16BuildTests.test_base_abi_bytes_reg_on_and_proof_scope_remain_bound

    def test_io16_and_policy_bases_cannot_change_or_be_missing_or_linked(self):
        for field in ('base_io16_evidence_sha256', 'pref64_policy_evidence_sha256'):
            bad = copy.deepcopy(self.evidence); bad[field] = '0' * 64
            with self.assertRaises(ValueError):
                self.select(bad)
        for name in ('n71-pci-io16-build.json', 'n71-pci-pref64-policy.json'):
            path = self.folder / name; raw = path.read_bytes(); path.unlink()
            with self.assertRaises(ValueError):
                self.select()
            target = self.folder / ('saved-' + name); target.write_bytes(raw); path.symlink_to(target)
            with self.assertRaises(ValueError):
                self.select()
            path.unlink(); path.write_bytes(raw)

    def test_missing_or_linked_pref64_evidence_never_selects_new_bytes(self):
        with self.assertRaises(ValueError):
            BUILD.select(self.root, self.previous, release=self.release, pcie_sha256=self.digest)
        target = self.folder / 'saved-pref64.json'; target.write_bytes(EVIDENCE.read_bytes())
        (self.folder / EVIDENCE.name).symlink_to(target)
        with self.assertRaises(ValueError):
            BUILD.select(self.root, self.previous, release=self.release, pcie_sha256=self.digest)


class Pref64BuildMutationsTests(unittest.TestCase):
    def test_pref64_selection_mutations_fail_by_assertion(self):
        variants = {
            'io16-base-binding': ("candidate.get('base_io16_evidence_sha256') == hashlib.sha256(base.read_bytes()).hexdigest()", 'True'),
            'policy-binding': ("candidate.get('pref64_policy_evidence_sha256') == hashlib.sha256(policy.read_bytes()).hexdigest()", 'True'),
            'policy-symlink': ("policy.is_file() and not policy.is_symlink()", 'policy.is_file()'),
            'truthy-pref-contract': ('pref64_contract.get(name) is True', 'bool(pref64_contract.get(name))'),
            'compiled-pref-report': ("build.get('pref64_disable_report_compiled') is True", 'True'),
            'required-pref-record': ("records[0]['assignment_pref64_disable'] = True", "records[0]['assignment_pref64_disable'] = False"),
            'pref-selection': ('pref64 = candidate is not None', 'pref64 = False'),
            'inherited-io16-contract': ('io16 = pref64', 'io16 = False'),
        }
        source = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-pref64-selection-') as directory:
            for name, (before, after) in variants.items():
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', N71_PREF64_BUILD_SCRIPT=str(path))
                p = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                    '-p', 'test_n71_pref64_build.py', '-k', 'Pref64BuildTests'],
                                   cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                output = p.stdout + p.stderr
                self.assertNotEqual(p.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output); self.assertNotIn('ERROR:', output, name + output)
                print('N71_PREF64_BUILD_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
