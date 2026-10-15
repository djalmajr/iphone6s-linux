"""Preserved PMD data stays explicit, private and bound to real build records."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_n71_pmd_runtime_build as fixture

ROOT = fixture.ROOT
SOURCE = ROOT / 'scripts/host/n71_pmd_source_reference.py'
PMD_SOURCE = ROOT / 'scripts/host/n71_pmd_runtime_build.py'
spec = importlib.util.spec_from_file_location('pmd_source_under_test', Path(os.environ.get('N71_PMD_REFERENCE_SCRIPT', SOURCE)))
SUBJECT = importlib.util.module_from_spec(spec); spec.loader.exec_module(SUBJECT)


class PmdSourceReference(unittest.TestCase):
    def setUp(self):
        data = fixture.PmdRuntime('test_current_records_select_pmd_without_changing_legacy_or_sources')
        data.setUp(); self.addCleanup(data.doCleanups); self.data = data; self.root = data.root
        hooks = [patch.object(fixture.SUBJECT, 'source_reference', SUBJECT), patch.dict(os.environ)]
        for hook in hooks:
            hook.start(); self.addCleanup(hook.stop)
        os.environ.pop(SUBJECT.ENV, None)
        self.runtime = self.root / 'runtime'; self.runtime.mkdir(mode=0o700)
        self.folder = self.runtime / 'frozen'; self.folder.mkdir(mode=0o700)
        self.source = self.folder / 'source'; self.source.mkdir(mode=0o700)
        compiled = data.read(fixture.MANIFEST)['inputs']; native = data.read(fixture.NATIVE)['inputs']
        self.records = dict(native) | dict(compiled)
        for name in sorted(self.records):
            target = self.source
            for part in Path(name).parts[:-1]:
                target = target / part; target.mkdir(mode=0o700, exist_ok=True)
            target = self.source / name; shutil.copyfile(self.root / name, target); target.chmod(0o600)
        self.metadata = {'format': 1, 'status': 'preserved_compiled_inputs', 'source_commit': SUBJECT.COMMIT,
            'source': 'source', 'inputs': self.records, 'compiled_input_count': 62, 'native_input_count': 69,
            'files': 78, 'bytes': 633894, 'compiled_manifest_sha256': SUBJECT.COMPILED_PIN,
            'no_code_executed_from_copy': True, 'no_phone_access': True}
        self.receipt = self.folder / 'receipt-private.json'; self.write(self.metadata)
        self.original = self.receipt.read_bytes()
        self.native_only = sorted(set(native) - set(compiled))[0]

    def write(self, data):
        self.receipt.write_text(json.dumps(data)); self.receipt.chmod(0o600)

    def resolve(self):
        with patch.dict(os.environ, {SUBJECT.ENV: str(self.receipt)}):
            return SUBJECT.resolve(self.root)

    def selected(self):
        try:
            with patch.dict(os.environ, {SUBJECT.ENV: str(self.receipt)}):
                return self.data.parent()
        except (ValueError, OSError) as error:
            self.fail('Preserved compiled PMD inputs refused: ' + str(error))

    def test_default_and_reference_are_read_only_and_preserve_environment(self):
        environment = dict(os.environ)
        self.assertEqual(SUBJECT.resolve(self.root), self.root)
        self.assertEqual(self.resolve(), self.source)
        with patch.object(subprocess, 'run', side_effect=AssertionError('No process allowed')):
            self.selected()
        self.assertEqual(self.receipt.read_bytes(), self.original)
        self.assertEqual(dict(os.environ), environment)

    def test_real_pmd_selection_uses_frozen_compiled_and_native_bytes(self):
        expected = self.data.parent()
        changed = {}
        for name in ('phone/kernel/n71-pcie-diagnostic.c', self.native_only):
            path = self.root / name; raw = path.read_bytes()
            changed[path] = bytes([raw[0] ^ 1]) + raw[1:]; path.write_bytes(changed[path])
        with self.assertRaises(ValueError): self.data.parent()
        self.assertEqual(self.selected(), expected)
        self.assertTrue(all(path.read_bytes() == raw for path, raw in changed.items()))
        self.assertEqual(self.receipt.read_bytes(), self.original)

    def test_schema_types_origin_and_budget_are_not_self_attestation(self):
        cases = [('format', True), ('status', 'accepted'), ('source_commit', 'f' * 40),
                 ('source', '../other'), ('files', 78.0), ('bytes', 633894.0),
                 ('compiled_input_count', 62.0), ('native_input_count', 69.0),
                 ('no_phone_access', False), ('no_code_executed_from_copy', False),
                 ('compiled_manifest_sha256', 'f' * 64)]
        for key, value in cases:
            with self.subTest(key=key):
                self.write(dict(self.metadata, **{key: value}))
                with self.assertRaises(ValueError): self.resolve()
        self.write(dict(self.metadata, extra=True))
        with self.assertRaises(ValueError): self.resolve()
        self.write(self.metadata); self.receipt.write_bytes(self.receipt.read_bytes() + b' ' * 65536)
        with self.assertRaises(ValueError): self.resolve()
        self.write(self.metadata)
        for value in ('', 'runtime/frozen/receipt-private.json', str(self.root / 'receipt-private.json')):
            with self.subTest(value=value), patch.dict(os.environ, {SUBJECT.ENV: value}), self.assertRaises(ValueError):
                SUBJECT.resolve(self.root)

    def test_consistently_forged_source_and_manifest_cannot_replace_compiled_inputs(self):
        name = 'phone/kernel/n71-pcie-diagnostic.c'; path = self.source / name
        raw = path.read_bytes(); path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        altered = json.loads(json.dumps(self.metadata))
        altered['inputs'][name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest(); self.write(altered)
        with self.assertRaises(ValueError): self.resolve()

    def test_private_modes_links_and_same_size_corruption_are_checked(self):
        path = self.source / 'phone/kernel/n71-pcie-diagnostic.c'; raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        with self.assertRaises(ValueError): self.resolve()
        path.write_bytes(raw); path.chmod(0o644)
        with self.assertRaises(ValueError): self.resolve()
        path.chmod(0o600); alias = self.folder / 'duplicate.c'; path.rename(alias); path.symlink_to(alias)
        with self.assertRaises(ValueError): self.resolve()
        path.unlink(); os.link(alias, path)
        with self.assertRaises(ValueError): self.resolve()
        path.unlink(); alias.rename(path)
        parent = path.parent; other = parent.with_name('alias-kernel'); parent.rename(other); parent.symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError): self.resolve()
        parent.unlink(); other.rename(parent)
        self.folder.chmod(0o755)
        with self.assertRaises(ValueError): self.resolve()
        self.folder.chmod(0o700)

    def test_public_build_proofs_still_come_from_current_project(self):
        self.selected()
        self.data.edit(fixture.KERNEL, ('build', 'full_image_linked'), False)
        with patch.dict(os.environ, {SUBJECT.ENV: str(self.receipt)}), self.assertRaises(ValueError):
            self.data.parent()


@unittest.skipIf(os.environ.get('N71_PMD_REFERENCE_SCRIPT') or os.environ.get('N71_PMD_RUNTIME_BUILD_SCRIPT'), 'Mutation child')
class PmdSourceMutations(unittest.TestCase):
    def test_reference_integrity_and_both_input_routes_fail_by_assertion(self):
        variants = [
            ('empty-selection', SOURCE, 'N71_PMD_REFERENCE_SCRIPT', 'if value is None:', 'if not value:', 'schema_types_origin_and_budget_are_not_self_attestation'),
            ('origin', SOURCE, 'N71_PMD_REFERENCE_SCRIPT', "data.get('source_commit') == COMMIT", 'True', 'schema_types_origin_and_budget_are_not_self_attestation'),
            ('count-type', SOURCE, 'N71_PMD_REFERENCE_SCRIPT', 'type(data.get(name)) is int', 'True', 'schema_types_origin_and_budget_are_not_self_attestation'),
            ('receipt-budget', SOURCE, 'N71_PMD_REFERENCE_SCRIPT', '0 < path.stat().st_size <= 65536', 'True', 'schema_types_origin_and_budget_are_not_self_attestation'),
            ('manifest-pin', SOURCE, 'N71_PMD_REFERENCE_SCRIPT', "hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == INPUTS_PIN", 'True', 'consistently_forged_source_and_manifest_cannot_replace_compiled_inputs'),
            ('private-file', SOURCE, 'N71_PMD_REFERENCE_SCRIPT', 'device_profile.protected(current)', 'pass', 'private_modes_links_and_same_size_corruption_are_checked'),
            ('source-hash', SOURCE, 'N71_PMD_REFERENCE_SCRIPT', "hashlib.sha256(current.read_bytes()).hexdigest() == record['sha256']", 'True', 'private_modes_links_and_same_size_corruption_are_checked'),
            ('compiled-route', PMD_SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT', 'source_file(source_root, name, row)', 'source_file(root, name, row)', 'real_pmd_selection_uses_frozen_compiled_and_native_bytes'),
            ('native-route', PMD_SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT', 'source_file(source_root, name, current)', 'source_file(root, name, current)', 'real_pmd_selection_uses_frozen_compiled_and_native_bytes'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-pmd-source-mutations-') as directory:
            for name, source, variable, before, after, method in variants:
                text = source.read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory) / (name + '.py'); path.write_text(body)
                env = dict(os.environ, **{variable: str(path)}, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT / 'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                    'test_n71_pmd_source_reference.PmdSourceReference.test_' + method], env=env,
                    capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name + result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('PMD_SOURCE_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
