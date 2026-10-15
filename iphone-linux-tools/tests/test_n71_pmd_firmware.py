"""PMD firmware selection/lifetime and same-boot recovery; hardware is modeled."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import test_n71_pmd_runtime_build as pmd_fixture
import test_n71_driver_firmware as package_fixture
import test_n71_driver_firmware_session as lifetime_fixture
import test_n71_driver_reacquire as reacquire_fixture

ROOT = pmd_fixture.ROOT
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_modules as wlan
import n71_iommu_build as iommu

SOURCES = {name: ROOT / ('scripts/host/' + filename) for name, filename in (
    ('package', 'n71_driver_firmware.py'), ('lifetime', 'n71_driver_firmware_session.py'),
    ('reacquire', 'n71_driver_reacquire.py'))}
VARIABLES = {name: 'N71_PMD_FIRMWARE_' + name.upper() + '_SCRIPT' for name in SOURCES}
RELEASE = iommu.PMD_RELEASE


def load(name):
    spec = importlib.util.spec_from_file_location('pmd_firmware_' + name, Path(os.environ.get(VARIABLES[name], SOURCES[name])))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class PmdFirmware(unittest.TestCase):
    def setUp(self):
        fixture = pmd_fixture.PmdRuntime('test_current_records_select_pmd_without_changing_legacy_or_sources')
        fixture.setUp(); self.addCleanup(fixture.doCleanups); self.pmd_root = fixture.root

    def copy_kernel(self, target):
        for source in self.pmd_root.rglob('*'):
            if not source.is_file(): continue
            path = target / source.relative_to(self.pmd_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)

    def accepted(self, function, *args, **kwargs):
        try: return function(*args, **kwargs)
        except (ValueError, KeyError, OSError) as error: self.fail('Qualified PMD firmware state refused: ' + str(error))

    def package(self):
        case = package_fixture.FirmwareTests('test_exact_order_owned_records_immutable_bytes_and_no_effects')
        case.subject = load('package'); case.setUp(); self.addCleanup(case.doCleanups)
        self.copy_kernel(case.root)
        case.request['release'] = RELEASE
        return case

    def test_catalog_stays_pinned_and_pmd_requires_a_qualified_matching_kernel(self):
        # Mutations killed: omit PMD kernel qualification or its firmware/kernel base binding.
        case = self.package()
        values = self.accepted(case.subject.select, case.root, case.request)
        self.assertEqual([record['path'] for record, _ in values], [name for name, _, _ in case.catalog])
        self.assertEqual([raw for _, raw in values], list(case.values.values()))
        self.assertEqual(case.subject.RELEASE, wlan.RELEASE)
        path = case.root / 'docs/evidence/kernel-n71-pmd-build.json'; raw = path.read_bytes()
        kernel = json.loads(raw); kernel['build']['full_image_linked'] = False; path.write_text(json.dumps(kernel))
        with self.assertRaises(ValueError): case.subject.select(case.root, case.request)
        path.write_bytes(raw)
        case.subject.KERNEL = 'f' * 40; case.reg['kernel_source_commit'] = case.subject.KERNEL; case.save()
        with self.assertRaises(ValueError): case.subject.select(case.root, case.request)

    def lifetime(self):
        outer = self

        class PmdLifetime(lifetime_fixture.FirmwareSessionTests):
            subject = load('lifetime')

            def fresh(inner):
                if not (inner.root / 'docs/evidence/kernel-n71-pmd-build.json').exists():
                    outer.copy_kernel(inner.root)
                super().fresh()
                inner.session.release = RELEASE; inner.session.result['kernel_release'] = RELEASE
                inner.session.driver_modules = wlan.qualified(ROOT, release=RELEASE)
                (inner.root / 'transport-settings-private.json').write_text(json.dumps({'release': RELEASE}))

        case = PmdLifetime('test_stage_bind_verify_restore_in_one_boot_and_keep_private_data')
        case.setUp(); self.addCleanup(case.doCleanups)
        return case

    def test_pmd_real_shell_stages_binds_restores_and_reconciles_without_replay(self):
        # Real shell/transport files model UID0/sysfs; no kernel firmware loader runs.
        for method in ('test_stage_bind_verify_restore_in_one_boot_and_keep_private_data',
                       'test_interrupted_binding_and_restore_reconcile_by_read_without_replay'):
            case = self.lifetime(); self.accepted(getattr(case, method))
            self.assertEqual(case.session.release, RELEASE)

    def test_configure_and_context_refuse_wcc_from_another_abi_before_capture(self):
        # Mutations killed: drop WCC/Session agreement at configuration or effect time.
        case = self.lifetime(); session = case.session
        session.driver_modules = wlan.qualified(ROOT)
        with self.assertRaises(ValueError): case.subject.header(session)
        del session.firmware_data
        with self.assertRaises(ValueError): case.subject.configure(session, {'root': case.root, 'directory': case.fixture.folder})
        self.assertEqual(case.calls, []); self.assertEqual(case.parameter.read_bytes(), b'')
        self.assertFalse(hasattr(session, 'firmware_data'))

    def reacquire(self):
        case = reacquire_fixture.ReacquireTests('test_check_only_keeps_session_and_files_unchanged_without_capture')
        case.subject = load('reacquire'); case.setUp(); self.addCleanup(case.doCleanups)

        def promote(session):
            session.release = RELEASE; session.result['kernel_release'] = RELEASE
            session.scan_hold = session.resource_capable = session.iommu_parent = True
            session.driver_modules = wlan.qualified(ROOT, release=RELEASE)
            return session

        promote(case.rt.session)
        restored = case.rt.case.restored
        case.rt.case.restored = lambda output: promote(restored(output))
        # Regenerate the model's initial PMD checkpoint before starting its cycle.
        case.rt.phone.journal.finish()
        original = case.fresh

        def fresh():
            session = promote(original())
            (case.fw.root / 'transport-settings-private.json').write_text(json.dumps({'release': RELEASE}))
            return session

        case.fresh = fresh
        return case

    def test_pmd_stopped_source_local_check_preserves_attributes_and_all_raw_files(self):
        # The unchanged teardown validator must accept PMD without probing or migrating owners.
        case = self.reacquire(); case.stopped(complete=True)
        case.session.output = case.rt.root / 'runtime'
        before = copy.deepcopy(case.session.result); attributes = dict(vars(case.session)); raw = case.bytes(case.source)
        result = self.accepted(case.subject.prepare, case.session, case.request(check=True))
        data = json.loads(raw['held-state-private.json'])
        self.assertEqual(result['previous_boot_id'], data['result']['boot_id'])
        self.assertEqual(case.calls, []); self.assertEqual(vars(case.session), attributes)
        self.assertEqual(case.session.result, before); self.assertEqual(case.bytes(case.source), raw)
        self.assertEqual(data['result']['kernel_release'], RELEASE)

    def test_reacquire_refuses_an_unknown_abi_even_with_otherwise_fresh_scope(self):
        # Mutation killed: remove known-release validation from reacquisition selection.
        case = self.reacquire(); case.stopped()
        self.accepted(case.subject.selection, case.session, case.request(check=True))
        case.session.release = 'unknown'; case.session.result['kernel_release'] = 'unknown'
        with self.assertRaises(ValueError): case.subject.selection(case.session, case.request(check=True))
        self.assertEqual(case.calls, [])


@unittest.skipIf(any(os.environ.get(name) for name in VARIABLES.values()), 'Mutation child selects subject')
class PmdFirmwareMutations(unittest.TestCase):
    def test_weakened_pmd_kernel_and_session_guards_fail_by_assertion(self):
        variants = [
            ('kernel', 'package', "if request['release'] == iommu.PMD_RELEASE:", 'if False:', 'catalog_stays_pinned_and_pmd_requires_a_qualified_matching_kernel'),
            ('base', 'package', "build['source_commit'] == KERNEL", 'True', 'catalog_stays_pinned_and_pmd_requires_a_qualified_matching_kernel'),
            ('configure-abi', 'lifetime', "require(wlan.selected_release(session.driver_modules) == session.release, 'Firmware WCC and Session ABI differ')", 'pass', 'configure_and_context_refuse_wcc_from_another_abi_before_capture'),
            ('effect-abi', 'lifetime', "require(wlan.selected_release(session.driver_modules) == session.release, 'Firmware effect WCC ABI differs')", 'pass', 'configure_and_context_refuse_wcc_from_another_abi_before_capture'),
            ('reacquire-abi', 'reacquire', 'session.release in firmware.firmware.RELEASES', 'True', 'reacquire_refuses_an_unknown_abi_even_with_otherwise_fresh_scope'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-pmd-firmware-mutations-') as directory:
            for name, kind, before, after, method in variants:
                text = SOURCES[kind].read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory)/(name+'.py'); path.write_text(body)
                environment = dict(os.environ, **{VARIABLES[kind]: str(path)}, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT/'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_n71_pmd_firmware.PmdFirmware.test_'+method],
                                        env=environment, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name+result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name+result.stderr)
                print('PMD_FIRMWARE_ASSERTION_KILL '+name, flush=True)


if __name__ == '__main__':
    unittest.main()
