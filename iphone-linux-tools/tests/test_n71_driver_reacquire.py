"""Stopped journals authorize a new cycle without migrating previous owners."""
import ast
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
import test_n71_driver_runtime_session as runtime_fixture
import test_n71_driver_firmware_session as firmware_fixture
import test_n71_runtime_unassigned_stop as unassigned_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_reacquire as REACQUIRE
SOURCE = ROOT / 'scripts/host/n71_driver_reacquire.py'


class ReacquireTests(unittest.TestCase):
    subject = REACQUIRE

    def setUp(self):
        self.rt = runtime_fixture.RuntimeSessionTests('test_start_observe_and_stop_share_one_boot_and_preserve_origin')
        self.rt.setUp(); self.addCleanup(self.rt.doCleanups)
        self.fw = firmware_fixture.FirmwareSessionTests('test_stage_bind_verify_restore_in_one_boot_and_keep_private_data')
        self.fw.setUp(); self.addCleanup(self.fw.doCleanups)
        hook = patch.object(self.subject, 'firmware', self.fw.subject)
        hook.start(); self.addCleanup(hook.stop)
        self.serial = 0; self.calls = []

    def stopped(self, complete=False):
        if complete: self.rt.accepted('start')
        self.rt.accepted('stop')
        self.source = self.rt.source
        self.before = self.bytes(self.source)
        return self.fresh()

    def bytes(self, directory):
        return {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}

    def fresh(self):
        self.serial += 1
        output = self.rt.root / 'runtime' / ('reacquire-' + str(self.serial)); output.mkdir(mode=0o700)
        session = self.rt.case.restored(output)
        session.scan_hold = True; session.history = None; session.resource_assignment = None
        session.module_directory = '/run/n71-link-' + format(self.serial, '024x')
        session.ssh = [sys.executable, str(self.fw.root / 'transport-private.py')]
        session.capture = self.capture
        self.session = session
        self.rt.session = self.rt.case.session = self.rt.life.session = self.rt.phone.session = session
        previous = json.loads((self.source / 'held-state-private.json').read_text())
        old = previous['module_directory']
        (self.fw.phone / old.lstrip('/')).mkdir(mode=0o700, parents=True, exist_ok=True)
        (self.fw.phone / 'proc/sys/kernel/random/boot_id').write_text(previous['result']['boot_id'] + '\n')
        return session

    def capture(self, name, command):
        self.calls.append((name, command))
        self.assertNotIn('insmod ', command); self.assertNotIn('rmmod ', command)
        self.assertNotIn('printf %s ', command); self.assertNotIn("printf '\\000'", command)
        if name == 'reacquire-empty':
            with contextlib.redirect_stdout(io.StringIO()):
                return firmware_fixture.LINK.Session.capture(self.session, name, command)
        return self.rt.capture(name, command)

    def request(self, check=False):
        return {'root': self.rt.root, 'source': self.source, 'identity': {'modules': {}}, 'check': check}

    def accepted(self, check=False):
        try: return self.subject.prepare(self.session, self.request(check))
        except (ValueError, OSError) as error: self.fail('Proved stopped source refused: ' + str(error))

    def rewrite_state(self, change):
        path = self.source / 'held-state-private.json'; data = json.loads(path.read_text())
        change(data); path.write_text(json.dumps(data) + '\n')

    def test_complete_stop_prepares_only_history_lineage_and_preserves_raw_source(self):
        # Mutations: omit lineage/history, migrate old owners, or strip evidence from raw captures.
        self.stopped(complete=True); initial = dict(self.session.__dict__)
        lineage = self.accepted()
        data = json.loads((self.source / 'held-state-private.json').read_text())
        self.assertEqual(lineage, {'source': str(self.source),
            'state_sha256': hashlib.sha256(self.before['held-state-private.json']).hexdigest(),
            'previous_boot_id': data['result']['boot_id'], 'previous_module_directory': data['module_directory'],
            'previous_primary_error': 0})
        self.assertEqual(self.session.result, dict(initial['result'], reacquire_lineage=lineage))
        for name in initial.keys() - {'result', 'history'}: self.assertEqual(getattr(self.session, name), initial[name])
        text = self.subject.history.read_private(self.source, data['checkpoint']['name'])
        self.session.history.verify_live(text)
        tail = '[ 9000.000000] N71_NEW_CYCLE marker\n'
        filtered = self.session.history.fresh(text + tail)
        self.assertIn(tail, filtered); self.assertFalse(self.subject.history.kernel_lines(text)[0] in filtered)
        raw = self.session.output / 'reacquire-stopped-current-private.log'
        self.assertIn(self.subject.history.kernel_lines(text)[0], raw.read_text())
        self.assertEqual(self.before, self.bytes(self.source))
        self.assertEqual([name for name, _ in self.calls], ['reacquire-stopped-current', 'reacquire-empty'])

    def test_check_only_keeps_session_and_files_unchanged_without_capture(self):
        # Mutation: perform a probe or install history during the local check gate.
        self.stopped(); self.session.output = self.rt.root / 'runtime'
        initial = copy.deepcopy(self.session.result); attributes = dict(self.session.__dict__)
        files = {str(p): p.read_bytes() for p in self.rt.root.rglob('*') if p.is_file()}
        self.assertEqual(self.accepted(check=True)['previous_primary_error'], 0)
        self.assertEqual(self.calls, []); self.assertEqual(self.session.__dict__, attributes)
        self.assertEqual(self.session.result, initial)
        self.assertEqual(files, {str(p): p.read_bytes() for p in self.rt.root.rglob('*') if p.is_file()})

    def test_incomplete_cleanup_summary_or_proof_refuses_and_restores_attributes(self):
        # Mutations: accept a missing cleanup receipt, pending teardown or an inconsistent summary.
        self.stopped(); original = self.before['held-state-private.json']
        changes = [lambda d: d['result'].update(cleanup_verified=False),
            lambda d: d['result'].update(cleanup_errors=['unfinished']),
            lambda d: d['proofs'].pop('restore'),
            lambda d: d['result']['driver_coordinator'].update(phase='running'),
            lambda d: d['result']['driver_coordinator'].update(primary_error=-13),
            lambda d: d['result']['driver_coordinator'].update(successful=False)]
        for change in changes:
            (self.source / 'held-state-private.json').write_bytes(original); self.rewrite_state(change)
            attributes = dict(self.session.__dict__)
            with self.subTest(change=changes.index(change)), self.assertRaises(ValueError):
                self.subject.prepare(self.session, self.request(check=True))
            self.assertEqual(self.session.__dict__, attributes)
        self.assertEqual(self.calls, [])

    def test_current_boot_history_drift_or_transport_error_restores_new_session(self):
        # Mutations: relax same-boot/prefix equality or omit finally restoration on probe failure.
        self.stopped(); original = self.rt.text
        base = original(); boot = json.loads(self.before['held-state-private.json'])['result']['boot_id']
        for text in (base.replace(boot, '87654321-1234-1234-1234-123456789abc'),
            base + '[ 9000.000000] N71_UNREGISTERED_ACTION\n',
            base.replace(self.subject.history.kernel_lines(base)[0] + '\n', '')):
            self.rt.text = lambda: text; attributes = dict(self.session.__dict__)
            with self.assertRaises(ValueError): self.subject.prepare(self.session, self.request())
            self.assertEqual(self.session.__dict__, attributes); self.assertEqual(self.before, self.bytes(self.source))
            self.fresh()
        self.rt.text = original
        attributes = dict(self.session.__dict__)
        with patch.object(self.subject.held, 'snapshot', side_effect=OSError('transport unavailable')):
            with self.assertRaises(OSError): self.subject.prepare(self.session, self.request())
        self.assertEqual(self.session.__dict__, attributes)

    def test_readonly_guard_refuses_foreign_stack_path_registry_and_modes(self):
        # Mutations: skip the actual empty-stack/path/header shell guards.
        self.stopped()
        module = self.fw.phone / 'sys/module/rfkill_gpio'
        driver = self.fw.phone / 'sys/bus/pci/drivers/brcmfmac'
        cases = [(lambda: module.mkdir(), lambda: module.rmdir()),
            (lambda: driver.mkdir(), lambda: driver.rmdir()),
            (lambda: self.fw.parameter.write_bytes(b'/foreign'), lambda: self.fw.parameter.write_bytes(b'')),
            (lambda: self.fw.parameter.chmod(0o666), lambda: self.fw.parameter.chmod(0o644))]
        for change, restore in cases:
            change(); attributes = dict(self.session.__dict__)
            with self.assertRaises(ValueError): self.subject.prepare(self.session, self.request())
            self.assertEqual(self.session.__dict__, attributes); self.assertEqual(self.before, self.bytes(self.source))
            restore(); self.fresh()

    def test_rechecks_source_bytes_after_probe_and_at_later_preflight(self):
        # Mutation: omit source hash rechecks at the probe or new preflight boundary.
        self.stopped(); capture = self.capture
        target = self.source / 'reg-unload-proof-private.log'; original = target.read_bytes()
        def race(name, command):
            process = capture(name, command)
            if name == 'reacquire-empty': target.write_bytes(original + b'\nSTDERR\nchanged\n')
            return process
        self.session.capture = race; attributes = dict(self.session.__dict__)
        with self.assertRaises(ValueError): self.subject.prepare(self.session, self.request())
        self.assertEqual(self.session.__dict__, attributes)
        target.write_bytes(original); self.fresh(); self.accepted()
        text = self.rt.text(); self.session.history.verify_live(text)
        boot = self.session.history.boot_id
        for changed in (text + '[ 9000.000000] N71_UNREGISTERED_ACTION\n',
            text.replace(boot, '87654321-1234-1234-1234-123456789abc')):
            with self.assertRaises(ValueError): self.session.history.verify_live(changed)
        target.write_bytes(original + b'changed')
        with self.assertRaises(ValueError): self.session.history.verify_live(text)
        target.write_bytes(original); target.chmod(0o644)
        with self.assertRaises(ValueError): self.session.history.verify_live(text)

    def test_fresh_selection_exclusive_paths_and_identity_refuse_before_capture(self):
        # Mutations: accept another profile, unsafe source/output or a previously used session.
        self.stopped(); initial = dict(self.session.__dict__)
        for key, value in [('scan_hold', False), ('resource_attempted', True), ('history', object()),
            ('module_directory', json.loads(self.before['held-state-private.json'])['module_directory']),
            ('output', self.source), ('driver_runtime_journal', [{'completion': None}])]:
            setattr(self.session, key, value)
            with self.subTest(key=key), self.assertRaises(ValueError): self.subject.prepare(self.session, self.request(True))
            self.session.__dict__.clear(); self.session.__dict__.update(initial)
        for request in [dict(self.request(True), identity={'modules': {'different': True}}),
            dict(self.request(True), check=1), dict(self.request(True), source=self.rt.root),
            dict(self.request(True), extra=True)]:
            with self.assertRaises(ValueError): self.subject.prepare(self.session, request)
        self.source.chmod(0o755)
        with self.assertRaises(ValueError): self.subject.prepare(self.session, self.request(True))
        self.assertEqual(self.calls, [])

    def test_negative_prior_cause_and_unassigned_stop_are_valid_without_new_owners(self):
        # Mutation: erase the previous negative cause or require fabricated assignment/native journals.
        self.rt.test_negative_assignment_is_observed_and_stopped_without_becoming_success()
        self.source = self.rt.source; self.fresh(); self.assertEqual(self.accepted()['previous_primary_error'], -13)
        self.assertIsNone(self.session.resource_assignment); self.assertEqual(self.session.driver_runtime_journal, [])
        empty = unassigned_fixture.UnassignedStopTests('test_observe_stop_and_repeated_stop_preserve_one_boot_without_assignment')
        empty.setUp(); self.addCleanup(empty.doCleanups); empty.accepted('stop')
        self.rt = empty.phone; self.source = self.rt.source; self.fresh()
        self.assertEqual(self.accepted()['previous_primary_error'], 0); self.assertIsNone(self.session.resource_assignment)

    def test_previous_firmware_requires_restored_path_and_explicit_new_data(self):
        # Mutations: accept an un-restored loader path or omit explicit firmware reselection.
        self.stopped(); data = json.loads(self.before['held-state-private.json'])
        package = {'format': 1, 'boot_id': data['result']['boot_id'],
            'directory': data['module_directory'] + '/firmware', 'manifest': self.fw.subject.records(),
            'status': 'ready', 'path': 'bound'}
        self.rewrite_state(lambda d: d['result'].update(firmware_package=package))
        self.session.firmware_data = self.fw.session.firmware_data
        with self.assertRaises(ValueError): self.subject.prepare(self.session, self.request(True))
        package['path'] = 'restored'; self.rewrite_state(lambda d: d['result'].update(firmware_package=package))
        self.session.firmware_data = None
        with self.assertRaises(ValueError): self.subject.prepare(self.session, self.request(True))
        self.session.firmware_data = self.fw.session.firmware_data
        self.assertEqual(self.accepted()['previous_primary_error'], 0)
        self.assertEqual(self.session.firmware_data, self.fw.session.firmware_data)
        self.assertNotIn('firmware_package', self.session.result)


class ReacquireMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReacquireTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        source = SOURCE.read_text()
        cases = [
            ('cleanup', "data['result'].get('cleanup_verified') is True", 'True', 'test_incomplete_cleanup_summary_or_proof_refuses_and_restores_attributes'),
            ('summary', "summary['phase'] == 'stopped'", 'True', 'test_incomplete_cleanup_summary_or_proof_refuses_and_restores_attributes'),
            ('session-restoration', 'session.__dict__.update(initial)', 'pass', 'test_current_boot_history_drift_or_transport_error_restores_new_session'),
            ('guard-stack', 'firmware.empty_stack()', "''", 'test_readonly_guard_refuses_foreign_stack_path_registry_and_modes'),
            ('guard-path', "firmware.path_test('0a')", "''", 'test_readonly_guard_refuses_foreign_stack_path_registry_and_modes'),
            ('source-hash', 'hashlib.sha256(path.read_bytes()).hexdigest() == expected', 'True', 'test_rechecks_source_bytes_after_probe_and_at_later_preflight'),
            ('history', 'history.kernel_lines(text) == self.lines', 'True', 'test_rechecks_source_bytes_after_probe_and_at_later_preflight'),
            ('boot', "re.findall(r'^N71_BOOT_ID ([0-9a-f-]{36})$', text, re.M) == [self.boot_id]", 'True', 'test_rechecks_source_bytes_after_probe_and_at_later_preflight'),
            ('local-check', "if not request['check']:", 'if True:', 'test_check_only_keeps_session_and_files_unchanged_without_capture'),
            ('negative-lineage', "'previous_primary_error': primary", "'previous_primary_error': 0", 'test_negative_prior_cause_and_unassigned_stop_are_valid_without_new_owners'),
            ('fresh-directory', "session.module_directory != initial['module_directory']", 'True', 'test_fresh_selection_exclusive_paths_and_identity_refuse_before_capture'),
            ('firmware-reselect', 'firmware.selected(session)', 'pass', 'test_previous_firmware_requires_restored_path_and_explicit_new_data'),
            ('filter', 'if line not in self.known', 'if True', 'test_complete_stop_prepares_only_history_lineage_and_preserves_raw_source'),
        ]
        for name, before, after, method in cases:
            with self.subTest(name=name):
                if name != 'local-check': self.assertEqual(source.count(before), 1, name)
                module = ModuleType('reacquire_mutant')
                exec(compile(ast.parse(source.replace(before, after)), str(SOURCE), 'exec'), module.__dict__)
                case = type('MutatedReacquireTests', (ReacquireTests,), {'subject': module})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name); self.assertGreater(len(result.failures), 0, name)
