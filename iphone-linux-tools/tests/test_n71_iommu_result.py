"""Software association, same-boot journal and refusal-before-unload contracts."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
SOURCE = ROOT / 'scripts/host/n71_iommu_result.py'
BUILD_SPEC = importlib.util.spec_from_file_location('n71_iommu_build', os.environ.get('N71_IOMMU_BUILD_SCRIPT', ROOT / 'scripts/host/n71_iommu_build.py'))
BUILD = importlib.util.module_from_spec(BUILD_SPEC)
sys.modules['n71_iommu_build'] = BUILD
BUILD_SPEC.loader.exec_module(BUILD)
SPEC = importlib.util.spec_from_file_location('n71_iommu_result', os.environ.get('N71_IOMMU_RESULT_SCRIPT', SOURCE))
RESULT = importlib.util.module_from_spec(SPEC)
sys.modules['n71_iommu_result'] = RESULT
SPEC.loader.exec_module(RESULT)
import test_n71_held_session as held_fixture
import test_n71_resource_stage as resource_fixture

HELD, LINK = held_fixture.HELD, held_fixture.LINK_SESSION
PROVIDER = ('N71_DART_CYCLE_PROVIDER bound=1 irq-hwirq=248 mapping-new=1; no DMA attachment\n'
            'N71_DART_LEASE_ACQUIRE error=0 running=1 pending=1; no DMA attachment\n')


def association(bus, devfn):
    return (f'N71_PCIE_SCAN_MSI bus={bus} devfn={devfn} inherited=1; no IRQ allocation\n'
            f'N71_PCIE_SCAN_DMA bus={bus} devfn={devfn} rid={"0008" if bus == 0 else "0100"} '
            'aliases-inferred=1 group=7 streaming=00000000ffffffff coherent=00000000ffffffff; '
            'public topology/source, read-only, no DMA\n'
            f'N71_PCIE_SCAN_IOMMU bus={bus} devfn={devfn} map_sid=0 translated=1; '
            'OF map and core domain, no private SID readback\n')


ACQUIRED = PROVIDER + held_fixture.ACQUIRED
for bus, devfn in ((0, '08'), (1, '00')):
    marker = f'N71_PCIE_SCAN_DEVICE bus={bus} devfn={devfn}'
    ACQUIRED = ACQUIRED.replace(marker, association(bus, devfn) + marker)
DART_CLEAN = ('N71_DART_CYCLE_REMOVED device=0 mapping-new=0 claimed=1; restore ownership held\n'
              'N71_DART_LEASE_CLEANUP error=0 pending=0 index=16 device=0 mapping-new=0 claimed=1 mapped=1; ownership retained until restore\n'
              'N71_DART_CYCLE_RELEASED device=0 mapping-new=0 claimed=0 mapped=0\n')
DART_CONTROL_ERROR = ('N71_DART_CYCLE_RESULT error=-5 snapshots=4 reads=152 guards=156 quiet=17 '
                      'writes=16 attempted=1 stopped=1 restored=1 control-changed=1; no DMA\n')


def getters(active=True):
    value=int(active)
    return (f'N71_PCIE_MSI requested=1 ready=1 held={value} associated={value} owner={value} '
            f'domain={value} mappings=0 child=0 session_error=0\n'
            f'N71_PCIE_IOMMU requested=1 ready=1 held={value} owner={value} available={value} '
            f'mapped={value} observed={2 * value} map_checked={value} session_error=0\n'
            'N71_HELD_PARAM msi_parent=Y\nN71_HELD_PARAM iommu_parent=Y\n')


OPEN = getters() + 'N71_PCIE_HELD held=1\n' + held_fixture.ACTIVE + ACQUIRED
CLOSED = (getters(False) + 'N71_PCIE_HELD held=0\n' + held_fixture.CLEAN + ACQUIRED
          + held_fixture.REMOVED + DART_CLEAN + held_fixture.CONFIG + held_fixture.PME_RESTORED
          + held_fixture.TLS_RESTORED + held_fixture.RESET + held_fixture.POWER + held_fixture.FINISHED)
UNBOUND_GETTERS = getters(False).replace('ready=1', 'ready=0')
UNBOUND_STATUS = 'N71_PCIE_STATUS ready=0 retained=0\n'
UNBOUND_RESOURCES = 'N71_PCIE_RESOURCES ready=0 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=0\n'
UNBOUND_PREPARE = 'N71_PCIE_SCAN_DART_PREPARED error=-19 available=0 mapped=0; before PCI publication\n'
UNBOUND_HISTORY = (PROVIDER + held_fixture.ACQUIRED.split('N71_PCIE_SCAN_DEVICE ')[0] + UNBOUND_PREPARE
                   + held_fixture.CONFIG + held_fixture.PME_RESTORED + held_fixture.TLS_RESTORED
                   + 'N71_PCIE_SCAN_RESULT error=-19 devices=0 endpoints=0 reads=149 attempts=0 writes=0 refusals=0; counts before cleanup, no DMA or radio\n'
                   + DART_CLEAN + held_fixture.RESET + held_fixture.POWER
                   + held_fixture.FINISHED.replace('primary_error=0', 'primary_error=-19'))
UNBOUND = UNBOUND_GETTERS + 'N71_PCIE_HELD held=0\n' + UNBOUND_STATUS + UNBOUND_RESOURCES + UNBOUND_HISTORY
DMA_EXPECTED = dict(requester_ids=[8, 256], group_id=7, mask_bits=32, root_aliases_inferred=1,
                    endpoint_aliases_inferred=1, aliases_inferred_from_fixed_source=True,
                    physical_translation_verified=False)


class IommuPhone(resource_fixture.ResourcePhone):
    """Track actual command effects; hardware dependencies remain synthetic."""
    def __init__(self):
        super().__init__()
        self.overrides['pcie'] = self.acquired
        self.overrides['held-cleanup'] = self.cleaned

    @staticmethod
    def acquired(phone, session, text):
        command = phone.calls[-1][1]
        assert 'msi_parent=1 iommu_parent=1' in command
        assert 'cat ' + RESULT.PCIE + 'iommu;' in command
        phone.history = held_fixture.BASELINE + held_fixture.timestamp(held_fixture.LINK + held_fixture.INVENTORY + ACQUIRED, 10)
        return 0, getters() + 'N71_PCIE_HELD held=1\n' + held_fixture.ACTIVE + phone.history

    @staticmethod
    def cleaned(phone, session, text):
        assert 'cat ' + RESULT.PCIE + 'iommu;' in phone.calls[-1][1]
        config = held_fixture.timestamp(held_fixture.CONFIG, 100)
        phone.history = phone.history.replace(config, held_fixture.timestamp(DART_CLEAN, 90) + config)
        return 0, getters(False) + phone.getter() + 'N71_PCIE_HELD held=0\n' + phone.status + phone.history

    def snapshot(self, session):
        if self.pcie:
            assert 'cat ' + RESULT.PCIE + 'iommu;' in self.calls[-1][1]
        return (getters(self.held) if self.pcie else '') + super().snapshot(session)


class IommuResultTests(unittest.TestCase):
    def setUp(self):
        self.session = SimpleNamespace(iommu_parent=True, result={})

    def accepted(self, function, *args):
        try:
            return function(*args)
        except (ValueError, KeyError) as error:
            self.fail('Valid contract refused: ' + str(error))

    def test_opt_in_exact_module_and_scope_before_effects(self):
        # Mutations killed: relax boolean, ABI, held/resource scope, bytes/hash/vermagic.
        proof = json.loads((ROOT / 'docs/evidence/n71-dma-topology-qualification.json').read_text())['kernel_build']
        record = dict(module='n71-pcie-diagnostic.ko', bytes=proof['module_bytes'], sha256=proof['module_sha256'], vermagic=proof['vermagic'])
        session = SimpleNamespace(iommu_parent=True, scan_hold=True, resource_capable=True,
                                  release=RESULT.n71_scan_held_result.RELEASE, modules=[(record, b'fixture')])
        self.accepted(RESULT.selected, session, ROOT)
        for field, value in (('iommu_parent', 1), ('iommu_parent', None), ('scan_hold', False),
                             ('resource_capable', False), ('release', 'wrong')):
            changed = copy.deepcopy(session); setattr(changed, field, value)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                RESULT.selected(changed, ROOT)
        for field, value in (('sha256', 'f' * 64), ('bytes', True), ('bytes', proof['module_bytes'] + 1), ('vermagic', 'wrong')):
            changed = copy.deepcopy(session); changed.modules[0][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                RESULT.selected(changed, ROOT)
        session.iommu_parent=False
        self.accepted(RESULT.selected, session, Path('/does-not-exist'))
        self.assertEqual(RESULT.getter(session), '')

    def test_retained_software_association_has_bounded_proof_tier(self):
        # Mutations killed: skip active getter, fabricate delivery or accept duplicate/partial topology.
        self.accepted(RESULT.retained, self.session, OPEN)
        self.assertEqual(self.session.result['iommu_association'], dict(observed_devices=2,
                         software_association_observed=True, irq_delivery_verified=False,
                         dma_translation_verified=False, wifi_verified=False, battery_or_charging_verified=False,
                         dma_topology=DMA_EXPECTED))
        for row in (PROVIDER.splitlines(True) + association(0, '08').splitlines(True)
                    + association(1, '00').splitlines(True) + getters().splitlines(True)):
            for text in (OPEN.replace(row, '', 1), OPEN + row, OPEN.replace(row, row.rstrip() + ' extra\n')):
                with self.subTest(row=row), self.assertRaises(ValueError):
                    RESULT.retained(SimpleNamespace(iommu_parent=True, result={}), text)

    def test_getter_state_and_exact_map_contract_refuse_drift(self):
        # Mutations killed: ignore counts, scoping, inactive owner, SID/provider or cleanup attempts.
        invalid = [OPEN.replace('mappings=0', 'mappings=1'), OPEN.replace('observed=2', 'observed=1'),
                   OPEN.replace('owner=1', 'owner=0'), OPEN.replace('map_checked=1', 'map_checked=0'),
                   OPEN.replace('available=1', 'available=0'), OPEN.replace('mapped=1', 'mapped=0'),
                   OPEN.replace('map_sid=0', 'map_sid=1'), OPEN.replace('translated=1', 'translated=0'),
                   OPEN.replace('devfn=08 map_sid', 'devfn=09 map_sid'),
                   OPEN + DART_CLEAN, OPEN.replace('iommu_parent=Y', 'iommu_parent=N')]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                RESULT.retained(self.session, text)
        for text in (getters().replace('observed=2 map_checked=1', 'observed=3 map_checked=0'),
                     getters().replace('N71_PCIE_MSI requested=1 ready=1', 'N71_PCIE_MSI requested=1 ready=0'),
                     getters().replace('session_error=0', 'session_error=-4096')):
            with self.assertRaises(ValueError): RESULT.live(text)
        first = association(0, '08')
        with self.assertRaises(ValueError):
            RESULT.retained(self.session, OPEN.replace(first, ''.join(reversed(first.splitlines(True)))))

    def test_final_getters_and_observed_removal_release_restore_order(self):
        # Mutations killed: unload with owners, missing release, or provider stop before bus removal.
        result = self.accepted(RESULT.cleanup, self.session, CLOSED)
        self.assertEqual(result, dict(software_ownership_released=True, physical_of_unmap_readback_verified=False,
                                     irq_delivery_verified=False, dma_translation_verified=False))
        invalid = [CLOSED.replace(getters(False), getters()), CLOSED.replace(DART_CLEAN, ''),
                   CLOSED.replace('index=16', 'index=15'), CLOSED.replace('pending=0 index=16', 'pending=1 index=16'),
                   CLOSED.replace(held_fixture.REMOVED + DART_CLEAN, DART_CLEAN + held_fixture.REMOVED),
                   CLOSED.replace(DART_CLEAN + held_fixture.CONFIG, held_fixture.CONFIG + DART_CLEAN)]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError): RESULT.cleanup(self.session, text)

    def test_checkpoint_selection_summary_and_live_drift(self):
        # Mutations killed: forget saved mode, summary, or compare only PCI state on resume.
        self.accepted(RESULT.retained, self.session, OPEN)
        data = dict(iommu_parent=True, result=self.session.result)
        self.accepted(RESULT.saved, self.session, data, OPEN)
        for changed in (dict(data, iommu_parent=False), dict(data, result={})):
            with self.assertRaises(ValueError): RESULT.saved(self.session, changed, OPEN)
        self.accepted(RESULT.resume, self.session, OPEN, OPEN)
        with self.assertRaises(ValueError):
            RESULT.resume(self.session, OPEN.replace('observed=2 map_checked=1', 'observed=0 map_checked=0'), OPEN)

    def test_pre_hold_failure_can_prove_complete_release_without_fabricated_attachment(self):
        # Mutation killed: require sixteen table writes for a provider that never attempted start.
        for attempted in (False, True):
            prefix = getters(False).replace('ready=1', 'ready=0') + 'N71_PCIE_HELD held=0\nN71_PCIE_STATUS ready=0 retained=0\n'
            acquired = f'N71_DART_LEASE_ACQUIRE error=-19 running=0 pending={int(attempted)}; no DMA attachment\n'
            lease = ('N71_DART_LEASE_CLEANUP error=0 pending=0 index=' + ('16' if attempted else '0')
                     + ' device=0 mapping-new=0 claimed=' + ('1' if attempted else '0')
                     + ' mapped=' + ('1' if attempted else '0') + '; ownership retained until restore\n')
            released = DART_CLEAN.splitlines(True)[-1]
            self.assertTrue(self.accepted(RESULT.cleanup, self.session, prefix + acquired + lease + released)['software_ownership_released'])

    def execution(self, phone, folder, name, source=None, *, assign=False):
        output = folder / 'runtime' / name; output.mkdir(mode=0o700)
        build = json.loads((ROOT / 'docs/evidence/n71-dma-topology-qualification.json').read_text())['kernel_build']
        modules = [({'module': HELD.MODULES[0], 'bytes': build['module_bytes'], 'sha256': build['module_sha256'], 'vermagic': build['vermagic']}, b'fixture'),
                   ({'module': HELD.MODULES[1], 'sha256': 'b' * 64}, b'reg-fixture')]
        with patch.object(LINK, 'ROOT', ROOT), patch.object(LINK.device_profile, 'ssh_options', return_value=[]):
            session = LINK.Session(output, modules, host_scan=True, scan_link_target=True, scan_pme_disable=True,
                                   scan_hold=True, resource_capable=True, iommu_parent=True, release=LINK.BINDING_RELEASE)
        session.capture = lambda *args, **kwargs: phone.capture(session, *args, **kwargs)
        with contextlib.redirect_stdout(io.StringIO()), patch.object(HELD, 'n71_resource_stage', resource_fixture.STAGE):
            code = HELD.run(session, {'modules': {r['module']: r['sha256'] for r, _ in modules}}, root=folder, source=source, assign=assign)
        return code, session, output

    def test_restored_control_error_retains_negative_operation_without_pending_owners(self):
        # Mutations killed: erase provider EIO, accept incomplete/duplicate restore or lose causal first error.
        released = DART_CLEAN.splitlines(True)[-1]
        text = (CLOSED.replace(held_fixture.CLEAN, held_fixture.CLEAN.replace('primary_error=0', 'primary_error=-5'))
                .replace(held_fixture.FINISHED, held_fixture.FINISHED.replace('primary_error=0', 'primary_error=-5'))
                .replace(released, DART_CONTROL_ERROR + released))
        proof = self.accepted(RESULT.cleanup, self.session, text)
        self.assertEqual(proof.get('provider_operation_error'), -5)
        self.assertTrue(proof['software_ownership_released'])
        self.assertFalse(proof['dma_translation_verified'])
        invalid = [text + DART_CONTROL_ERROR, text + 'N71_DART_CYCLE_RESULT malformed\n',
                   text.replace('primary_error=-5', 'primary_error=-13'),
                   text.replace('snapshots=4', 'snapshots=3'), text.replace('reads=152', 'reads=151'),
                   text.replace('guards=156', 'guards=155'), text.replace('quiet=17', 'quiet=16'),
                   text.replace('writes=16', 'writes=15'), text.replace('stopped=1', 'stopped=0'),
                   text.replace('restored=1', 'restored=0'), text.replace('attempted=1', 'attempted=0'),
                   text.replace('CYCLE_RESULT error=-5', 'CYCLE_RESULT error=-13'),
                   text.replace('CYCLE_RESULT error=-5', 'CYCLE_RESULT error=-4096'),
                   text.replace('LEASE_CLEANUP error=0 pending=0', 'LEASE_CLEANUP error=-5 pending=1'),
                   text.replace(DART_CLEAN.splitlines(True)[0], ''),
                   text.replace(DART_CONTROL_ERROR, '').replace(held_fixture.CONFIG, held_fixture.CONFIG + DART_CONTROL_ERROR)]
        for changed in invalid:
            with self.subTest(text=changed), self.assertRaises(ValueError):
                RESULT.cleanup(self.session, changed)

    def test_actual_coordinator_releases_restored_control_error_and_reuses_cleanup_proof(self):
        # Mutations killed: omit provider proof/passing EIO or repeat cleanup/assignment on resume.
        class ControlErrorPhone(IommuPhone):
            @staticmethod
            def cleaned(phone, session, text):
                IommuPhone.cleaned(phone, session, text)
                first_error = phone.assignment_error or -5
                phone.status = phone.status.replace('primary_error=0', 'primary_error=' + str(first_error))
                phone.resources['error'] = first_error
                release = held_fixture.timestamp(DART_CLEAN, 90)
                inserted = held_fixture.timestamp(DART_CLEAN.replace(DART_CLEAN.splitlines(True)[-1],
                                                 DART_CONTROL_ERROR + DART_CLEAN.splitlines(True)[-1]), 90)
                phone.history = phone.history.replace(release, inserted).replace(held_fixture.FINISHED,
                                       held_fixture.FINISHED.replace('primary_error=0', 'primary_error=' + str(first_error)))
                return 0, getters(False) + phone.getter() + 'N71_PCIE_HELD held=0\n' + phone.status + phone.history

        for assignment_error in (0, -13):
            with self.subTest(assignment_error=assignment_error), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory); (folder / 'runtime').mkdir(mode=0o700); phone = ControlErrorPhone()
                phone.assignment_error = assignment_error
                code, _, source = self.execution(phone, folder, 'acquire'); self.assertEqual(code, 0)
                code, _, source = self.execution(phone, folder, 'assign', source, assign=True); self.assertEqual(code, int(assignment_error != 0))
                code, session, source = self.execution(phone, folder, 'release', source)
                self.assertEqual(code, int(assignment_error != 0), session.result)
                self.assertTrue(session.result['cleanup_verified'])
                self.assertEqual(session.result['resource_assignment']['error'], assignment_error)
                self.assertEqual(session.result.get('iommu_cleanup', {}).get('provider_operation_error'), -5)
                self.assertFalse(phone.pcie or phone.reg or phone.active)
                code, session, _ = self.execution(phone, folder, 'resume-clean', source)
                self.assertEqual(code, int(assignment_error != 0), session.result)
                self.assertEqual((phone.assignments, phone.cleanup_calls), (1, 1))

    def test_unbound_prepare_failure_requires_matching_negative_complete_release(self):
        self.assertTrue(self.accepted(RESULT.cleanup, self.session, UNBOUND)['software_ownership_released'])
        invalid = [UNBOUND.replace('SCAN_RESULT error=-19', 'SCAN_RESULT error=-5'),
                   UNBOUND.replace('primary_error=-19', 'primary_error=-5'),
                   UNBOUND.replace('devices=0 endpoints=0', 'devices=2 endpoints=1'),
                   UNBOUND.replace('available=0 mapped=0; before', 'available=1 mapped=0; before'),
                   UNBOUND.replace(UNBOUND_PREPARE, ''), UNBOUND + UNBOUND_PREPARE,
                   UNBOUND.replace(held_fixture.FINISHED.replace('primary_error=0', 'primary_error=-19'), ''),
                   UNBOUND + held_fixture.FINISHED.replace('primary_error=0', 'primary_error=-19'),
                   UNBOUND.replace('error=-19', 'error=-5000'),
                   UNBOUND.replace(held_fixture.RESET, ''), UNBOUND.replace(held_fixture.POWER, ''),
                   UNBOUND.replace(held_fixture.CONFIG, '') + held_fixture.CONFIG,
                   UNBOUND.replace(UNBOUND_PREPARE, held_fixture.CONFIG + UNBOUND_PREPARE).replace(held_fixture.CONFIG + held_fixture.PME_RESTORED, held_fixture.PME_RESTORED),
                   UNBOUND.replace(DART_CLEAN, ''), UNBOUND.replace(PROVIDER, ''),
                   UNBOUND.replace('error=0 running=1 pending=1', 'error=-5 running=0 pending=1'),
                   UNBOUND.replace('index=16', 'index=15'), UNBOUND + held_fixture.CONFIG,
                   UNBOUND.replace(held_fixture.RESET + held_fixture.POWER, held_fixture.POWER + held_fixture.RESET),
                   UNBOUND.replace('ready=0 held=0 owner=0', 'ready=0 held=0 owner=1')]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError): RESULT.cleanup(self.session, text)

    def test_actual_coordinator_cleans_unbound_probe_failure_without_second_scan(self):
        class UnboundPhone(IommuPhone):
            @staticmethod
            def acquired(phone, session, text):
                phone.held = False; phone.empty = True; phone.status = UNBOUND_STATUS
                phone.resources = dict.fromkeys(resource_fixture.STAGE.n71_resource_result.FIELDS, 0)
                phone.history = held_fixture.BASELINE + held_fixture.timestamp(held_fixture.LINK + held_fixture.INVENTORY + UNBOUND_HISTORY, 10)
                return 0, UNBOUND_GETTERS + UNBOUND_RESOURCES + 'N71_PCIE_HELD held=0\n' + phone.status + phone.history

            def snapshot(self, session):
                return super().snapshot(session).replace(getters(False), UNBOUND_GETTERS)

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); (folder / 'runtime').mkdir(mode=0o700); phone = UnboundPhone()
            code, session, _ = self.execution(phone, folder, 'failed-prepare')
            self.assertEqual(code, 1, session.result)
            self.assertTrue(session.result['cleanup_verified'], session.result)
            self.assertTrue(session.result.get('iommu_cleanup', {}).get('software_ownership_released'))
            self.assertFalse(phone.pcie or phone.reg or phone.active)
            stages = [stage for stage, _ in phone.calls]
            self.assertEqual(stages.count('pcie'), 1)
            self.assertEqual(stages.count('held-pcie-unload'), 1)
            self.assertEqual(stages.count('held-reg-unload'), 1)
            self.assertNotIn('held-cleanup', stages)
            self.assertNotIn('held-assign', stages)

    def test_actual_coordinator_acquires_resumes_and_releases_without_rescan(self):
        # Mutations killed: omit module args/getters, journal selection or unload without association cleanup.
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); (folder / 'runtime').mkdir(mode=0o700); phone=IommuPhone()
            code, session, source = self.execution(phone, folder, 'acquire')
            self.assertEqual(code, 0, session.result)
            self.assertTrue(session.result['iommu_association']['software_association_observed'])
            self.assertTrue(json.loads((source / 'held-state-private.json').read_text())['iommu_parent'])
            code, session, _ = self.execution(phone, folder, 'release', source)
            self.assertEqual(code, 0, session.result)
            self.assertTrue(session.result.get('iommu_cleanup', {}).get('software_ownership_released'))
            self.assertFalse(phone.pcie or phone.reg or phone.active)
            self.assertEqual((phone.cleanup_calls, sum(stage == 'pcie' for stage, _ in phone.calls)), (1, 1))

    def test_resume_selection_or_getter_drift_precedes_any_cleanup_effect(self):
        # Mutations killed: skip journal/live checks and operate on altered immutable selection.
        for field in ('saved-mode', 'immutable', 'observation'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                folder=Path(directory); (folder / 'runtime').mkdir(mode=0o700); phone=IommuPhone()
                code, session, source=self.execution(phone, folder, 'acquire'); self.assertEqual(code, 0)
                if field == 'saved-mode':
                    path=source / 'held-state-private.json'; data=json.loads(path.read_text()); data['iommu_parent']=False
                    path.write_text(json.dumps(data))
                else:
                    before, after = (('iommu_parent=Y', 'iommu_parent=N') if field == 'immutable' else
                                     ('observed=2 map_checked=1', 'observed=0 map_checked=0'))
                    phone.overrides['held-resume-live']=lambda phone, session, text: (0, text.replace(before, after))
                code, session, _=self.execution(phone, folder, 'refused', source)
                self.assertEqual(code, 1, session.result)
                self.assertEqual(phone.cleanup_calls, 0)
                self.assertTrue(phone.reg and phone.active and phone.pcie)

    def test_pending_association_blocks_unload_and_reg_release(self):
        # Mutation killed: omit association cleanup validation after generic PCI status says clean.
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); (folder / 'runtime').mkdir(mode=0o700); phone=IommuPhone()
            code, _, source=self.execution(phone, folder, 'acquire'); self.assertEqual(code, 0)
            def pending(phone, session, text):
                code, text=IommuPhone.cleaned(phone, session, text)
                return code, text.replace('held=0 owner=0 available=0 mapped=0', 'held=0 owner=1 available=1 mapped=0')
            phone.overrides['held-cleanup']=pending
            code, session, _=self.execution(phone, folder, 'pending', source)
            self.assertEqual(code, 1, session.result)
            self.assertTrue(phone.pcie and phone.reg and phone.active)
            self.assertFalse(any(stage in ('held-pcie-unload', 'held-restore') for stage, _ in phone.calls))

    def test_invalid_first_capture_is_refused_and_cleaned_in_same_boot(self):
        # Mutation killed: skip initial association parsing and certify a later checkpoint instead.
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); (folder / 'runtime').mkdir(mode=0o700); phone=IommuPhone()
            def corrupt(phone, session, text):
                code, text=IommuPhone.acquired(phone, session, text)
                return code, text.replace('mappings=0', 'mappings=1')
            phone.overrides['pcie']=corrupt
            code, session, _=self.execution(phone, folder, 'refused')
            self.assertEqual(code, 1, session.result)
            self.assertFalse(session.result.get('held_verified', False))
            self.assertTrue(session.result['cleanup_verified'], session.result)
            self.assertEqual(phone.cleanup_calls, 1)

    def test_pre_scan_bound_failure_preserves_first_error_and_all_release_proofs(self):
        # Mutations killed: omit reset/power/error/empty-resource checks on a retained provider failure.
        session=SimpleNamespace(iommu_parent=True, result={}, resource_attempted=False, resource_assignment=None,
                                modules=[({'module': 'n71-pcie-diagnostic.ko'}, b'fixture')])
        prefix=getters(False) + 'N71_PCIE_HELD held=0\n' + held_fixture.CLEAN.replace('primary_error=0', 'primary_error=-19')
        provider=('N71_DART_LEASE_ACQUIRE error=-19 running=0 pending=0; no DMA attachment\n'
                  'N71_DART_LEASE_CLEANUP error=0 pending=0 index=0 device=0 mapping-new=0 claimed=0 mapped=0; ownership retained until restore\n'
                  + DART_CLEAN.splitlines(True)[-1])
        resources='N71_PCIE_RESOURCES ready=0 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=-19\n'
        text=prefix + resources + provider + held_fixture.RESET + held_fixture.POWER + held_fixture.FINISHED.replace('primary_error=0', 'primary_error=-19')
        self.assertFalse(self.accepted(RESULT.pre_scan_cleanup, session, text)['held_acquired'])
        for changed in (text.replace(held_fixture.RESET, ''), text.replace(held_fixture.POWER, ''),
                        text.replace('active=0 error=-19', 'active=1 error=-19'),
                        text.replace('error=-19 running=0', 'error=-5 running=0'),
                        text.replace(held_fixture.RESET + held_fixture.POWER, held_fixture.POWER + held_fixture.RESET)):
            with self.assertRaises(ValueError): RESULT.pre_scan_cleanup(session, changed)

    def test_saved_cleanup_summary_cannot_claim_a_stronger_proof_than_its_log(self):
        # Mutation killed: trust a saved physical-proof boolean instead of reconstructing the summary.
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory); (folder / 'runtime').mkdir(mode=0o700); phone=IommuPhone()
            code, _, source=self.execution(phone, folder, 'acquire'); self.assertEqual(code, 0)
            code, _, final=self.execution(phone, folder, 'release', source); self.assertEqual(code, 0)
            path=final / 'held-state-private.json'; data=json.loads(path.read_text())
            self.assertIn('iommu_cleanup', data['result'])
            data['result']['iommu_cleanup']['physical_of_unmap_readback_verified']=True; path.write_text(json.dumps(data))
            calls=len(phone.calls)
            code, session, _=self.execution(phone, folder, 'refused', final)
            self.assertEqual(code, 1, session.result); self.assertEqual(len(phone.calls), calls)


    def test_dma_group_masks_requesters_and_inferred_aliases_are_strict(self):
        # Mutations killed: omit exact requester/count, shared group, masks or alias constraints.
        invalid = [OPEN.replace('rid=0008', 'rid=0009'), OPEN.replace('rid=0100', 'rid=0101'),
                   OPEN.replace('aliases-inferred=1 group=7', 'aliases-inferred=3 group=7'),
                   OPEN.replace('devfn=00 rid=0100 aliases-inferred=1 group=7',
                                'devfn=00 rid=0100 aliases-inferred=1 group=8'),
                   OPEN.replace('group=7', 'group=2147483648'), OPEN.replace('group=7', 'group=-1'),
                   OPEN.replace('streaming=00000000ffffffff', 'streaming=ffffffffffffffff'),
                   OPEN.replace('coherent=00000000ffffffff', 'coherent=0000000000000000')]
        dma = [row for row in association(0, '08').splitlines(True) if 'N71_PCIE_SCAN_DMA ' in row][0]
        invalid += [OPEN + dma.rstrip() + ' extra\n', OPEN.replace(dma, '')]
        msi = association(0, '08').splitlines(True)[0]
        invalid += [OPEN.replace(msi + dma, dma + msi)]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                RESULT.retained(SimpleNamespace(iommu_parent=True, result={}), text)

    def test_legacy_alias_inference_and_group_zero_have_only_software_proof(self):
        # Mutations killed: reject valid legacy alias/group0 or promote inference to physical proof.
        for group in (0, 2147483647):
            text = OPEN.replace('group=7', 'group=' + str(group)).replace(
                'devfn=00 rid=0100 aliases-inferred=1', 'devfn=00 rid=0100 aliases-inferred=2')
            session = SimpleNamespace(iommu_parent=True, result={})
            self.accepted(RESULT.retained, session, text)
            self.assertEqual(session.result['iommu_association']['dma_topology'],
                             dict(DMA_EXPECTED, group_id=group, endpoint_aliases_inferred=2))
            self.assertFalse(session.result['iommu_association']['dma_translation_verified'])

    def test_source_binding_exports_and_previous_abi_refuse_selection(self):
        # Mutations killed: accept changed weak binding/source/exports or select the superseded D16 ABI.
        proof = json.loads((ROOT / 'docs/evidence/n71-dma-topology-qualification.json').read_text())
        build = proof['kernel_build']
        record = dict(module='n71-pcie-diagnostic.ko', bytes=build['module_bytes'],
                      sha256=build['module_sha256'], vermagic=build['vermagic'])
        session = SimpleNamespace(iommu_parent=True, scan_hold=True, resource_capable=True,
                                  release=RESULT.n71_scan_held_result.RELEASE, modules=[(record, b'fixture')])
        changes = [('source_commit', 'foreign'), ('tracked_patch_sha256', 'f' * 64),
                   ('vmlinux_symbol_binding', {'pci_for_each_dma_alias': 'T', 'pci_real_dma_dev': 'T'}),
                   ('arm64_real_dma_override_files', ['arch/arm64/foreign.c']),
                   ('exported_group_apis', []), ('unexported_alias_helpers', [])]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); target = folder / 'docs/evidence'; target.mkdir(parents=True)
            for key, value in changes:
                changed = copy.deepcopy(proof); changed['primary_source_audit'][key] = value
                (target / 'n71-dma-topology-qualification.json').write_text(json.dumps(changed))
                with self.subTest(key=key), self.assertRaises(ValueError): RESULT.selected(session, folder)
            for key in ('exported_group_apis_present', 'unexported_alias_helpers_not_referenced'):
                changed = copy.deepcopy(proof); changed['kernel_build'][key] = False
                (target / 'n71-dma-topology-qualification.json').write_text(json.dumps(changed))
                with self.subTest(key=key), self.assertRaises(ValueError): RESULT.selected(session, folder)
        previous = json.loads((ROOT / 'docs/evidence/n71-iommu-caller-qualification.json').read_text())['kernel_build']
        session.modules[0][0].update(bytes=previous['module_bytes'], sha256=previous['module_sha256'])
        with self.assertRaises(ValueError): RESULT.selected(session, ROOT)

    def test_saved_dma_details_are_reconstructed_before_any_resume_effect(self):
        # Mutation killed: trust saved DMA fields or remove the new observations from the journal summary.
        for field, value in (('group_id', 8), ('mask_bits', 64), ('root_aliases_inferred', 2),
                             ('requester_ids', [8, 257]), ('physical_translation_verified', True)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory); (folder / 'runtime').mkdir(mode=0o700); phone = IommuPhone()
                code, _, source = self.execution(phone, folder, 'acquire'); self.assertEqual(code, 0)
                path = source / 'held-state-private.json'; data = json.loads(path.read_text())
                data['result']['iommu_association']['dma_topology'][field] = value
                path.write_text(json.dumps(data)); calls = len(phone.calls)
                code, session, _ = self.execution(phone, folder, 'refused', source)
                self.assertEqual(code, 1, session.result); self.assertEqual(len(phone.calls), calls)


class IommuMutationTests(unittest.TestCase):
    @unittest.skipIf(os.environ.get('N71_IOMMU_MUTATION_CHILD'), 'Parent mutation gate only')
    def test_compiled_mutations_fail_by_assertion(self):
        variants = {
            'boolean': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'type(value) is bool', 'True'),
            'scope': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'session.scan_hold and session.resource_capable', 'True'),
            'hash': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "records[0]['sha256'] == build['module_sha256']", 'True'),
            'bytes': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "records[0]['bytes'] == build['module_bytes']", 'True'),
            'active': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "live(text) == {'msi': MSI_ACTIVE, 'iommu': IOMMU_ACTIVE}", 'True'),
            'topology': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "[row.groups() for row in rows] == [('0', '08'), ('1', '00')]", 'True'),
            'publication-order': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'positions == sorted(set(positions))', 'True'),
            'budget': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "0 <= iommu['observed'] <= 2", 'True'),
            'getter-scope': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "all(msi[key] == iommu[key] for key in ('requested', 'ready', 'held', 'session_error'))", 'True'),
            'retained-provider': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "'N71_DART_CYCLE_RELEASED ' not in text and 'N71_DART_LEASE_CLEANUP ' not in text", 'True'),
            'saved-mode': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "data.get('iommu_parent', False) is capable(session)", 'True'),
            'saved-summary': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "data['result'].get('iommu_association') == expected", 'True'),
            'lease-restore': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "final[:5] == ('0', '0', '16' if pending else '0', '0', '0')", 'True'),
            'consumer-order': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'removed.start() < lease[0].start()', 'True'),
            'config-order': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'released.start() < configs[0].start()', 'True'),
            'unbound-error-bounds': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', '-4095 <= primary < 0', 'True'),
            'unbound-unique-caller': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "len(finished) == text.count('N71_PCIE_SESSION_CLEANUP ') == 1", 'True'),
            'unbound-order': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'configs[-1].start() < lease[0].start()', 'True'),
            'control-error-unique': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "text.count('N71_DART_CYCLE_RESULT ') == 1", 'True'),
            'control-error-complete': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'cycle == dict(error=-5, snapshots=4, reads=152, guards=156, quiet=17, writes=16,\n                                      attempted=1, stopped=1, restored=1, control_changed=1)', 'True'),
            'control-error-first': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "caller.get('primary_error', 0) == first_error", 'True'),
            'control-error-first-assignment': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "first_error = (assignment['error'] if assignment else 0) or cycle['error']", "first_error = cycle['error']"),
            'control-error-removed': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'n71_dart_cycle_result.cleanup(text)', 'pass'),
            'control-error-order': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "lease[-1].start() < text.index('N71_DART_CYCLE_RESULT ') < released.start()", 'True'),
            'control-error-preserved': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "proof['provider_operation_error'] = cycle['error']", "proof['provider_operation_error'] = 0"),
            'control-error-passed': ('n71_resource_stage.py', 'N71_RESOURCE_STAGE_SCRIPT', 'provider_error=provider_error)', 'provider_error=0)'),
            'module-args': ('n71-link-session.py', 'N71_HELD_LINK_SCRIPT', "parameters += ' msi_parent=1 iommu_parent=1'", "parameters += ''"),
            'initial-proof': ('n71-link-session.py', 'N71_HELD_LINK_SCRIPT', 'n71_iommu_result.retained(self, p.stdout)', 'pass'),
            'checkpoint-getter': ('n71_held_session.py', 'N71_HELD_SESSION_SCRIPT', 'command += n71_iommu_result.getter(session)', "command += ''"),
            'snapshot-selection': ('n71_held_session.py', 'N71_HELD_SESSION_SCRIPT', 'n71_iommu_result.snapshot(session, raw, pcie)', 'pass'),
            'resume-drift': ('n71_held_session.py', 'N71_HELD_SESSION_SCRIPT', 'n71_iommu_result.resume(session, live, prior)', 'pass'),
            'cleanup-gate': ('n71_held_session.py', 'N71_HELD_SESSION_SCRIPT', 'iommu_cleanup = n71_iommu_result.cleanup(session, proof)', 'iommu_cleanup = None'),
            'saved-cleanup': ('n71_held_session.py', 'N71_HELD_SESSION_SCRIPT', "result.get('iommu_cleanup') == iommu_proof", 'True'),
            'pre-scan-resources': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "== dict.fromkeys(n71_resource_stage.n71_resource_result.FIELDS, 0) | {'error': primary}", "!= {}"),
            'pre-scan-error': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'int(acquired.group(1)) == primary', 'True'),
            'pre-scan-order': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "text.index('N71_DART_CYCLE_RELEASED ') < reset.start() < power.start() < finished[-1].start()", 'True'),
            'unattempted-restore-index': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "'16' if pending else '0'", "'16'"),
            'proof-tier': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "'wifi_verified': False", "'wifi_verified': True"),
            'weak-binding': ('n71_iommu_build.py', 'N71_IOMMU_BUILD_SCRIPT',
                             "audit['vmlinux_symbol_binding'] == {'pci_for_each_dma_alias': 'T', 'pci_real_dma_dev': 'W'}", 'True'),
            'source-premises': ('n71_iommu_build.py', 'N71_IOMMU_BUILD_SCRIPT',
                                "audit['source_commit'] == build['source_commit'] == '958481f87fee0949ff6a9a4af77f7eb6dac8a149'", 'True'),
            'override-premises': ('n71_iommu_build.py', 'N71_IOMMU_BUILD_SCRIPT', "audit['arm64_real_dma_override_files'] == []", 'True'),
            'group-api-premises': ('n71_iommu_build.py', 'N71_IOMMU_BUILD_SCRIPT',
                                  "audit['exported_group_apis'] == ['iommu_group_get', 'iommu_group_put', 'iommu_group_id']", 'True'),
            'alias-api-premises': ('n71_iommu_build.py', 'N71_IOMMU_BUILD_SCRIPT',
                                  "audit['unexported_alias_helpers'] == ['pci_for_each_dma_alias', 'pci_real_dma_dev']", 'True'),
            'module-group-api': ('n71_iommu_build.py', 'N71_IOMMU_BUILD_SCRIPT', "build['exported_group_apis_present'] is True", 'True'),
            'module-alias-api': ('n71_iommu_build.py', 'N71_IOMMU_BUILD_SCRIPT', "build['unexported_alias_helpers_not_referenced'] is True", 'True'),
            'dma-marker-count': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT',
                                 'require(len(rows) == text.count(marker) == 2\n            and [row.groups()[:3]',
                                 'require(len(rows) == 2\n            and [row.groups()[:3]'),
            'dma-requester': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT',
                              "[row.groups()[:3] for row in rows] == [('0', '08', '0008'), ('1', '00', '0100')]", 'True'),
            'dma-alias-set': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', "root[3] == '1' and endpoint[3] in ('1', '2')", 'True'),
            'dma-shared-group': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', 'root[4] == endpoint[4]', 'True'),
            'dma-group-bound': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT', '0 <= int(root[4]) <= 2147483647', 'True'),
            'dma-mask': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT',
                         "all(row[5:] == ('00000000ffffffff', '00000000ffffffff') for row in (root, endpoint))", 'True'),
            'dma-position': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT',
                             'scans[0][index].start(), dma_rows[index].start(),', 'scans[0][index].start(),'),
            'dma-proof-tier': ('n71_iommu_result.py', 'N71_IOMMU_RESULT_SCRIPT',
                               "'physical_translation_verified': False", "'physical_translation_verified': True"),
        }
        with tempfile.TemporaryDirectory(prefix='n71-iommu-mutations-') as directory:
            for name, (filename, variable, before, after) in variants.items():
                source=(ROOT / 'scripts/host' / filename).read_text()
                self.assertEqual(source.count(before), 1, name)
                path=Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                environment=dict(os.environ, N71_IOMMU_MUTATION_CHILD='1', PYTHONDONTWRITEBYTECODE='1')
                environment[variable]=str(path)
                process=subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                                        '-p', 'test_n71_iommu_result.py', '-k', 'IommuResultTests'],
                                       env=environment, capture_output=True, text=True, timeout=35)
                output=process.stdout + process.stderr
                self.assertNotEqual(process.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_IOMMU_RESULT_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
