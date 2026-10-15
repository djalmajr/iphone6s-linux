"""Bind PMD Session data and journals without operating a phone or kernel."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_n71_pmd_runtime_build as fixture
import test_n71_driver_module_stage as journal_fixture

ROOT = fixture.ROOT
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_modules as wlan
import n71_iommu_build as iommu
import n71_pmd_wifi_build as wifi


def load(name, source, variable):
    spec = importlib.util.spec_from_file_location(name, Path(os.environ.get(variable, source)))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


BUILD_SOURCE = ROOT / 'scripts/host/n71_driver_runtime_build.py'
PROFILE_SOURCE = ROOT / 'scripts/host/n71_driver_runtime_profile.py'
STAGE_SOURCE = ROOT / 'scripts/host/n71_driver_module_stage.py'
BUILD = load('pmd_runtime_builder', BUILD_SOURCE, 'N71_PMD_RUNTIME_CALLER_SCRIPT')
PROFILE = load('pmd_runtime_profile', PROFILE_SOURCE, 'N71_PMD_RUNTIME_PROFILE_SCRIPT')
STAGE = load('pmd_module_journal', STAGE_SOURCE, 'N71_PMD_MODULE_STAGE_SCRIPT')
RELEASE = iommu.PMD_RELEASE


def elf(name):
    raw = bytearray(b'\x7fELF\x02\x01\x01'.ljust(64, b'\0')); struct.pack_into('<HH', raw, 16, 1, 183)
    return bytes(raw) + name.encode() + b'\0vermagic=' + (RELEASE + ' SMP preempt mod_unload aarch64').encode() + b'\0'


class PmdRuntimeProfile(unittest.TestCase):
    def setUp(self):
        case = fixture.PmdRuntime('test_current_records_select_pmd_without_changing_legacy_or_sources')
        case.setUp(); self.addCleanup(case.doCleanups); self.root = case.root; self.folder = case.folder
        proof = json.loads((ROOT / 'docs/evidence/n71-pmd-wifi-modules-qualified.json').read_text())
        (self.folder / 'n71-pmd-wifi-modules-qualified.json').write_text(json.dumps(proof))
        for name in proof['input_qualification']['inputs']:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(fixture.compiled_source(name))
        hook = patch.object(PROFILE, 'build', BUILD); hook.start(); self.addCleanup(hook.stop)
        self.request = {'release': RELEASE, 'pcie_sha256': self.read(fixture.DIAGNOSTICS)['modules']['n71_pcie_diagnostic']['sha256']}
        self.actual = self.accepted(BUILD.select, self.root, self.request)
        # Only this disposable output metadata describes synthetic nonbootable ELF bytes.
        diagnostics = self.read(fixture.DIAGNOSTICS); self.raw = {}
        for key, name in [('n71_pcie_diagnostic', 'n71-pcie-diagnostic.ko'),
                          ('n71_wlan_power_diagnostic', 'n71-wlan-power-diagnostic.ko')]:
            data = elf(name); self.raw[name] = data
            diagnostics['modules'][key].update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        self.write(fixture.DIAGNOSTICS, diagnostics)
        reuse = self.read(fixture.REUSE)
        reuse['binary_comparison']['new_module_sha256'] = diagnostics['modules']['n71_pcie_diagnostic']['sha256']
        self.write(fixture.REUSE, reuse)
        for path in wifi.PATHS:
            name = path.rsplit('/', 1)[-1]; data = elf(name); self.raw[name] = data
            proof['modules'][path].update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        self.write('n71-pmd-wifi-modules-qualified.json', proof)
        self.request['pcie_sha256'] = diagnostics['modules']['n71_pcie_diagnostic']['sha256']
        self.selected = self.accepted(BUILD.select, self.root, self.request)
        self.modules = [(copy.deepcopy(row), self.raw[row['module']]) for row in self.selected['diagnostics']]
        self.drivers = [(copy.deepcopy(row), self.raw[row['module']]) for row in self.selected['drivers']]

    def read(self, name):
        return json.loads((self.folder / name).read_text())

    def write(self, name, data):
        (self.folder / name).write_text(json.dumps(data))

    def accepted(self, function, *args, **kwargs):
        try: return function(*args, **kwargs)
        except (ValueError, KeyError, OSError) as error: self.fail('Qualified PMD state refused: ' + str(error))

    def session(self):
        return SimpleNamespace(release=RELEASE, scan_hold=True, resource_capable=True,
                               iommu_parent=True, driver_runtime=False, modules=copy.deepcopy(self.modules))

    def configure(self, session, drivers=None):
        return PROFILE.configure(session, {'root': self.root, 'modules': self.drivers if drivers is None else drivers})

    def test_real_compiled_selection_binds_caller_reg_on_wcc_and_kernel(self):
        # Mutations killed: remove the PMD route, select legacy WCC or omit the runtime flag.
        self.assertEqual(len(self.actual['diagnostics']), 2)
        self.assertEqual(len(self.actual['drivers']), 5)
        self.assertIs(self.actual['diagnostics'][0]['driver_runtime'], True)
        self.assertEqual(self.actual['diagnostics'][0]['bytes'], 142232)
        self.assertTrue(all(r['vermagic'].startswith(RELEASE + ' ') for r in self.actual['diagnostics'] + self.actual['drivers']))
        self.assertEqual(self.actual['kernel_outputs']['Image']['sha256'],
                         self.read(fixture.KERNEL)['build']['outputs']['Image']['sha256'])
        for request in [dict(self.request, pcie_sha256='f' * 64), dict(self.request, release='unrecorded'),
                        dict(self.request, extra=True)]:
            with self.subTest(request=request), self.assertRaises(ValueError): BUILD.qualified(self.root, request)

    def test_configuration_owns_separate_immutable_module_bytes_and_rechecks_them(self):
        # Existing blob guards plus the new PMD selection must retain owned records and hashes.
        session = self.session(); self.accepted(self.configure, session)
        self.assertIs(session.driver_runtime, True)
        self.assertEqual(session.driver_modules, self.selected['drivers'])
        self.assertEqual(len(PROFILE.staged(session)), 5)
        self.assertEqual(session.driver_runtime_journal, []); self.assertEqual(session.driver_module_journal, [])
        self.drivers[0][0]['sha256'] = 'f' * 64
        self.assertEqual(session.driver_modules, self.selected['drivers'])
        self.accepted(PROFILE.selected, session, self.root)
        record, data = session.driver_module_data[0]
        session.driver_module_data[0] = (record, bytes([data[0] ^ 1]) + data[1:])
        with self.assertRaises(ValueError): PROFILE.selected(session, self.root)
        with self.assertRaises(ValueError): PROFILE.staged(session)

    def test_mode_and_byte_refusals_leave_configuration_and_files_untouched(self):
        # Mutation killed: drop the explicit held/resource/IOMMU Session requirement.
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for name, value in [('scan_hold', False), ('resource_capable', 1), ('iommu_parent', False), ('release', 'unknown')]:
            session = self.session(); setattr(session, name, value); original = copy.deepcopy(vars(session))
            with self.subTest(name=name), self.assertRaises(ValueError): self.configure(session)
            self.assertEqual(vars(session), original)
        for data in [bytearray(self.drivers[0][1]), self.drivers[0][1][:-1]]:
            session = self.session(); pairs = list(self.drivers); pairs[0] = (pairs[0][0], data)
            with self.assertRaises(ValueError): self.configure(session, pairs)
            self.assertIs(session.driver_runtime, False)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_journal_serializes_selected_abi_and_refuses_a_crossed_session(self):
        # Mutations killed: serialize a global ABI or omit Session/manifest agreement.
        states = {name: {'present': 0, 'state': '-', 'refs': 0, 'holders': []} for name in wlan.OBSERVED}
        state = {'boot': journal_fixture.BOOT, 'directory': '/run/n71-link-' + 'a' * 24, 'registered': 0, 'states': states}
        records = self.selected['drivers']
        text = self.accepted(STAGE.state_text, records, state)
        self.assertIn('release=' + RELEASE + ' boot=', text)
        self.accepted(STAGE.snapshot, records, state)
        session = self.session(); self.accepted(self.configure, session)
        self.assertEqual(self.accepted(STAGE.selected, session), records)
        session.release = wlan.RELEASE
        with self.assertRaises(ValueError): STAGE.selected(session)

    def test_pmd_journal_cycle_and_lost_transport_recovery_never_replay(self):
        # A real journal persists PMD intent/proofs; simulated transport supplies kernel observations.
        class PmdJournal(journal_fixture.ModuleJournalTests):
            subject = STAGE

            def make_session(inner, output):
                session = super().make_session(output)
                session.release = RELEASE; session.result['kernel_release'] = RELEASE
                session.driver_modules = wlan.qualified(ROOT, release=RELEASE)
                return session

        for method in ('test_ordered_load_and_reverse_unload_persist_only_the_proved_owners',
                       'test_lost_transport_recovers_receipt_without_repeating_load'):
            case = PmdJournal(method); case.setUp(); self.addCleanup(case.doCleanups)
            self.accepted(getattr(case, method))


@unittest.skipIf(any(os.environ.get(name) for name in ('N71_PMD_RUNTIME_CALLER_SCRIPT',
                'N71_PMD_RUNTIME_PROFILE_SCRIPT', 'N71_PMD_MODULE_STAGE_SCRIPT')), 'Mutation child selects subject')
class PmdRuntimeMutations(unittest.TestCase):
    def test_new_pmd_routes_and_journal_binding_fail_by_assertion(self):
        variants = [
            ('caller-route', BUILD_SOURCE, 'N71_PMD_RUNTIME_CALLER_SCRIPT', 'if release == iommu.PMD_RELEASE:', 'if False:', 'real_compiled_selection_binds_caller_reg_on_wcc_and_kernel'),
            ('caller-hash', BUILD_SOURCE, 'N71_PMD_RUNTIME_CALLER_SCRIPT', "request['pcie_sha256'] == parent['module_sha256']", 'True', 'real_compiled_selection_binds_caller_reg_on_wcc_and_kernel'),
            ('caller-wcc', BUILD_SOURCE, 'N71_PMD_RUNTIME_CALLER_SCRIPT', 'wlan.qualified(root, release=release)', 'wlan.qualified(root)', 'real_compiled_selection_binds_caller_reg_on_wcc_and_kernel'),
            ('runtime-flag', BUILD_SOURCE, 'N71_PMD_RUNTIME_CALLER_SCRIPT', 'driver_runtime=True', 'driver_runtime=False', 'real_compiled_selection_binds_caller_reg_on_wcc_and_kernel'),
            ('profile-pmd', PROFILE_SOURCE, 'N71_PMD_RUNTIME_PROFILE_SCRIPT', '(wlan.RELEASE, iommu.PMD_RELEASE)', '(wlan.RELEASE,)', 'configuration_owns_separate_immutable_module_bytes_and_rechecks_them'),
            ('profile-mode', PROFILE_SOURCE, 'N71_PMD_RUNTIME_PROFILE_SCRIPT', "all(getattr(session, name, None) is True for name in ('scan_hold', 'resource_capable', 'iommu_parent'))", 'True', 'mode_and_byte_refusals_leave_configuration_and_files_untouched'),
            ('journal-abi', STAGE_SOURCE, 'N71_PMD_MODULE_STAGE_SCRIPT', "'release=' + modules.selected_release(records)", "'release=' + modules.RELEASE", 'journal_serializes_selected_abi_and_refuses_a_crossed_session'),
            ('journal-session', STAGE_SOURCE, 'N71_PMD_MODULE_STAGE_SCRIPT', "getattr(session, 'release', None) == modules.selected_release(records)", 'True', 'journal_serializes_selected_abi_and_refuses_a_crossed_session'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-pmd-profile-mutations-') as directory:
            for name, source, variable, before, after, method in variants:
                text = source.read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory)/(name+'.py'); path.write_text(body)
                environment = dict(os.environ, **{variable: str(path)}, PYTHONDONTWRITEBYTECODE='1',
                                   PYTHONPATH=str(ROOT/'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                    'test_n71_pmd_runtime_profile.PmdRuntimeProfile.test_'+method], env=environment,
                    capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name+result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name+result.stderr)
                print('PMD_PROFILE_ASSERTION_KILL '+name, flush=True)


if __name__ == '__main__':
    unittest.main()
