"""Real CLI cycles with isolated firmware transport and modeled PCI/WCC."""
import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import test_n71_iommu_result as iommu_fixture
import test_n71_driver_module_stage as module_fixture
import test_n71_driver_runtime_stage as native_fixture
import test_n71_driver_runtime_result as result_fixture
import test_n71_resource_pref64 as assignment_fixture
import test_n71_firmware_runtime_integration as firmware_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_cli as CLI
import n71_driver_runtime_session as coordinator
import n71_driver_reacquire as reacquire
import n71_held_session as held
import n71_driver_runtime_stage as native
import n71_session_history as history
import n71_resource_stage as resources
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_cli.py'
ENTRY = ROOT / 'scripts/host/n71-runtime-session.py'

REAL_RUN = subprocess.run
REAL_HELD_RUN = held.run
REAL_COORDINATOR_RUN = coordinator.run
TIMESTAMP = iommu_fixture.held_fixture.timestamp


class CyclePhone(iommu_fixture.IommuPhone):
    def __init__(self, test, firmware):
        super().__init__()
        self.test = test; self.firmware = firmware; self.cycles = 0; self.sessions = []
        self.wcc = module_fixture.ModuleJournalTests('test_ordered_load_and_reverse_unload_persist_only_the_proved_owners')
        self.wcc.present = set(); self.wcc.receipts = {}; self.wcc.calls = []; self.wcc.refs = {}
        self.wcc.exception = None; self.wcc.exit_code = 0; self.wcc.ssh_exit = None; self.wcc.complete_receipt = True
        self.wcc.current_driver = dict(native_fixture.INITIAL)
        self.overrides['pcie'] = self.acquired_cycle
        self.overrides['held-assign'] = self.assigned_cycle
        self.overrides['held-cleanup'] = self.cleaned_cycle

    def attach(self, session):
        self.sessions.append(session)
        session.ssh = [sys.executable, str(self.firmware.root / 'transport-private.py')]
        session.capture = lambda name, command, raw=None: self.capture(session, name, command, raw)
        self.wcc.session = session; self.wcc.output = session.output
        self.wcc.journal = SimpleNamespace(path=session.output / 'held-state-private.json')

    def acquired_cycle(self, phone, session, text):
        code, _ = iommu_fixture.IommuPhone.acquired(phone, session, text)
        self.history = self.previous + self.history.removeprefix(iommu_fixture.held_fixture.BASELINE)
        return code, iommu_fixture.getters() + 'N71_PCIE_HELD held=1\n' + self.status + self.history + self.native_getter()

    def cleaned_cycle(self, phone, session, text):
        self.test.assertFalse(self.wcc.present, 'PCI cleanup preceded WCC unload')
        self.test.assertFalse(self.wcc.current_driver['pending'], 'PCI cleanup preceded native release')
        self.test.assertIn(self.firmware.parameter.read_bytes(), (b'', b'\0'), 'PCI cleanup preceded firmware restoration')
        self.wcc.current_driver = dict.fromkeys(native.result.FIELDS, 0) | {'requested': 1}
        code, value = iommu_fixture.IommuPhone.cleaned(phone, session, text)
        return code, 'N71_BOOT_ID ' + self.boot + '\n' + value + self.native_getter()

    def assigned_cycle(self, phone, session, text):
        stamp = 60 + self.cycles * 10000
        prior = TIMESTAMP(iommu_fixture.resource_fixture.resource_fixture.RESULT, stamp)
        reports = assignment_fixture.POSITIVE.removeprefix(assignment_fixture.HELD)
        self.history = self.history.replace(prior, TIMESTAMP(reports, stamp))
        return 0, 'N71_PCIE_RESOURCE_ACTION exit=0\n' + self.getter() + 'N71_PCIE_HELD held=1\n' + self.status + self.history

    def native_getter(self):
        return (native.state_text(self.wcc.current_driver)
            + result_fixture.allocation_row({'ready': int(self.held), 'held': int(self.held), 'error': self.assignment_error}))

    def snapshot(self, session):
        value = super().snapshot(session)
        self.wcc.kernel_history = self.history
        text = self.wcc.text()
        wire = text[text.index(module_fixture.MODULES.IDENTITY):text.index('N71_WLAN_REGISTERED=')]
        wire += 'N71_WLAN_REGISTERED=' + str(int('brcmfmac' in self.wcc.present)) + '\n'
        wire += ''.join(line + '\n' for line in text.splitlines()
            if line.startswith(('N71_WLAN_STARTED ', 'N71_WLAN_EXIT ', 'N71_WLAN_RECEIPT_MISSING')))
        return value + wire + (self.native_getter() if self.pcie else '')

    def save(self, session, stage, value, code=0):
        path = session.output / (stage + '-private.log')
        with path.open('x') as log: log.write(value + '\nSTDERR\nprivate cycle capture\n')
        path.chmod(0o600)
        return SimpleNamespace(returncode=code, stdout=session.history.fresh(value) if session.history and stage != 'preflight' else value)

    def sync_stack(self):
        for name in module_fixture.MODULES.OBSERVED:
            path = self.firmware.phone / 'sys/module' / name
            if name in self.wcc.present: path.mkdir(exist_ok=True)
            elif path.exists(): path.rmdir()
        registry = self.firmware.phone / 'sys/bus/pci/drivers/brcmfmac'
        if 'brcmfmac' in self.wcc.present: registry.mkdir(exist_ok=True)
        elif registry.exists(): registry.rmdir()

    def capture(self, session, stage, command, raw=None):
        self.wcc.session = session; self.wcc.output = session.output
        self.wcc.journal = SimpleNamespace(path=session.output / 'held-state-private.json')
        self.wcc.kernel_history = self.history
        if stage.startswith(('firmware-', 'transfer-', 'hash-')) or stage in ('module-directory', 'runtime-stack-empty', 'reacquire-empty'):
            self.calls.append((stage, command))
            with contextlib.redirect_stdout(io.StringIO()):
                return firmware_fixture.firmware_fixture.LINK.Session.capture(session, stage, command, raw)
        if stage.startswith('driver-runtime-'):
            self.calls.append((stage, command))
            entry = json.loads((session.output / 'held-state-private.json').read_text())['driver_runtime_journal'][-1]
            self.test.assertIsNone(entry['completion'], 'Native action preceded durable intent')
            action = entry['action']; state = dict(self.wcc.current_driver)
            if action == 'prepare': state.update(dict.fromkeys(('pending',) + native.result.OWNERS, 1))
            elif action == 'publish': state.update(published=1, reads=7)
            else: state.update(dict.fromkeys(('pending',) + native.result.OWNERS, 0)); state['reads'] += 2
            self.wcc.current_driver = state
            self.history += native_fixture.native(action, state, {'stamp': self.cycles * 10000 + 300 + len(self.calls)})
            return self.save(session, stage, native_fixture.snapshot(state, self.history, {'action': action, 'exit_value': 0}))
        if stage.startswith('wlan-module-') and not stage.endswith('-after'):
            self.calls.append((stage, command))
            entry = session.driver_module_journal[-1]
            if entry['action'] == 'load':
                self.test.assertEqual(self.firmware.parameter.read_bytes(),
                    (str(self.firmware.phone) + session.module_directory + '/firmware').encode(), 'WCC load preceded firmware binding')
            value = self.wcc.capture(stage, command); self.sync_stack()
            return value
        if stage.startswith(('held-checkpoint-', 'runtime-', 'wlan-module-')) or stage in ('held-acquire-live', 'held-resume-live', 'held-failure-live', 'reacquire-stopped-current'):
            self.calls.append((stage, command))
            with patch.object(iommu_fixture.held_fixture, 'timestamp', lambda text, start: TIMESTAMP(text, start + self.cycles * 10000)):
                return self.save(session, stage, self.snapshot(session))
        if stage == 'pci-empty':
            self.calls.append((stage, command)); self.test.assertTrue(self.empty)
            return self.save(session, stage, 'N71_PCI_PREFLIGHT_EMPTY\n')
        if stage == 'pcie':
            self.previous = self.history; self.cycles += 1
            self.status = iommu_fixture.held_fixture.ACTIVE
            self.resources = dict(iommu_fixture.resource_fixture.STAGE.INITIAL)
            self.removed = self.configured = self.pme_tls_restored = False
            self.wcc.current_driver = dict(native_fixture.INITIAL)
        with patch.object(iommu_fixture.held_fixture, 'timestamp', lambda text, start: TIMESTAMP(text, start + self.cycles * 10000)):
            process = super().capture(session, stage, command, raw)
        if stage in ('held-pcie-unload', 'held-restore', 'held-reg-unload'):
            path = session.output / (stage + '-private.log')
            prefix = 'N71_BOOT_ID ' + self.boot + '\n'
            path.write_text(prefix + path.read_text()); process.stdout = prefix + process.stdout
        if stage == 'preflight':
            process.stdout = (session.output / (stage + '-private.log')).read_text().split('\nSTDERR\n', 1)[0]
        return process


def setup(test, subject):
    fixture = firmware_fixture.FirmwareIntegrationTests('test_start_observe_stop_order_one_boot_and_source_immutability')
    fw, case, package = fixture.cli_case()
    test.addCleanup(fixture.doCleanups)
    phone = CyclePhone(test, fw)
    (fw.phone / 'proc/sys/kernel/random/boot_id').write_text(phone.boot + '\n')
    link_loader = subject.link_module
    def link(root):
        module = link_loader(root); session_type = module.Session
        module.n71_driver_firmware_session = fw.subject
        def session(*args, **kwargs):
            value = session_type(*args, **kwargs); phone.attach(value); return value
        module.Session = session
        return module
    def transport(args, **options):
        test.assertEqual(args[:2], [sys.executable, str(fw.root / 'transport-private.py')], 'Process escaped isolated firmware transport')
        return REAL_RUN(args, **options)
    for hook in (patch.object(subject, 'link_module', link), patch.object(subject, 'firmware', fw.subject),
        patch.object(subject.held, 'run', REAL_HELD_RUN), patch.object(subject.coordinator, 'run', REAL_COORDINATOR_RUN),
        patch.object(coordinator, 'firmware', fw.subject), patch.object(reacquire, 'firmware', fw.subject),
        patch.object(subprocess, 'run', side_effect=transport)):
        hook.start(); test.addCleanup(hook.stop)
    return fw, case, package, phone


class ReacquireCliTests(unittest.TestCase):
    subject = CLI

    def setUp(self):
        self.fw, self.case, self.package, self.phone = setup(self, self.subject)
        self.source = None; self.outputs = []

    def invoke(self, action, options=None):
        options = options or {}
        request = self.case.request(action, check=options.get('check', False))
        request['source'] = None if action == 'acquire' else options.get('source', self.source)
        if options.get('firmware', True): request['firmware'] = self.package
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = self.subject.run(self.case.root, request)
        if code == 0 and not request['check']:
            self.source = request['output']; self.outputs.append(self.source)
        return code, output.getvalue()

    def accepted(self, action, options=None):
        try: code, text = self.invoke(action, options)
        except (ValueError, OSError) as error: self.fail('Qualified runtime cycle refused: ' + str(error))
        self.assertEqual(code, 0, text)
        return self.phone.sessions[-1]

    def cycle(self, acquire='acquire'):
        self.accepted(acquire)
        self.accepted('assign')
        self.accepted('start')
        self.accepted('observe')
        return self.accepted('stop')

    def files(self, directory):
        return {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}

    def state(self):
        return json.loads((self.source / 'held-state-private.json').read_text())

    def test_two_complete_cli_cycles_share_boot_and_preserve_distinct_evidence(self):
        # Mutations: omit preparation, reuse stopped source as acquisition or inherit old owners/journals.
        first = self.cycle(); origin = self.source; before = self.files(origin); data = self.state()
        prior = history.read_private(origin, data['checkpoint']['name'])
        second = self.cycle('reacquire'); final = self.state()
        self.assertEqual(self.phone.cycles, 2); self.assertEqual(self.phone.assignments, 2)
        self.assertEqual(first.result['boot_id'], second.result['boot_id'])
        self.assertNotEqual(first.module_directory, second.module_directory)
        self.assertEqual(len(self.outputs), len(set(self.outputs)))
        self.assertEqual(final['baseline'], history.kernel_lines(prior))
        self.assertEqual([e['action'] for e in final['driver_runtime_journal']], ['prepare', 'publish', 'release'])
        self.assertEqual(len(final['driver_module_journal']), 10)
        self.assertEqual(final['result']['driver_coordinator'], dict(action='stop', phase='stopped', primary_error=0, successful=True))
        lineage = final['result'].get('reacquire_lineage'); self.assertIsInstance(lineage, dict)
        self.assertEqual(lineage['source'], str(origin)); self.assertEqual(lineage['previous_primary_error'], 0)
        self.assertEqual(lineage['previous_module_directory'], first.module_directory)
        self.assertEqual(final['result'][self.fw.subject.KEY]['directory'], second.module_directory + '/firmware')
        self.assertEqual(final['result'][self.fw.subject.KEY]['path'], 'restored')
        self.assertEqual(self.fw.parameter.read_bytes(), b'\0')
        self.assertEqual(before, self.files(origin)); self.assertFalse(self.phone.pcie or self.phone.reg or self.phone.wcc.present)
        raw = history.read_private(self.source, final['checkpoint']['name'])
        self.assertEqual(sum('N71_PCIE_DRIVER_RESULT action=prepare ' in row for row in history.kernel_lines(raw)), 2)
        self.assertEqual(sum('N71_PCIE_DRIVER_RESULT action=prepare ' in row for row in final['driver_runtime_journal'][0]['history']), 1)
        self.assertFalse(any('reboot' in command or 'osascript' in command for _, command in self.phone.calls))
        self.accepted('reacquire', {'check': True})
        self.assertEqual(before, self.files(origin)); self.assertEqual(self.phone.cycles, 2)

    def test_cleanup_view_preserves_originals_and_rejects_changed_prefixes(self):
        # Mutations: discard baseline guards or normalize the authoritative native journal in place.
        self.cycle(); session = self.phone.sessions[-1]
        proof = history.read_private(self.source, 'pcie-cleanup-proof-private.log')
        import copy
        ledger = copy.deepcopy(session.driver_runtime_journal); prefix = list(session.history.lines)
        view, text = resources.cleanup_view(session, proof)
        self.assertEqual(session.driver_runtime_journal, ledger); self.assertEqual(session.history.lines, prefix)
        self.assertEqual(view.driver_runtime_journal[0]['history'], ledger[0]['history'][len(prefix):])
        self.assertEqual(history.kernel_lines(text), history.kernel_lines(proof)[len(prefix):])
        with self.assertRaises(ValueError): resources.cleanup_view(session, proof.replace(prefix[0] + '\n', '', 1))
        session.driver_runtime_journal = copy.deepcopy(ledger)
        session.driver_runtime_journal[0]['history'] = ledger[0]['history'][1:]
        try:
            with self.assertRaises(ValueError): resources.cleanup_view(session, proof)
        finally: session.driver_runtime_journal = ledger

    def test_real_entry_local_check_creates_no_output_or_transport(self):
        # Mutations: perform effects in check, bypass stopped validation or omit reacquire from argparse choices.
        self.cycle(); source = self.source; before = self.files(source); count = len(self.phone.calls)
        request = dict(self.case.request('reacquire'), source=source, firmware=self.package)
        request['check'] = True; request['output'] = None
        try:
            with contextlib.redirect_stdout(io.StringIO()) as text:
                self.assertEqual(self.subject.run(self.case.root, request), 0)
        except (ValueError, OSError) as error: self.fail('Qualified local reacquire gate refused: ' + str(error))
        self.assertIn('N71_RUNTIME_LOCAL_GATE_OK', text.getvalue())
        spec = importlib.util.spec_from_file_location('reacquire_entry', ENTRY)
        entry = importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
        entry.__file__ = str(self.case.root / 'scripts/host/n71-runtime-session.py'); entry.runtime = self.subject
        args = ['n71-runtime-session.py', '--profile', str(self.case.profile), '--source', str(source),
            '--firmware-dir', str(self.package), '--action', 'reacquire', '--check']
        try:
            with patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()): self.assertEqual(entry.main(), 0)
        except (ValueError, OSError, SystemExit) as error: self.fail('Qualified reacquire entry refused: ' + str(error))
        self.assertEqual(before, self.files(source)); self.assertEqual(count, len(self.phone.calls))
        self.assertEqual(self.phone.cycles, 1); self.assertEqual(len(self.outputs), 5)

    def test_source_is_mandatory_and_active_or_incomplete_cleanup_refuses(self):
        # Mutations: omit source scope or let a running/incomplete source authorize another acquisition.
        with self.assertRaises(ValueError): self.invoke('reacquire')
        self.accepted('acquire'); before = self.files(self.source); effects = self.phone.cycles
        with self.assertRaises(ValueError): self.invoke('reacquire')
        self.assertEqual(before, self.files(self.source)); self.assertEqual(self.phone.cycles, effects)
        self.accepted('stop'); source = self.source; data = self.state()
        data['result']['cleanup_verified'] = False
        (source / 'held-state-private.json').write_text(json.dumps(data) + '\n')
        with self.assertRaises(ValueError): self.invoke('reacquire', {'check': True})
        self.assertEqual(self.phone.cycles, effects)

    def test_boot_or_history_drift_refuses_before_new_acquisition(self):
        # Mutations: skip same-boot and history validation before effects.
        self.cycle(); origin = self.source; before = self.files(origin); initial = self.phone.history
        for change in ('history', 'boot'):
            if change == 'history': self.phone.history = initial + '[ 90000.000000] N71_UNREGISTERED_ACTION\n'
            else: self.phone.boot = '87654321-1234-1234-1234-123456789abc'
            with self.assertRaises(ValueError): self.invoke('reacquire')
            self.assertEqual(self.phone.cycles, 1); self.assertEqual(before, self.files(origin))
            self.phone.history = initial; self.phone.boot = native_fixture.BOOT

    def test_firmware_reselection_is_required_and_environment_restores_on_refusal(self):
        # Mutations: silently reuse old firmware metadata or leak profile/umask after refusal.
        self.cycle(); count = len(self.phone.calls)
        import os
        previous = os.environ.get('IPHONE_LINUX_PROFILE'); mask = os.umask(0o022)
        try:
            with self.assertRaises(ValueError): self.invoke('reacquire', {'firmware': False, 'check': True})
            self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'), previous)
            current = os.umask(0o022); self.assertEqual(current, 0o022)
        finally: os.umask(mask)
        self.assertEqual(len(self.phone.calls), count); self.assertEqual(self.phone.cycles, 1)


class ReacquireCliMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReacquireCliTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        source = SOURCE.read_text()
        cases = [
            ('prepare', "reacquire.prepare(session, {'root': root, 'source': request['source'],\n                'identity': identity, 'check': request['check']})", 'pass', 'test_two_complete_cli_cycles_share_boot_and_preserve_distinct_evidence'),
            ('fresh-acquire', 'source=None, assign=False', "source=request['source'], assign=False", 'test_two_complete_cli_cycles_share_boot_and_preserve_distinct_evidence'),
            ('check-propagation', "'identity': identity, 'check': request['check']", "'identity': identity, 'check': False", 'test_real_entry_local_check_creates_no_output_or_transport'),
            ('check-new-output', "if not request['check']:", 'if True:', 'test_real_entry_local_check_creates_no_output_or_transport'),
            ('reacquire-choice', "'stop', 'reacquire')", "'stop')", 'test_real_entry_local_check_creates_no_output_or_transport'),
        ]
        for name, before, after, method in cases:
            with self.subTest(name=name):
                self.assertEqual(source.count(before), 1, name)
                module = ModuleType('reacquire_cli_mutant'); module.__file__ = str(SOURCE)
                exec(compile(ast.parse(source.replace(before, after, 1)), str(SOURCE), 'exec'), module.__dict__)
                case = type('MutatedReacquireCliTests', (ReacquireCliTests,), {'subject': module})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name); self.assertGreater(len(result.failures), 0, name)
        path = ROOT / 'scripts/host/n71_resource_stage.py'; source = path.read_text()
        mutations = [
            ('baseline-prefix', "n71_session_history.kernel_lines(text)[:len(prefix)] == prefix", 'True'),
            ('native-prefix', "entry['history'][:len(prefix)] == prefix", 'True'),
            ('native-view-history', "dict(entry, history=entry['history'][len(prefix):])", 'entry'),
        ]
        for name, before, after in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(before), 1, name)
                module = ModuleType('resource_cycle_mutant'); module.__file__ = str(path)
                exec(compile(ast.parse(source.replace(before, after, 1)), str(path), 'exec'), module.__dict__)
                with patch.dict(sys.modules, {'n71_resource_stage': module}), patch.object(held, 'n71_resource_stage', module), patch.object(CLI, 'reacquire', reacquire):
                    original = globals()['resources']; globals()['resources'] = module
                    try:
                        result = unittest.TextTestRunner(stream=io.StringIO()).run(ReacquireCliTests('test_cleanup_view_preserves_originals_and_rejects_changed_prefixes'))
                    finally: globals()['resources'] = original
                self.assertEqual(result.errors, [], name); self.assertGreater(len(result.failures), 0, name)
