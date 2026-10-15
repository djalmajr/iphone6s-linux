"""PMD WCC build binding and POSIX effects with synthetic kernel tools."""
import copy
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_iommu_build
import test_n71_driver_modules as shell
import test_n71_pmd_runtime_build as pmd_fixture


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


BUILD_SOURCE = ROOT / 'scripts/host/n71_pmd_wifi_build.py'
MODULE_SOURCE = ROOT / 'scripts/host/n71_driver_modules.py'
BUILD = load('pmd_wifi_under_test', Path(os.environ.get('N71_PMD_WIFI_BUILD_SCRIPT', BUILD_SOURCE)))
MODULES = load('pmd_modules_under_test', Path(os.environ.get('N71_PMD_DRIVER_MODULES_SCRIPT', MODULE_SOURCE)))
RELEASE = n71_iommu_build.PMD_RELEASE
PROOF = 'n71-pmd-wifi-modules-qualified.json'


class PmdDriverModules(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='n71-pmd-wcc-'); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve(); self.folder = self.root / 'docs/evidence'
        self.folder.mkdir(parents=True)
        names = [PROOF, 'kernel-n71-pmd-build.json', 'n71-pmd-diagnostics-build.json',
                 'n71-pmd-diagnostic-inputs.json', 'n71-pmd-caller-reuse.json', 'n71-brcmfmac-caller-qualified.json']
        for name in names: shutil.copyfile(ROOT / 'docs/evidence' / name, self.folder / name)
        source_names = set(self.read(PROOF)['input_qualification']['inputs'])
        for name in ('n71-pmd-diagnostic-inputs.json', 'n71-brcmfmac-caller-qualified.json'):
            source_names.update(self.read(name)['inputs'])
        for name in source_names:
            target = self.root / name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(pmd_fixture.compiled_source(name))
        self.original = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        modules = patch.dict(sys.modules, {'n71_pmd_wifi_build': BUILD})
        modules.start(); self.addCleanup(modules.stop)

    def read(self, name):
        return json.loads((self.folder / name).read_text())

    def restore(self):
        for path, raw in self.original.items():
            if path.is_symlink(): path.unlink()
            path.write_bytes(raw)

    def edit(self, keys, value):
        proof = self.read(PROOF); target = proof
        for key in keys[:-1]: target = target[key]
        target[keys[-1]] = value
        (self.folder / PROOF).write_text(json.dumps(proof))

    def accepted(self, function, *args, **kwargs):
        try: return function(*args, **kwargs)
        except (ValueError, KeyError, OSError) as error: self.fail('Valid PMD WCC facts refused: ' + str(error))

    def qualified(self):
        return MODULES.qualified(self.root, release=RELEASE)

    def shell_case(self):
        case = shell.DriverModuleTests('test_real_shell_loads_in_order_and_unloads_normally_in_reverse')
        case.subject = MODULES; case.setUp(); self.addCleanup(case.doCleanups)
        # The inherited tools use synthetic bytes, names and dependencies only.
        for record in case.records: record['vermagic'] = RELEASE + ' SMP preempt mod_unload aarch64'
        (case.tools / 'uname').write_text('#!/bin/sh\nprintf "%s\\n" "' + RELEASE + '"\n')
        operation = case.operation
        case.operation = lambda action, name, index: operation(action, name, index) | {'release': RELEASE}
        return case

    def test_real_build_selects_five_pmd_modules_and_preserves_default(self):
        # Mutation killed: remove the explicit PMD qualified-build route.
        previous = MODULES.qualified(ROOT)
        records = self.accepted(self.qualified)
        self.assertEqual([r['name'] for r in records], list(MODULES.NAMES))
        self.assertEqual(sum(r['bytes'] for r in records), 1211368)
        self.assertEqual(MODULES.selected_release(records), RELEASE)
        self.assertEqual(MODULES.qualified(ROOT), previous)
        self.assertEqual({p: p.read_bytes() for p in self.original}, self.original)
        with self.assertRaises(ValueError): MODULES.qualified(self.root, release='unrecorded')

    def test_kernel_audit_inputs_imports_alias_and_abi_are_bound(self):
        # Mutations killed: drop kernel-baseline coupling, import/alias proof or compiled ABI.
        path = BUILD.PATHS[3]
        cases = [(('qualified',), False), (('kernel_release',), shell.MODULES.RELEASE),
                 (('baseline', 'kernel_sha256', '.config'), 'f' * 64),
                 (('all_imports_resolved',), False), (('werror_modpost_passed',), False),
                 (('modules', path, 'imports_verified'), False),
                 (('modules', path, 'endpoint_pci_alias_verified'), False),
                 (('modules', path, 'vermagic'), shell.MODULES.RELEASE + ' SMP preempt mod_unload aarch64'),
                 (('irq_correction', 'applied_to_package_copy_only'), False),
                 (('variant_config_changes', 'CONFIG_BRCMFMAC_PCIE'), ['n', 'n'])]
        for keys, value in cases:
            self.restore(); self.edit(keys, value)
            with self.subTest(keys=keys), self.assertRaises(ValueError): self.qualified()

    def test_compiled_input_pin_and_actual_patch_bytes_are_required(self):
        # Mutations killed: trust a rewritten input manifest or ignore changed source bytes.
        name = 'phone/kernel/patches/0008-brcmfmac-msi-error.patch'
        path = self.root / name; raw = path.read_bytes(); path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        with self.assertRaises(ValueError): self.qualified()
        self.edit(('input_qualification', 'inputs', name),
                  {'bytes': len(raw), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        self.edit(('irq_correction', 'patch_sha256'), hashlib.sha256(path.read_bytes()).hexdigest())
        with self.assertRaises(ValueError): self.qualified()

    def test_unknown_and_mixed_manifests_are_refused_before_observation(self):
        # Mutations killed: allow an entirely unknown ABI or a different ABI in later rows.
        records = self.accepted(self.qualified)
        for index, version in [(None, 'unknown'), (1, shell.MODULES.RELEASE)]:
            changed = copy.deepcopy(records)
            for row in changed if index is None else [changed[index]]:
                row['vermagic'] = version + ' SMP preempt mod_unload aarch64'
            with self.subTest(index=index), self.assertRaises(ValueError): MODULES.getter(changed, shell.DIRECTORY)

    def test_posix_full_load_and_reverse_cleanup_accept_only_the_selected_abi(self):
        # Mutations killed: parse PMD as legacy, or generate the legacy uname guard for PMD.
        case = self.shell_case()
        self.accepted(case.test_real_shell_loads_in_order_and_unloads_normally_in_reverse)

    def test_crossed_operation_or_live_kernel_refuses_before_any_receipt_or_effect(self):
        # Mutations killed: omit operation ABI agreement or the shell's live uname recheck.
        case = self.shell_case()
        request = self.accepted(case.operation, 'load', 'rfkill', 0)
        crossed = dict(request, release=shell.MODULES.RELEASE)
        with self.assertRaises(ValueError): MODULES.command(case.records, crossed)
        command = self.accepted(MODULES.command, case.records, request)
        (case.tools / 'uname').write_text('#!/bin/sh\nprintf "%s\\n" "' + shell.MODULES.RELEASE + '"\n')
        process = case.run_shell(command)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse(any(case.target.glob('*receipt-private.log')))
        self.assertFalse((case.root / 'effects').exists())
        self.assertFalse((case.modules / 'rfkill').exists())


@unittest.skipIf(any(os.environ.get(name) for name in ('N71_PMD_WIFI_BUILD_SCRIPT',
                'N71_PMD_DRIVER_MODULES_SCRIPT')), 'Mutation child selects subject')
class PmdDriverMutations(unittest.TestCase):
    def test_weakened_pmd_selection_and_effect_guards_fail_by_assertion(self):
        variants = [
            ('route', MODULE_SOURCE, 'N71_PMD_DRIVER_MODULES_SCRIPT', 'if release == n71_iommu_build.PMD_RELEASE:', 'if False:', 'real_build_selects_five_pmd_modules_and_preserves_default'),
            ('baseline', BUILD_SOURCE, 'N71_PMD_WIFI_BUILD_SCRIPT', "pmd.digest(proof.get('baseline')) == pmd.digest(baseline)", 'True', 'kernel_audit_inputs_imports_alias_and_abi_are_bound'),
            ('imports', BUILD_SOURCE, 'N71_PMD_WIFI_BUILD_SCRIPT', "row.get('imports_verified') is True", 'True', 'kernel_audit_inputs_imports_alias_and_abi_are_bound'),
            ('alias', BUILD_SOURCE, 'N71_PMD_WIFI_BUILD_SCRIPT', "name != 'brcmfmac' or row.get('endpoint_pci_alias_verified') is True", 'True', 'kernel_audit_inputs_imports_alias_and_abi_are_bound'),
            ('inputs', BUILD_SOURCE, 'N71_PMD_WIFI_BUILD_SCRIPT', 'pmd.digest(inputs) == INPUTS_PIN', 'True', 'compiled_input_pin_and_actual_patch_bytes_are_required'),
            ('known-abi', MODULE_SOURCE, 'N71_PMD_DRIVER_MODULES_SCRIPT', 'version in (', 'True or version in (', 'unknown_and_mixed_manifests_are_refused_before_observation'),
            ('mixed-abi', MODULE_SOURCE, 'N71_PMD_DRIVER_MODULES_SCRIPT', "record['vermagic'] == version", 'True', 'unknown_and_mixed_manifests_are_refused_before_observation'),
            ('live-abi', MODULE_SOURCE, 'N71_PMD_DRIVER_MODULES_SCRIPT', "(selected_release(records), expected['boot'])", "(RELEASE, expected['boot'])", 'posix_full_load_and_reverse_cleanup_accept_only_the_selected_abi'),
            ('operation-abi', MODULE_SOURCE, 'N71_PMD_DRIVER_MODULES_SCRIPT', "operation['release'] == release", 'True', 'crossed_operation_or_live_kernel_refuses_before_any_receipt_or_effect'),
            ('remote-abi', MODULE_SOURCE, 'N71_PMD_DRIVER_MODULES_SCRIPT', '''test "$(uname -r)" = "' + release + '"; ''', 'true; ', 'crossed_operation_or_live_kernel_refuses_before_any_receipt_or_effect'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-pmd-wcc-mutations-') as directory:
            for name, source, variable, before, after, method in variants:
                text = source.read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory)/(name+'.py'); path.write_text(body)
                environment = dict(os.environ, **{variable: str(path)}, PYTHONDONTWRITEBYTECODE='1',
                                   PYTHONPATH=str(ROOT/'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                    'test_n71_pmd_driver_modules.PmdDriverModules.test_'+method], env=environment,
                    capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name+result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name+result.stderr)
                print('PMD_WCC_ASSERTION_KILL '+name, flush=True)


if __name__ == '__main__':
    unittest.main()
