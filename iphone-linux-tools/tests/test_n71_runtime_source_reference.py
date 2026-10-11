"""Production selection binds explicit private historical data, not new source."""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
import test_n71_driver_runtime_build as fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_runtime_source_reference as REFERENCE
import n71_driver_runtime_build as BUILD
SOURCE = ROOT / 'scripts/host/n71_runtime_source_reference.py'


class RuntimeSourceReferenceTests(unittest.TestCase):
    builder = BUILD
    subject = REFERENCE

    def setUp(self):
        case = fixture.RuntimeBuildTests('test_exact_selection_preserves_assignment_reg_on_and_ordered_wcc_without_writing')
        case.setUp(); self.addCleanup(case.doCleanups)
        self.root = case.root.resolve(); self.proof = case.proof; self.request = case.request
        environment = patch.dict(os.environ)
        environment.start(); self.addCleanup(environment.stop)
        os.environ.pop(REFERENCE.ENV, None)
        self.baseline = BUILD.select(self.root, self.request)
        (self.root / 'runtime').mkdir(mode=0o700)
        self.output = self.root / 'runtime/source-snapshot'
        self.source = self.output / 'source'; self.source.mkdir(parents=True, mode=0o700)
        self.output.chmod(0o700)
        for name in self.proof['inputs']:
            path = self.source / name; path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.root / name, path); path.chmod(0o600)
        recorded = self.source / REFERENCE.PROOF; recorded.parent.mkdir(parents=True)
        recorded.write_bytes((self.root / REFERENCE.PROOF).read_bytes()); recorded.chmod(0o600)
        self.receipt = {'format': 1, 'commit': 'a' * 40, 'archive_sha256': 'b' * 64,
            'proof_sha256': hashlib.sha256(recorded.read_bytes()).hexdigest(), 'source': 'source',
            'input_count': 69, 'input_hashes_verified': True, 'source_files': 70,
            'selected': self.baseline, 'phone_accessed': False}
        self.path = self.output / 'receipt.json'; self.save()

    def save(self):
        self.path.write_text(json.dumps(self.receipt)); self.path.chmod(0o600)

    def resolve(self):
        with patch.dict(os.environ, {REFERENCE.ENV: str(self.path)}):
            return self.subject.resolve(self.root, self.proof)

    def test_explicit_source_preserves_selection_and_current_bytes(self):
        # Mutation captured: ignoring the receipt validates changed working input instead of preserved bytes.
        path = self.root / 'phone/kernel/n71-i2c-power-diagnostic.c'
        path.write_bytes(path.read_bytes() + b'\n// current source evolved\n')
        current = path.read_bytes()
        with self.assertRaises(ValueError): self.builder.select(self.root, self.request)
        with patch.dict(os.environ, {REFERENCE.ENV: str(self.path)}):
            try:
                selected = self.builder.select(self.root, self.request)
            except ValueError as error:
                self.fail('Explicit preserved source refused: ' + str(error))
            self.assertEqual(selected, self.baseline)
        self.assertEqual(path.read_bytes(), current)
        self.assertEqual(self.resolve(), self.source)
        self.assertEqual(self.subject.resolve(self.root, self.proof), self.root)

    def test_input_tamper_or_missing_never_falls_back_to_current(self):
        # Mutation captured: treating an invalid historical snapshot as permission to use working files.
        path = self.source / 'phone/kernel/n71-i2c-power-diagnostic.c'
        original = path.read_bytes()
        for raw in (original + b'changed', None):
            if raw is None: path.unlink()
            else: path.write_bytes(raw)
            with patch.dict(os.environ, {REFERENCE.ENV: str(self.path)}), self.assertRaises(ValueError):
                BUILD.select(self.root, self.request)

    def test_receipt_proof_schema_and_source_name_are_bound(self):
        # Mutation captured: omitting proof equality or source-name scope accepts foreign provenance.
        original = dict(self.receipt)
        for key, value in [('proof_sha256', 'f' * 64), ('source', '../foreign'),
                           ('input_count', True), ('phone_accessed', True), ('commit', 'HEAD'),
                           ('format', True), ('input_hashes_verified', False)]:
            self.receipt = dict(original); self.receipt[key] = value; self.save()
            with self.subTest(key=key), self.assertRaises(ValueError): self.resolve()
        self.receipt = dict(original); self.receipt['extra'] = True; self.save()
        with self.assertRaises(ValueError): self.resolve()

    def test_private_paths_and_links_are_required(self):
        # Mutation captured: dropping the runtime scope permits a receipt from a different project.
        old = self.path
        self.path = self.root / 'outside.json'; self.save()
        with self.assertRaises(ValueError): self.resolve()
        self.path = old; self.path.chmod(0o644)
        with self.assertRaises(ValueError): self.resolve()
        self.path.chmod(0o600)
        renamed = self.output / 'real-source'; self.source.rename(renamed); self.source.symlink_to(renamed, target_is_directory=True)
        with self.assertRaises(ValueError): self.resolve()


class RuntimeSourceReferenceMutations(unittest.TestCase):
    def test_reference_mutations_fail_by_assertion(self):
        source = SOURCE.read_text()
        for name, before, after, method in [
            ('proof-binding', "receipt['proof_sha256'] == hashlib.sha256(expected).hexdigest()", 'True',
                'test_receipt_proof_schema_and_source_name_are_bound'),
            ('source-name', "receipt['source'] == 'source'", 'True',
                'test_receipt_proof_schema_and_source_name_are_bound'),
        ]:
            self.assertEqual(source.count(before), 1)
            subject = ModuleType('reference_mutant')
            exec(compile(ast.parse(source.replace(before, after, 1)), str(SOURCE), 'exec'), subject.__dict__)
            case = type('MutatedRuntimeReferenceTests', (RuntimeSourceReferenceTests,), {'subject': subject})
            result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
            self.assertEqual(result.errors, [], name)
            self.assertGreater(len(result.failures), 0, name)
            print('N71_SOURCE_REFERENCE_MUTATION_KILLED', name, 'AssertionError')
        path = ROOT / 'scripts/host/n71_driver_runtime_build.py'
        original = path.read_text(); before = 'root = source_reference.resolve(root, proof)'
        self.assertEqual(original.count(before), 1)
        builder = ModuleType('source_selection_mutant')
        exec(compile(ast.parse(original.replace(before, 'root = root', 1)), str(path), 'exec'), builder.__dict__)
        case = type('MutatedSourceSelectionTests', (RuntimeSourceReferenceTests,), {'builder': builder})
        result = unittest.TextTestRunner(stream=io.StringIO()).run(case('test_explicit_source_preserves_selection_and_current_bytes'))
        self.assertEqual(result.errors, [])
        self.assertGreater(len(result.failures), 0)
        print('N71_SOURCE_REFERENCE_MUTATION_KILLED', 'missing-input-resolution', 'AssertionError')


if __name__ == '__main__':
    unittest.main()
