"""Stopping before driver preparation still requires complete same-boot ownership proofs."""
import ast
import copy
import hashlib
import io
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
import test_n71_runtime_held_capture as fixture
import test_n71_driver_runtime_stage as native_fixture
import test_n71_resource_result as resource_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_lifetime as LIFETIME
import n71_held_session as HELD
import n71_resource_stage as RESOURCE
import n71_session_history as HISTORY
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_lifetime.py'


class UnpreparedStopTests(unittest.TestCase):
    subject = LIFETIME

    def setUp(self):
        self.case = fixture.RuntimeHeldSourceTests('test_removed_source_loader_and_read_only_recovery_preserve_origin')
        self.case.setUp(); self.addCleanup(self.case.doCleanups)
        self.life = self.case.life; self.session = self.case.session; self.journal = self.case.journal
        acquisition = '\n'.join(self.session.driver_runtime_journal[0]['history']) + '\n'
        provider_lines = [line for line in HISTORY.kernel_lines(self.case.cleanup_proof) if '[ 9' in line]
        complete = acquisition + '\n'.join(provider_lines) + '\n'
        self.case.cleanup_proof = self.case.cleanup_proof.replace(self.case.full_history, complete)
        self.case.full_history = complete; self.life.phone.kernel_history = acquisition
        self.life.phone.current_driver = dict(native_fixture.INITIAL)
        self.session.driver_runtime_journal = []; self.session.driver_module_journal = []
        self.journal.proofs = {'resource-assignment':self.journal.proofs['resource-assignment']}; self.journal.save()
        patched = patch.dict(sys.modules, {'n71_driver_runtime_lifetime':self.subject}); patched.start(); self.addCleanup(patched.stop)

    def accepted(self, function, *args):
        try: return function(*args)
        except ValueError as error: self.fail('Proved unprepared stop refused: ' + str(error))

    def release(self):
        self.accepted(self.case.release); self.case.checkpoint()
        return self.case.removed_text(), self.life.context()

    def test_stop_and_source_loader_prove_cleanup_without_inventing_native_actions(self):
        # Mutation: require a fabricated native prepare/release ledger before accepting a clean unprepared host.
        text, context = self.release()
        before = {path.name:path.read_bytes() for path in self.case.output.iterdir()}
        result = self.accepted(self.subject.removed, self.session, text, context)
        self.assertTrue(result['resource_cleanup_verified']); self.assertEqual(result['assignment_error'], 0)
        restored = self.case.restored(self.case.output)
        data, _, _ = self.accepted(HELD.load_source, restored, self.life.root, self.case.output, {'modules':{}})
        recovered = self.accepted(fixture.RECOVERY.load, restored, {'root':self.life.root, 'source':self.case.output,
            'identity':{'modules':{}}, 'allowed_proofs':HELD.PROOFS, 'loader':HELD.load_source, 'snapshot':HELD.snapshot})
        self.assertEqual(recovered[0], data)
        self.assertEqual(data['driver_runtime_journal'], []); self.assertEqual(data['driver_module_journal'], [])
        self.assertEqual(before, {path.name:path.read_bytes() for path in self.case.output.iterdir()})
        self.assertFalse(self.case.pcie or self.case.reg or self.case.active)
        self.assertFalse(any('driver-' in command or 'insmod ' in command for _,command in self.case.calls))

    def test_assignment_failure_keeps_its_first_cause_after_complete_cleanup(self):
        # Mutation: require assignment success or erase a completed negative assignment cause on stop.
        active, _ = resource_fixture.failed()
        proof = HISTORY.read_private(self.case.output, 'resource-assignment-proof-private.log')
        event = RESOURCE.n71_resource_result.event(active)
        proof = proof.replace('error=0 assigned=1', 'error=-13 assigned=0').replace('exit=0', 'exit=1')
        proof = proof.replace(resource_fixture.fixture.ACTIVE, resource_fixture.fixture.ACTIVE.replace('primary_error=0', 'primary_error=-13'))
        proof = proof.replace('assigned=1 pending=1 claimed=1 active=0 error=0', 'assigned=0 pending=1 claimed=1 active=0 error=-13')
        path = self.case.output / 'resource-assignment-proof-private.log'; path.write_text(proof)
        self.session.resource_assignment = RESOURCE.n71_resource_result.outcome(proof)
        self.assertEqual(self.session.resource_assignment['event'], event)
        self.session.result['resource_assignment'] = self.session.resource_assignment
        self.journal.proofs['resource-assignment'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.life.phone.kernel_history = self.life.phone.kernel_history.replace('error=0 assigned=1', 'error=-13 assigned=0')
        self.case.full_history = self.case.full_history.replace('error=0 assigned=1', 'error=-13 assigned=0').replace('stop-error=0','stop-error=-13').replace('power_put_pending=0 primary_error=0\n','power_put_pending=0 primary_error=-13\n')
        self.case.cleanup_proof = self.case.cleanup_proof.replace('error=0 assigned=1', 'error=-13 assigned=0').replace('stop-error=0','stop-error=-13').replace('power_put_pending=0 primary_error=0\n','power_put_pending=0 primary_error=-13\n')
        self.case.cleanup_proof = self.case.cleanup_proof.replace(resource_fixture.fixture.CLEAN, resource_fixture.fixture.CLEAN.replace('primary_error=0','primary_error=-13'))
        self.case.cleanup_proof = self.case.cleanup_proof.replace('active=0 error=0', 'active=0 error=-13').replace('operation_error=0 error=0', 'operation_error=0 error=-13')
        self.case.cleanup_proof = self.case.cleanup_proof.replace('child=0 error=0 session_error=0', 'child=0 error=-13 session_error=0')
        self.journal.save(); text, context = self.release()
        result = self.accepted(self.subject.removed, self.session, text, context)
        self.assertTrue(result['resource_cleanup_verified']); self.assertEqual(result['assignment_error'], -13)

    def test_missing_changed_assignment_and_unrecorded_native_action_refuse(self):
        # Mutations: trust missing/altered assignment or ignore an unrecorded native effect before cleanup.
        text, context = self.release()
        missing = copy.deepcopy(context); missing['proofs'].pop('resource-assignment')
        with self.assertRaises(ValueError): self.subject.removed(self.session, text, missing)
        altered = copy.deepcopy(context)
        altered['proofs']['resource-assignment'] = altered['proofs']['resource-assignment'].replace('exit=0','exit=1')
        with self.assertRaises(ValueError): self.subject.removed(self.session, text, altered)
        saved = self.session.resource_assignment
        self.session.resource_assignment = dict(saved, assignment_verified=False)
        with self.assertRaises(ValueError): self.subject.removed(self.session, text, context)
        self.session.resource_assignment = saved
        unknown = native_fixture.native('prepare', native_fixture.PREPARED, {'stamp':5000})
        anchor = next(line for line in HISTORY.kernel_lines(context['proofs']['resource-assignment']) if 'N71_PCIE_RESOURCE_RESULT ' in line) + '\n'
        altered = copy.deepcopy(context)
        altered['proofs'] = {name:proof.replace(anchor, anchor + unknown) for name,proof in altered['proofs'].items()}
        with self.assertRaises(ValueError): self.subject.removed(self.session, text.replace(anchor, anchor + unknown), altered)

    def test_empty_ledgers_do_not_bypass_common_boot_owner_and_cleanup_guards(self):
        # Mutations: skip the shared boot, ownership, prefix or provider cleanup checks for an unprepared host.
        text, context = self.release()
        invalid = [text.replace(native_fixture.BOOT, '87654321-1234-1234-1234-123456789abc'),
            text.replace('name=rfkill present=0 state=-', 'name=rfkill present=1 state=live'),
            text.replace(native_fixture.BASE, ''), text.replace('N71_HELD_PCI_EMPTY=1', 'N71_HELD_PCI_EMPTY=0')]
        for live in invalid:
            with self.subTest(live=live[-80:]), self.assertRaises(ValueError): self.subject.removed(self.session, live, context)
        for name in ('pcie-cleanup', 'pcie-unload'):
            changed = copy.deepcopy(context); changed['proofs'].pop(name)
            with self.subTest(proof=name), self.assertRaises(ValueError): self.subject.removed(self.session, text, changed)


class UnpreparedStopMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(UnpreparedStopTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        source = SOURCE.read_text()
        mutations = [
            ('unprepared-stop', "assignment = getattr(session, 'resource_assignment', None)\n        require(not native", "require(False, 'Unprepared cleanup refused')\n        assignment = getattr(session, 'resource_assignment', None)\n        require(not native", 'test_stop_and_source_loader_prove_cleanup_without_inventing_native_actions'),
            ('assignment-proof', "not native and not wlan and assignment is not None and 'resource-assignment' in proofs\n                and resources.outcome(proofs['resource-assignment']) == assignment", 'True', 'test_missing_changed_assignment_and_unrecorded_native_action_refuse'),
            ('assignment-summary', "and resources.outcome(proofs['resource-assignment']) == assignment", '', 'test_missing_changed_assignment_and_unrecorded_native_action_refuse'),
            ('unrecorded-native-action', "not any(driver.result.ACTION_MARKER in line for line in fresh)", 'True', 'test_missing_changed_assignment_and_unrecorded_native_action_refuse'),
        ]
        for name, before, after, method in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(before), 1, name)
                subject = ModuleType('runtime_unprepared_mutant')
                exec(compile(ast.parse(source.replace(before, after, 1)), str(SOURCE), 'exec'), subject.__dict__)
                case = type('MutatedUnpreparedStopTests', (UnpreparedStopTests,), {'subject':subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name); self.assertGreater(len(result.failures), 0, name)
                print('N71_UNPREPARED_STOP_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
