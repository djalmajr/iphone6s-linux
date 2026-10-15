"""Real journals and parsers coordinate a synthetic phone in one boot."""
import ast
import hashlib
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
import test_n71_runtime_unprepared_stop as initial_fixture
import test_n71_driver_runtime_stage as native_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_session as COORDINATOR
import n71_driver_runtime_stage as NATIVE
import n71_driver_module_stage as WLAN
import n71_held_session as HELD
import n71_session_history as HISTORY
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_session.py'


class RuntimeSessionTests(unittest.TestCase):
    subject = COORDINATOR

    def setUp(self):
        setup = initial_fixture.UnpreparedStopTests('test_stop_and_source_loader_prove_cleanup_without_inventing_native_actions')
        setup.setUp(); self.addCleanup(setup.doCleanups)
        self.setup = setup; self.case = setup.case; self.life = setup.life; self.phone = self.life.phone
        self.session = setup.session; self.root = self.life.root; self.origin = self.case.output
        self.calls = []; self.fail_module = None; self.transport_module = None; self.cleaned = False; self.serial = 0; self.race = False
        self.provider_tail = '\n'.join(HISTORY.kernel_lines(self.case.full_history)[len(HISTORY.kernel_lines(self.phone.kernel_history)):]) + '\n'
        self.cleanup_template = self.case.cleanup_proof; self.template_history = self.case.full_history
        self.session.capture = self.capture
        self.phone.journal.finish()
        self.source = self.origin

    def text(self):
        return self.case.removed_text() if self.cleaned else self.life.text()

    def capture(self, name, command):
        self.calls.append((name, command))
        if name.startswith('driver-runtime-'):
            saved = json.loads((self.session.output / 'held-state-private.json').read_text())
            entry = saved['driver_runtime_journal'][-1]
            self.assertIsNone(entry['completion'], 'Native effect preceded durable intent')
            action = entry['action']; state = dict(self.phone.current_driver)
            if action == 'prepare': state.update(dict.fromkeys(('pending',) + NATIVE.result.OWNERS, 1))
            elif action == 'publish': state.update(published=1, reads=7)
            else: state.update(dict.fromkeys(('pending',) + NATIVE.result.OWNERS, 0)); state['reads'] += 2
            self.phone.current_driver = state
            self.phone.kernel_history += native_fixture.native(action, state, {'stamp':20 + len(self.calls)})
            raw = native_fixture.snapshot(state, self.phone.kernel_history, {'action':action,'exit_value':0})
        elif name.startswith('wlan-module-') and not name.endswith('-after'):
            entry = self.session.driver_module_journal[-1]
            self.phone.exit_code = int(entry['name'] == self.fail_module)
            self.phone.exception = 'after' if entry['name'] == self.transport_module else None
            return self.phone.capture(name, command)
        elif name in ('held-cleanup','held-pci-empty','held-pcie-unload','held-restore','held-reg-unload'):
            if name == 'held-cleanup':
                self.assertFalse(self.phone.present, 'Provider cleanup preceded normal WCC unload')
                self.assertFalse(self.phone.current_driver['pending'], 'Provider cleanup preceded native release')
                self.phone.kernel_history += self.provider_tail; self.case.full_history = self.phone.kernel_history
                self.case.cleanup_proof = self.cleanup_template.replace(self.template_history, self.phone.kernel_history)
                self.cleaned = True
            return self.case.capture(name, command)
        else:
            self.assertNotIn('insmod ', command); self.assertNotIn('rmmod ', command)
            self.assertNotIn(' > ' + HELD.PCIE + 'action', command)
            if name == 'runtime-current' and self.race:
                with (self.source / 'resource-assignment-proof-private.log').open('a') as file: file.write('\nSTDERR\nchanged after source validation\n')
            if self.case.reg:
                self.phone.kernel_history += '[ ' + str(100 + len(self.calls)) + '.000000] N71_REG_ON_READ error=0 value_valid=1 value=' + ('81' if self.case.active else '80') + '\n'
            raw = self.text()
        path = self.session.output / (name + '-private.log')
        with path.open('x') as file: file.write(raw + '\nSTDERR\nprivate capture detail\n')
        path.chmod(0o600)
        return SimpleNamespace(returncode=0, stdout='filtered collector output')

    def run_action(self, action):
        self.serial += 1; output = self.root / 'runtime' / ('operation-' + str(self.serial)); output.mkdir(mode=0o700)
        self.session = self.case.restored(output)
        self.case.session = self.life.session = self.phone.session = self.session; self.phone.output = output
        self.phone.journal = SimpleNamespace(path=output / 'held-state-private.json'); self.session.capture = self.capture
        return self.subject.run(self.session, {'action':action,'root':self.root,'source':self.source,'identity':{'modules':{}}})

    def accepted(self, action):
        try: result = self.run_action(action)
        except (ValueError, OSError) as error: self.fail('Proved runtime session refused: ' + str(error))
        self.source = self.session.output
        return result

    def effects(self):
        return [name for name, _ in self.calls if name.startswith(('driver-runtime-','wlan-module-')) and not name.endswith('-after')
            or name in ('held-cleanup','held-pcie-unload','held-restore','held-reg-unload')]

    def test_start_observe_and_stop_share_one_boot_and_preserve_origin(self):
        # Mutations: reorder preparation/publication/cleanup or repeat an already proved start/stop effect.
        origin = {p.name:p.read_bytes() for p in self.origin.iterdir()}
        result = self.accepted('start')
        self.assertEqual(result, dict(action='start',phase='running',primary_error=0,successful=True))
        self.assertEqual(self.phone.present, set(WLAN.modules.NAMES)); self.assertTrue(self.case.active and self.case.pcie and self.case.reg)
        effects = self.effects(); self.assertEqual(len(effects), 7)
        for action in ('observe','start'):
            result = self.accepted(action); self.assertEqual(result['phase'], 'running'); self.assertEqual(self.effects(), effects)
        result = self.accepted('stop'); self.assertEqual(result['phase'], 'stopped'); self.assertTrue(result['successful'])
        self.assertFalse(self.phone.present or self.case.active or self.case.pcie or self.case.reg)
        self.assertEqual([entry['action'] for entry in self.session.driver_runtime_journal], ['prepare','publish','release'])
        self.assertEqual([entry['name'] for entry in self.session.driver_module_journal[5:]], list(reversed(WLAN.modules.NAMES)))
        self.assertEqual(self.session.result['boot_id'], native_fixture.BOOT)
        effects = self.effects()
        for action in ('observe','stop'):
            self.assertEqual(self.accepted(action)['phase'], 'stopped'); self.assertEqual(self.effects(), effects)
        self.assertEqual(origin, {p.name:p.read_bytes() for p in self.origin.iterdir()})

    def test_complete_failed_load_resumes_only_the_missing_prefix(self):
        # Mutation: reload the already owned prefix or publish before the full WCC stack.
        self.fail_module = WLAN.modules.NAMES[2]
        with self.assertRaises(ValueError): self.run_action('start')
        self.assertEqual(self.phone.present, set(WLAN.modules.NAMES[:2])); self.assertTrue(self.case.active)
        self.assertIn('driver_coordinator_error', self.session.result)
        self.source = self.session.output; self.fail_module = None
        self.assertTrue(self.accepted('start')['successful'])
        self.assertNotIn('driver_coordinator_error', self.session.result)
        self.assertIn('previous_driver_coordinator_error', self.session.result)
        loaded = [entry['name'] for entry in self.session.driver_module_journal if entry['action'] == 'load']
        self.assertEqual(loaded, list(WLAN.modules.NAMES[:3]) + list(WLAN.modules.NAMES[2:]))
        self.assertEqual([entry['action'] for entry in self.session.driver_runtime_journal], ['prepare','publish'])

    def test_busy_unload_retains_providers_without_creating_an_effect(self):
        # Mutation: use force removal or provider cleanup after a busy normal unload.
        self.accepted('start'); self.phone.refs['brcmfmac_wcc'] = 1; effects = self.effects()
        with self.assertRaises(ValueError): self.run_action('stop')
        self.assertEqual(self.effects(), effects); self.assertEqual(self.phone.present, set(WLAN.modules.NAMES))
        self.assertTrue(self.case.active and self.case.pcie and self.case.reg); self.assertFalse(self.cleaned)
        saved = json.loads((self.session.output / 'held-state-private.json').read_text())
        self.assertEqual(len(saved['driver_module_journal']), 5); self.assertIsNotNone(saved['checkpoint'])

    def test_transport_failure_recovers_by_observation_without_replay_or_orphan_copy(self):
        # Mutations: repeat a pending receipt or copy an orphan instead of the fresh recovered proof.
        self.transport_module = WLAN.modules.NAMES[2]
        with self.assertRaises(OSError): self.run_action('start')
        self.assertEqual(self.phone.present, set(WLAN.modules.NAMES[:3]))
        self.assertIsNone(self.session.driver_module_journal[-1]['completion'])
        self.source = self.session.output; orphan = self.source / 'unregistered-private.log'; orphan.write_text('private orphan\n'); orphan.chmod(0o600)
        before = {p.name:p.read_bytes() for p in self.source.iterdir()}; effects = self.effects(); self.transport_module = None
        self.assertEqual(self.accepted('observe')['phase'], 'retained'); self.assertEqual(self.effects(), effects)
        entry = self.session.driver_module_journal[-1]['completion']
        self.assertEqual((entry['mode'], entry['shell_exit'], entry['operation_exit']), ('observed',None,0))
        original = self.root / 'runtime' / 'operation-1'
        self.assertEqual(before, {p.name:p.read_bytes() for p in original.iterdir()}); self.assertFalse((self.source / orphan.name).exists())

    def test_unprepared_stop_never_creates_native_or_wcc_intents(self):
        # Mutation: manufacture prepare/release or module effects for a never-started host.
        self.assertEqual(self.accepted('stop')['phase'], 'stopped')
        self.assertEqual(self.session.driver_runtime_journal, []); self.assertEqual(self.session.driver_module_journal, [])
        self.assertFalse(any(name.startswith(('driver-runtime-','wlan-module-')) for name in self.effects()))

    def test_negative_assignment_is_observed_and_stopped_without_becoming_success(self):
        # Mutation: report success after cleanup0 or lose the first assignment cause.
        resource = initial_fixture.resource_fixture
        path = self.origin / 'resource-assignment-proof-private.log'; proof = path.read_text()
        proof = proof.replace(resource.fixture.ACTIVE, resource.fixture.ACTIVE.replace('primary_error=0','primary_error=-13'))
        proof = proof.replace('error=0 assigned=1','error=-13 assigned=0').replace('exit=0','exit=1')
        proof = proof.replace('assigned=1 pending=1 claimed=1 active=0 error=0','assigned=0 pending=1 claimed=1 active=0 error=-13')
        path.write_text(proof); self.session.resource_assignment = initial_fixture.RESOURCE.n71_resource_result.outcome(proof)
        self.session.result['resource_assignment'] = self.session.resource_assignment
        self.phone.journal.proofs['resource-assignment'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.phone.kernel_history = self.phone.kernel_history.replace('error=0 assigned=1','error=-13 assigned=0')
        self.life.primary = -13; self.life.vector['error'] = -13; self.phone.current_driver['error'] = -13
        self.provider_tail = self.provider_tail.replace('power_put_pending=0 primary_error=0\n','power_put_pending=0 primary_error=-13\n').replace('stop-error=0','stop-error=-13')
        self.template_history = self.case.full_history.replace('error=0 assigned=1','error=-13 assigned=0').replace('power_put_pending=0 primary_error=0\n','power_put_pending=0 primary_error=-13\n').replace('stop-error=0','stop-error=-13')
        self.cleanup_template = self.cleanup_template.replace('error=0 assigned=1','error=-13 assigned=0').replace('power_put_pending=0 primary_error=0\n','power_put_pending=0 primary_error=-13\n').replace('stop-error=0','stop-error=-13')
        self.cleanup_template = self.cleanup_template.replace(resource.fixture.CLEAN, resource.fixture.CLEAN.replace('primary_error=0','primary_error=-13'))
        self.cleanup_template = self.cleanup_template.replace('active=0 error=0','active=0 error=-13').replace('operation_error=0 error=0','operation_error=0 error=-13').replace('child=0 error=0 session_error=0','child=0 error=-13 session_error=0')
        self.phone.journal.save(); self.phone.journal.finish()
        result = self.accepted('observe'); self.assertEqual((result['primary_error'],result['successful']), (-13,False))
        with self.assertRaises(ValueError): self.run_action('start')
        self.assertEqual(self.effects(), []); self.source = self.session.output
        result = self.accepted('stop'); self.assertEqual(result, dict(action='stop',phase='stopped',primary_error=-13,successful=False))
        self.assertEqual(self.session.driver_runtime_journal, []); self.assertTrue(self.session.result['cleanup_verified'])

    def test_invalid_boot_history_source_and_selection_refuse_before_effect(self):
        # Mutations: skip current identity/history or let an unsafe source authorize a kernel effect.
        initial = self.text(); original_text = self.text
        for value in (initial.replace(native_fixture.BOOT, '87654321-1234-1234-1234-123456789abc'),
            initial + '[ 800.000000] N71_OTHER_ACTION unknown\n'):
            self.text = lambda: value
            with self.assertRaises(ValueError): self.run_action('start')
            self.assertEqual(self.effects(), [])
        self.text = original_text
        data = json.loads((self.origin / 'held-state-private.json').read_text()); name = data['checkpoint']['name']
        with (self.origin / name).open('a') as file: file.write('changed\n')
        with self.assertRaises(ValueError): self.run_action('start')
        self.assertEqual(self.effects(), [])

    def test_proof_changed_between_source_validation_and_copy_refuses_before_effect(self):
        # Mutation: omit the registered byte-hash check at the copy boundary.
        self.race = True
        with self.assertRaises(ValueError): self.run_action('start')
        self.assertEqual(self.effects(), []); self.assertEqual(self.phone.present, set())


class RuntimeSessionMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeSessionTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        source = SOURCE.read_text()
        cycle = 'test_start_observe_and_stop_share_one_boot_and_preserve_origin'
        mutations = [
            ('prepare-before-load', "proved = native.act(session, journal, {'action': 'prepare', 'live': live})", "proved = {'native': {'error': 0}}", cycle),
            ('publication', "proved = native.act(session, journal, {'action': 'publish', 'live': live})", "proved = {'native': {'error': 0}}", cycle),
            ('reverse-unload', 'for name in reversed(wlan.modules.NAMES):', 'for name in wlan.modules.NAMES:', cycle),
            ('provider-cleanup', 'held.release(session, journal, presence, live)', 'pass', cycle),
            ('observe-without-effects', "elif request['action'] == 'stop': stop(session, journal, (live, presence))", 'else: stop(session, journal, (live, presence))', cycle),
            ('fresh-validation', "validate(session, {'text': live, 'presence': presence, 'context': {'baseline': data['baseline'], 'checkpoint': prior, 'proofs': proofs}})", 'pass', 'test_invalid_boot_history_source_and_selection_refuse_before_effect'),
            ('complete-proof-bytes', 'raw = path.read_bytes()', 'raw = history.read_private(origin, name).encode()', cycle),
            ('copy-integrity', 'hashlib.sha256(raw).hexdigest() == digest', 'True', 'test_proof_changed_between_source_validation_and_copy_refuses_before_effect'),
            ('recovered-proof-origin', "if recovered is not None and recovered != data['result'].get('runtime_recovery_source'):", 'if False:', 'test_transport_failure_recovers_by_observation_without_replay_or_orphan_copy'),
            ('negative-cause', "cleanup.get('cleanup_primary_error', cleanup['assignment_error'])", '0', 'test_negative_assignment_is_observed_and_stopped_without_becoming_success'),
            ('negative-success', "'successful': primary == 0", "'successful': True", 'test_negative_assignment_is_observed_and_stopped_without_becoming_success'),
        ]
        for name, before, after, method in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(before), 1, name)
                subject = ModuleType('runtime_session_mutant')
                exec(compile(ast.parse(source.replace(before, after, 1)), str(SOURCE), 'exec'), subject.__dict__)
                case = type('MutatedRuntimeSessionTests', (RuntimeSessionTests,), {'subject':subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name); self.assertGreater(len(result.failures), 0, name)
                print('N71_RUNTIME_SESSION_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
