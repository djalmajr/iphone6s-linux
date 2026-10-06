"""Bind the unsized lifecycle module to its native qualification and rollback."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import test_n71_pref64_build as pref64

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71_resource_build.py'
SPEC = importlib.util.spec_from_file_location('unsized_build_under_test',
    os.environ.get('N71_PREF64_UNSIZED_BUILD_SCRIPT', SOURCE))
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)
EVIDENCE = ROOT / 'docs/evidence/n71-pci-pref64-unsized-build.json'


class UnsizedBuildTests(unittest.TestCase):
    def setUp(self):
        pref64.Pref64BuildTests.setUp(self)
        for name in ('n71-pci-pref64-build.json', 'n71-pci-pref64-unsized-adapter.json'):
            (self.folder / name).write_bytes((ROOT / 'docs/evidence' / name).read_bytes())
        self.evidence = json.loads(EVIDENCE.read_text())
        self.digest = self.evidence['real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']

    def select(self, evidence=None, digest=None):
        (self.folder / EVIDENCE.name).write_text(json.dumps(self.evidence if evidence is None else evidence))
        return BUILD.select(self.root, self.previous, release=self.release,
                            pcie_sha256=self.digest if digest is None else digest)

    def test_known_bytes_keep_four_reports_and_preserve_reg_on(self):
        try:
            records = self.select()
        except ValueError as error:
            self.fail('Qualified unsized artifact refused: ' + str(error))
        for key in ('assignment_readback', 'assignment_optional_windows',
                    'assignment_io16_upper', 'assignment_pref64_disable'):
            self.assertIs(records[0].get(key), True)
        self.assertEqual(records[0]['sha256'], self.digest)
        self.assertEqual(records[1], self.previous[1])
        self.assertEqual(pref64.io16.fixture.RESOURCE.selected_records(
            ROOT, release=self.release, pcie_sha256=self.digest), records)
        with self.assertRaises(ValueError):
            self.select(digest='0' * 64)

    def test_all_older_hashes_keep_their_original_contracts(self):
        for name, optional, upper, typed in (
            ('n71-pci-resource-readback.json', False, False, False),
            ('n71-pci-optional-build.json', True, False, False),
            ('n71-pci-io16-build.json', True, True, False),
            ('n71-pci-pref64-build.json', True, True, True),
        ):
            digest = json.loads((self.folder / name).read_text())[
                'real_module_build']['modules']['n71-pcie-diagnostic.ko']['sha256']
            records = self.select(digest=digest)
            self.assertEqual(records[0].get('assignment_optional_windows', False), optional)
            self.assertEqual(records[0].get('assignment_io16_upper', False), upper)
            self.assertEqual(records[0].get('assignment_pref64_disable', False), typed)
            self.assertEqual(records[1], self.previous[1])

    def test_unsized_qualification_and_contract_require_exact_booleans(self):
        for value in (False, 1):
            bad = copy.deepcopy(self.evidence)
            bad['pref64_unsized_adapter_qualified'] = value
            with self.assertRaises(ValueError):
                self.select(bad)
        for field in BUILD.UNSIZED_FLAGS:
            for value in (False, 1):
                bad = copy.deepcopy(self.evidence)
                bad['pref64_unsized_contract'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.select(bad)

    def test_unsized_base_and_adapter_cannot_change_or_be_missing_or_linked(self):
        for field in ('base_pref64_evidence_sha256', 'unsized_adapter_evidence_sha256'):
            bad = copy.deepcopy(self.evidence)
            bad[field] = '0' * 64
            with self.assertRaises(ValueError):
                self.select(bad)
        for name in ('n71-pci-pref64-build.json', 'n71-pci-pref64-unsized-adapter.json'):
            path = self.folder / name
            raw = path.read_bytes()
            path.unlink()
            with self.assertRaises(ValueError):
                self.select()
            target = self.folder / ('saved-' + name)
            target.write_bytes(raw)
            path.symlink_to(target)
            with self.assertRaises(ValueError):
                self.select()
            path.unlink()
            path.write_bytes(raw)

    def test_missing_or_linked_unsized_evidence_never_selects_new_bytes(self):
        with self.assertRaises(ValueError):
            BUILD.select(self.root, self.previous, release=self.release, pcie_sha256=self.digest)
        target = self.folder / 'saved-unsized.json'
        target.write_bytes(EVIDENCE.read_bytes())
        (self.folder / EVIDENCE.name).symlink_to(target)
        with self.assertRaises(ValueError):
            BUILD.select(self.root, self.previous, release=self.release, pcie_sha256=self.digest)

    test_pref64_contract_and_compilation_require_exact_booleans = (
        pref64.Pref64BuildTests.test_pref64_contract_and_compilation_require_exact_booleans)
    test_abi_bytes_reg_on_and_proof_scope_remain_bound = (
        pref64.Pref64BuildTests.test_abi_bytes_reg_on_and_proof_scope_remain_bound)
    test_io16_and_policy_bases_cannot_change_or_be_missing_or_linked = (
        pref64.Pref64BuildTests.test_io16_and_policy_bases_cannot_change_or_be_missing_or_linked)


class UnsizedBuildMutationsTests(unittest.TestCase):
    def test_unsized_selection_mutations_fail_by_assertion(self):
        variants = {
            'base-binding': ('candidate.get(field) == hashlib.sha256(bound.read_bytes()).hexdigest()', 'True'),
            'base-symlink': ('bound.is_file() and not bound.is_symlink()', 'bound.is_file()'),
            'truthy-qualification': ("candidate.get('pref64_unsized_adapter_qualified') is True",
                                     "bool(candidate.get('pref64_unsized_adapter_qualified'))"),
            'truthy-contract': ("candidate.get('pref64_unsized_contract', {}).get(name) is True",
                                "bool(candidate.get('pref64_unsized_contract', {}).get(name))"),
            'unsized-check-lost': ("request.get('unsized', False)", 'False'),
            'unsized-selection-lost': ("'filename': 'n71-pci-pref64-unsized-build.json'",
                                       "'filename': 'missing-unsized-build.json'"),
        }
        source = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-unsized-selection-') as directory:
            for name, (before, after) in variants.items():
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py')
                path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                   N71_PREF64_UNSIZED_BUILD_SCRIPT=str(path))
                p = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                    '-p', 'test_n71_pref64_unsized_build.py', '-k', 'UnsizedBuildTests'],
                    cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                output = p.stdout + p.stderr
                self.assertNotEqual(p.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_PREF64_UNSIZED_BUILD_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
