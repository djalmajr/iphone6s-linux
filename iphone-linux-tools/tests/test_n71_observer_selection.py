"""Real PMD base, frozen legacy inputs and current observer data; no device access."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_n71_pmd_source_reference as fixture

ROOT = fixture.ROOT
SOURCE = ROOT / 'scripts/host/n71_pmd_observer_build.py'
BASE_SOURCE = ROOT / 'scripts/host/n71_pmd_runtime_build.py'
spec = importlib.util.spec_from_file_location('observer_selection_under_test', Path(os.environ.get('N71_OBSERVER_SELECTION_SCRIPT', SOURCE)))
SUBJECT = importlib.util.module_from_spec(spec); spec.loader.exec_module(SUBJECT)
BUILD = 'n71-pmd-observer-build.json'
MANIFEST = 'n71-pmd-observer-inputs.json'


class ObserverSelection(unittest.TestCase):
    def setUp(self):
        case = fixture.PmdSourceReference('test_default_and_reference_are_read_only_and_preserve_environment')
        case.setUp(); self.addCleanup(case.doCleanups); self.case = case; self.data = case.data
        self.root = case.root; self.folder = self.data.folder
        hook = patch.dict(sys.modules, {'n71_pmd_observer_build': SUBJECT}); hook.start(); self.addCleanup(hook.stop)
        os.environ.pop(SUBJECT.ENV, None)
        os.environ[fixture.SUBJECT.ENV] = str(case.receipt)
        for name in (BUILD, MANIFEST):
            (self.folder / name).write_bytes((ROOT / 'docs/evidence' / name).read_bytes())
        for name in self.read(MANIFEST)['inputs']:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
        self.original = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.previous = self.data.parent()
        self.old_records = self.data.read(fixture.fixture.DIAGNOSTICS)['modules']
        self.context = {'release': fixture.fixture.SUBJECT.RELEASE,
            'kernel_hashes': self.data.read(fixture.fixture.DIAGNOSTICS)['kernel_hashes'],
            'source_bundle': self.data.read(fixture.fixture.DIAGNOSTICS)['source_bundle']}

    def read(self, name):
        return json.loads((self.folder / name).read_text())

    def write(self, name, data):
        (self.folder / name).write_text(json.dumps(data))

    def restore(self):
        for path, raw in self.original.items():
            if path.is_symlink(): path.unlink()
            path.write_bytes(raw)

    def selected(self):
        try:
            with patch.dict(os.environ, {SUBJECT.ENV: SUBJECT.VARIANT}):
                return self.data.parent()
        except (ValueError, OSError) as error:
            self.fail('Compiled observers refused: ' + str(error))

    def refuse(self):
        with patch.dict(os.environ, {SUBJECT.ENV: SUBJECT.VARIANT}), self.assertRaises(ValueError):
            self.data.parent()

    def test_default_ignores_observer_files_and_invalid_opt_in_never_falls_back(self):
        base = fixture.fixture.SUBJECT
        with patch.object(base, 'evidence', side_effect=AssertionError('Default must not read observer records')):
            self.assertIs(SUBJECT.select(self.root, self.old_records, **self.context), self.old_records)
        for value in ('', 'observers', 'pmd-observers-v2'):
            with patch.dict(os.environ, {SUBJECT.ENV: value}), self.assertRaises(ValueError):
                SUBJECT.select(self.root, self.old_records, **self.context)
        (self.folder / BUILD).unlink()
        self.assertEqual(self.data.parent(), self.previous)

    def test_real_base_selects_new_hash_and_resource_pair_without_mutation(self):
        proof = self.read(BUILD); expected = proof['modules']['n71_pcie_diagnostic']
        selected = self.selected()
        self.assertEqual(selected['module_sha256'], expected['sha256'])
        self.assertEqual(selected['module_bytes'], expected['bytes'])
        self.assertNotEqual(selected['module_sha256'], self.previous['module_sha256'])
        self.assertEqual(selected['baseline_sha256'], self.previous['baseline_sha256'])
        with patch.dict(os.environ, {SUBJECT.ENV: SUBJECT.VARIANT}):
            rows = self.data.records(pcie_sha256=expected['sha256'])
            self.assertEqual(rows[0]['sha256'], expected['sha256'])
            self.assertEqual(rows[1]['sha256'], proof['modules']['n71_wlan_power_diagnostic']['sha256'])
            with self.assertRaises(ValueError): self.data.records(pcie_sha256=self.previous['module_sha256'])
        self.assertEqual({p: p.read_bytes() for p in self.original}, self.original)
        self.assertEqual(self.data.parent(), self.previous)

    def test_kernel_source_and_native_gate_bindings_are_required(self):
        for key, value in (('kernel_hashes', dict(self.context['kernel_hashes'], **{'.config': 'f' * 64})),
                ('source_bundle', dict(self.context['source_bundle'], stage='baseline')),
                ('source_head', 'f' * 40), ('module_bytes', 269312.0), ('w1_werror', False),
                ('base_kernel_source_and_outputs_preserved', False), ('loaded', True), ('wifi_verified', True)):
            with self.subTest(key=key):
                data = self.read(BUILD); data[key] = value; self.write(BUILD, data)
                self.refuse(); self.restore()
        data = self.read(BUILD); data['arm64_native']['cases'] = 324.0; self.write(BUILD, data)
        self.refuse()

    def test_consistent_forged_module_identity_is_not_a_new_compiled_catalog(self):
        data = self.read(BUILD); data['modules']['n71_pcie_diagnostic']['sha256'] = 'f' * 64
        self.write(BUILD, data); self.refuse()

    def test_consistent_forged_source_manifest_is_not_a_new_compiled_input(self):
        name = 'phone/kernel/n71-dma-observe.h'; path = self.root / name; raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        data = self.read(MANIFEST); data['inputs'][name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.write(MANIFEST, data); self.refuse()

    def test_source_corruption_alias_and_missing_record_are_refused(self):
        path = self.root / 'phone/kernel/n71-dma-observe.h'; raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:]); self.refuse(); self.restore()
        alias = self.root / 'alias.h'; alias.write_bytes(raw); path.unlink(); path.symlink_to(alias)
        self.refuse(); self.restore()
        (self.folder / BUILD).unlink(); self.refuse()

    def test_legacy_base_qualification_and_explicit_frozen_reference_remain_required(self):
        with patch.dict(os.environ):
            os.environ.pop(fixture.SUBJECT.ENV)
            self.refuse()
        self.data.edit(fixture.fixture.KERNEL, ('build', 'exit_code'), False)
        self.refuse()


@unittest.skipIf(os.environ.get('N71_OBSERVER_SELECTION_SCRIPT') or os.environ.get('N71_PMD_RUNTIME_BUILD_SCRIPT'), 'Mutation child')
class ObserverSelectionMutations(unittest.TestCase):
    def test_new_selection_guards_and_actual_base_route_fail_by_assertion(self):
        variants = [
            ('opt-in', SOURCE, 'N71_OBSERVER_SELECTION_SCRIPT', 'if value != VARIANT:', 'if False:', 'default_ignores_observer_files_and_invalid_opt_in_never_falls_back'),
            ('kernel', SOURCE, 'N71_OBSERVER_SELECTION_SCRIPT', "proof.get('kernel_hashes') == kernel_hashes", 'True', 'kernel_source_and_native_gate_bindings_are_required'),
            ('source-bundle', SOURCE, 'N71_OBSERVER_SELECTION_SCRIPT', "proof.get('source_bundle') == source_bundle", 'True', 'kernel_source_and_native_gate_bindings_are_required'),
            ('module-catalog', SOURCE, 'N71_OBSERVER_SELECTION_SCRIPT', 'pmd.digest(modules) == MODULES_PIN', 'True', 'consistent_forged_module_identity_is_not_a_new_compiled_catalog'),
            ('source-manifest', SOURCE, 'N71_OBSERVER_SELECTION_SCRIPT', 'pmd.digest(inputs) == INPUTS_PIN', 'True', 'consistent_forged_source_manifest_is_not_a_new_compiled_input'),
            ('actual-source', SOURCE, 'N71_OBSERVER_SELECTION_SCRIPT', 'pmd.source_file(root, name, row)', 'pass', 'source_corruption_alias_and_missing_record_are_refused'),
            ('native-type', SOURCE, 'N71_OBSERVER_SELECTION_SCRIPT', 'type(gates.get(name)) is int', 'True', 'kernel_source_and_native_gate_bindings_are_required'),
            ('base-route', BASE_SOURCE, 'N71_PMD_RUNTIME_BUILD_SCRIPT',
             'records = observers.select(root, records, release=release, kernel_hashes=hashes, source_bundle=selected)',
             'records = records', 'real_base_selects_new_hash_and_resource_pair_without_mutation'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-observer-selection-mutations-') as directory:
            for name, source, variable, before, after, method in variants:
                text = source.read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory) / (name + '.py'); path.write_text(body)
                env = dict(os.environ, **{variable: str(path)}, PYTHONPATH=str(ROOT / 'tests'), PYTHONDONTWRITEBYTECODE='1')
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                    'test_n71_observer_selection.ObserverSelection.test_' + method], env=env,
                    capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name + result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('OBSERVER_SELECTION_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
