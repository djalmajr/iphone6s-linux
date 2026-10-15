"""Replay pre-stop refusals through real cleanup parsers and native journals."""
import ast
import copy
import io
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch
import test_n71_driver_runtime_cleanup as fixture
import n71_scan_held_result as HELD
import n71_session_history as HISTORY

ROOT = Path(__file__).resolve().parents[1]
REFUSALS = ('[ 3.100000] N71_PCIE_SCAN_WRITE_REFUSED bus=1 devfn=00 where=05c size=4 value=00000000 error=-1\n'
            '[ 3.200000] N71_PCIE_SCAN_WRITE_REFUSED bus=1 devfn=00 where=064 size=2 value=00000000 error=-1\n')
LATE = '[ 5.000000] N71_PCIE_SCAN_WRITE_REFUSED bus=1 devfn=00 where=004 size=2 value=00000000 error=-5\n'
REMOVED = fixture.iommu_fixture.held_fixture.REMOVED


class StopHistoryTests(unittest.TestCase):
    held = HELD
    resource = fixture.RESOURCE
    resources = fixture.RESOURCES

    def setUp(self):
        case = fixture.RuntimeCleanupTests('test_successful_release_retains_negative_driver_cause_in_real_cleanup_dispatch')
        case.resource = self.resource; case.resources = self.resources
        case.setUp(); self.addCleanup(case.doCleanups); self.case = case
        hook = patch.object(self.resource, 'n71_scan_held_result', self.held)
        hook.start(); self.addCleanup(hook.stop)

    def physical_shape(self):
        session, text = self.case.closed({'driver_error': -1})
        _, original = self.case.lifetime(-1)
        self.assertTrue(text.endswith(original)); text = text[:-len(original)]
        before, after = text.split(REMOVED)
        session.driver_runtime_journal = []; history = fixture.native_fixture.BASE
        initial = dict(fixture.native_fixture.INITIAL)
        for index, (action, state) in enumerate((('prepare', fixture.native_fixture.PREPARED),
            ('publish', fixture.native_fixture.PUBLISHED),
            ('release', fixture.native_fixture.RELEASED | dict(error=-1, operation_error=-1)))):
            if action == 'release':
                history += REFUSALS; initial.update(error=-1, operation_error=-1)
            entry = dict(action=action, before=dict(initial), history=HISTORY.kernel_lines(history), completion=None)
            history += fixture.native_fixture.native(action, state, {'stamp': index + 2})
            proof = fixture.native_fixture.snapshot(state, history, {'exit_value': 0, 'action': action})
            entry['completion'] = fixture.STAGE.completion(session, entry,
                {'text': proof, 'boot': fixture.native_fixture.BOOT, 'mode': 'direct', 'shell_exit': 0})
            session.driver_runtime_journal.append(entry); initial = dict(state)
        return session, before + history + REMOVED + after

    def lower(self, session, text, history=None, errors=None):
        context = errors or {'driver_error': -1, 'provider_error': 0,
            'driver_history': session.driver_runtime_journal[-1]['history'] if history is None else history}
        return self.resource.cleanup_errors(text, session.resource_assignment, context)

    def accepted(self, function, *args):
        try: return function(*args)
        except (ValueError, KeyError, AttributeError) as error: self.fail('Proved pre-stop cleanup refused: ' + str(error))

    def test_real_dispatch_preserves_old_errors_and_zero_stop_without_mutating_evidence(self):
        # Mutation: omit the authenticated pre-release history or drop the original driver cause.
        session, text = self.physical_shape(); saved = copy.deepcopy(session)
        proof = self.accepted(self.resources.cleanup, session, text)
        self.assertEqual((proof['stop_error'], proof['driver_primary_error'], proof['cleanup_primary_error']), (0, -1, -1))
        self.assertTrue(proof['resource_cleanup_verified']); self.assertEqual(session, saved)
        with self.assertRaises(ValueError):
            self.resource.cleanup_errors(text, session.resource_assignment, {'driver_error': -1, 'provider_error': 0})

    def test_later_or_unproved_refusals_never_disappear_into_previous_history(self):
        # Mutation: classify by text membership alone or ignore every write before native release.
        session, text = self.physical_shape()
        late = text.replace(REMOVED, LATE + REMOVED.replace('stop-error=0', 'stop-error=-5'))
        proof = self.accepted(self.resources.cleanup, session, late)
        self.assertEqual((proof['stop_error'], proof['driver_primary_error']), (-5, -1))
        duplicate = text.replace(REMOVED, REFUSALS.splitlines(True)[0] + REMOVED)
        release = next(line + '\n' for line in text.splitlines() if 'N71_PCIE_DRIVER_RESULT action=release ' in line)
        unproved = text.replace(release, LATE.replace('5.000000', '3.300000') + release)
        mismatch = text.replace(REMOVED, LATE + REMOVED.replace('stop-error=0', 'stop-error=-13'))
        for current in [text.replace(REMOVED, LATE + REMOVED), duplicate, unproved, mismatch]:
            with self.subTest(tail=current[-200:]), self.assertRaises(ValueError): self.resources.cleanup(session, current)
        after_removal = text.replace(REMOVED, REMOVED.replace('stop-error=0', 'stop-error=-5') + LATE)
        with self.assertRaises(ValueError): self.lower(session, after_removal)

    def test_context_requires_exact_pre_release_prefix_cause_and_release_order(self):
        # Mutation: trust a forged prefix, include release in the prefix, erase cause, or release after removal.
        session, text = self.physical_shape(); prior = session.driver_runtime_journal[-1]['history']
        invalid = [True, None, [], 'not a list', ['x' * (2 * 1024 * 1024 + 1)],
            [prior[0].replace('N71_TEST_BASELINE', 'N71_DIFFERENT_BASELINE')] + prior[1:]]
        release = next(line for line in text.splitlines() if 'N71_PCIE_DRIVER_RESULT action=release ' in line)
        invalid += [prior + [release]]
        for history in invalid:
            errors = {'driver_error': -1, 'provider_error': 0, 'driver_history': history}
            with self.subTest(history=str(history)[:100]), self.assertRaises(ValueError):
                self.lower(session, text, errors=errors)
        with self.assertRaises(ValueError):
            self.lower(session, text, errors={'driver_error': 0, 'provider_error': -1, 'driver_history': prior})
        no_cause = text.replace('primary_error=-1', 'primary_error=0')
        with self.assertRaises(ValueError): self.held.cleanup(no_cause, primary_error=0, prior_history=prior)
        late_release = text.replace(release + '\n', '') + release + '\n'
        with self.assertRaises(ValueError): self.lower(session, late_release)
        with self.assertRaises(ValueError): self.lower(session, text.replace(release + '\n', ''))
        with self.assertRaises(ValueError): self.lower(session, text.replace(release, release.replace('pending=0', 'pending=1')))
        foreign = copy.deepcopy(session); foreign.result['boot_id'] = '87654321-1234-1234-1234-123456789abc'
        with self.assertRaises(ValueError): self.resources.cleanup(foreign, text)


class StopHistoryMutations(unittest.TestCase):
    def test_executed_assertion_mutations(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(StopHistoryTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        mutations = [
            ('forged-prefix', 'held', HELD, 'n71_session_history.kernel_lines(text)[:len(prior)] == prior', 'True',
                'test_context_requires_exact_pre_release_prefix_cause_and_release_order'),
            ('release-in-prefix', 'held', HELD, 'not any(marker in line for line in prior)', 'True',
                'test_context_requires_exact_pre_release_prefix_cause_and_release_order'),
            ('post-release-membership', 'held', HELD, 'row.start() < release.start() and line in known', 'line in known',
                'test_later_or_unproved_refusals_never_disappear_into_previous_history'),
            ('unproved-before-release', 'held', HELD, 'row.start() < release.start() and line in known', 'row.start() < release.start()',
                'test_later_or_unproved_refusals_never_disappear_into_previous_history'),
            ('missing-cause', 'held', HELD, "request['primary_error'] < 0", 'True',
                'test_context_requires_exact_pre_release_prefix_cause_and_release_order'),
            ('release-after-removal', 'held', HELD, "text.index('N71_PCIE_SESSION_HELD ') < release.start() < request['removed'].start()", 'True',
                'test_context_requires_exact_pre_release_prefix_cause_and_release_order'),
            ('stop-cause-lost', 'held', HELD, 'int(current[0].group(1)) == stop_error', 'True',
                'test_later_or_unproved_refusals_never_disappear_into_previous_history'),
            ('outside-lifetime', 'held', HELD, "all(text.index('N71_PCIE_SESSION_HELD ') < row.start() < removed.start() for row in refusals)", 'True',
                'test_later_or_unproved_refusals_never_disappear_into_previous_history'),
            ('context-from-provider', 'resource', fixture.RESOURCE, "'driver_history' not in errors or (driver_error < 0 and error == 0 and prior_history is not None)", 'True',
                'test_context_requires_exact_pre_release_prefix_cause_and_release_order'),
            ('missing-dispatch-history', 'resources', fixture.RESOURCES, "errors['driver_history'] = history", 'pass',
                'test_real_dispatch_preserves_old_errors_and_zero_stop_without_mutating_evidence')]
        for name, attribute, original, before, after, method in mutations:
            source = Path(original.__file__).read_text(); self.assertEqual(source.count(before), 1, name)
            subject = ModuleType('stop_history_mutant')
            exec(compile(ast.parse(source.replace(before, after, 1)), original.__file__, 'exec'), subject.__dict__)
            case = StopHistoryTests(method); setattr(case, attribute, subject)
            result = unittest.TextTestRunner(stream=io.StringIO()).run(case)
            self.assertFalse(result.errors, 'Infrastructure error is not proof: ' + name + str(result.errors))
            self.assertTrue(result.failures and all('AssertionError' in detail for _, detail in result.failures), name)
            print('N71_STOP_HISTORY_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
