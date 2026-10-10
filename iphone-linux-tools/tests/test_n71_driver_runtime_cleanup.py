"""A completed native release preserves its first cause through provider cleanup."""
import ast
import copy
import io
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import test_n71_driver_runtime_stage as native_fixture
import test_n71_iommu_result as iommu_fixture
import test_n71_resource_result as resource_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_result as DRIVER
import n71_driver_runtime_stage as STAGE
import n71_iommu_result as IOMMU
import n71_resource_result as RESOURCE
import n71_resource_stage as RESOURCES


class RuntimeCleanupTests(unittest.TestCase):
    driver = DRIVER
    iommu = IOMMU
    resource = RESOURCE
    resources = RESOURCES

    def setUp(self):
        for owner, name, value in ((STAGE, 'result', self.driver),
                                  (self.iommu, 'n71_driver_runtime_result', self.driver),
                                  (self.resources, 'n71_driver_runtime_result', self.driver),
                                  (self.resources, 'n71_iommu_result', self.iommu),
                                  (self.resources, 'n71_resource_result', self.resource)):
            patched = patch.object(owner, name, value); patched.start(); self.addCleanup(patched.stop)

    def lifetime(self, error=0):
        session = SimpleNamespace(driver_runtime=True, driver_runtime_journal=[], iommu_parent=True,
            resource_capable=True, resource_attempted=True,
            resource_assignment=RESOURCE.outcome(resource_fixture.OPEN),
            result={'boot_id': native_fixture.BOOT}, modules=[({'module': 'n71-pcie-diagnostic.ko'}, b'')])
        history = native_fixture.BASE; before = dict(native_fixture.INITIAL)
        for index, (action, state) in enumerate((('prepare', native_fixture.PREPARED),
                    ('publish', native_fixture.PUBLISHED), ('release', native_fixture.RELEASED | dict(error=error, operation_error=error)))):
            entry = dict(action=action, before=dict(before), history=history.splitlines(), completion=None)
            history += native_fixture.native(action, state, {'stamp': index + 2})
            text = native_fixture.snapshot(state, history, {'exit_value': 0, 'action': action})
            entry['completion'] = STAGE.completion(session, entry,
                {'text': text, 'boot': native_fixture.BOOT, 'mode': 'direct', 'shell_exit': 0})
            session.driver_runtime_journal.append(entry); before = state
        return session, history

    def closed(self, request=None):
        request = request or {}; error = request.get('driver_error', 0); provider = request.get('provider_error', 0)
        session, history = self.lifetime(error)
        primary = error or provider
        text = iommu_fixture.CLOSED
        text = text.replace(iommu_fixture.held_fixture.REMOVED,
            resource_fixture.RESULT + iommu_fixture.held_fixture.REMOVED + resource_fixture.RESTORE)
        text = text.replace(iommu_fixture.held_fixture.CONFIG, iommu_fixture.held_fixture.CONFIG + resource_fixture.RELEASE)
        if provider:
            released = iommu_fixture.DART_CLEAN.splitlines(True)[-1]
            text = text.replace(released, iommu_fixture.DART_CONTROL_ERROR + released)
        text = text.replace(iommu_fixture.held_fixture.CLEAN,
            iommu_fixture.held_fixture.CLEAN.replace('primary_error=0', 'primary_error=' + str(primary)))
        text = text.replace(iommu_fixture.held_fixture.FINISHED,
            iommu_fixture.held_fixture.FINISHED.replace('primary_error=0', 'primary_error=' + str(primary)))
        final = dict.fromkeys(DRIVER.FIELDS, 0) | dict(requested=1, error=primary)
        text += resource_fixture.EMPTY.replace('error=0', 'error=' + str(primary))
        text += 'N71_BOOT_ID ' + native_fixture.BOOT + '\n' + STAGE.state_text(final) + history
        return session, text

    def accepted(self, function, *args):
        try: return function(*args)
        except (ValueError, KeyError, AttributeError) as error:
            self.fail('Proved runtime cleanup refused: ' + str(error))

    def test_successful_release_retains_negative_driver_cause_in_real_cleanup_dispatch(self):
        # Mutations: drop runtime error propagation or report completed software release as successful driver operation.
        for error in (0, -5, -13):
            session, text = self.closed({'driver_error': error})
            proof = self.accepted(self.resources.cleanup, session, text)
            self.assertTrue(proof['resource_cleanup_verified'])
            self.assertEqual(proof['assignment_error'], 0); self.assertEqual(proof['stop_error'], 0)
            if error:
                self.assertEqual((proof.get('driver_primary_error'), proof.get('cleanup_primary_error')), (error, error))
            else:
                self.assertNotIn('driver_primary_error', proof)
            self.assertEqual(session.driver_runtime_journal[-1]['completion']['native']['error'], 0)
            self.assertEqual(session.driver_runtime_journal[-1]['completion']['state']['error'], error)

    def test_later_provider_error_cannot_replace_the_proved_driver_cause(self):
        # Mutations: provider error precedes the driver cause or the original provider error is erased.
        for error in (0, -13):
            session, text = self.closed({'driver_error': error, 'provider_error': -5})
            proof = self.accepted(self.resources.cleanup, session, text)
            self.assertEqual(proof['cleanup_primary_error'], error or -5)
            self.assertEqual(proof['provider_operation_error'], -5)
            if error: self.assertEqual(proof['driver_primary_error'], error)
            else: self.assertNotIn('driver_primary_error', proof)
            provider = self.accepted(self.iommu.cleanup, session, text)
            self.assertTrue(provider['software_ownership_released']); self.assertFalse(provider['dma_translation_verified'])

    def test_assignment_precedence_and_exact_cause_schema_preserve_legacy_result(self):
        # Mutations: driver error precedes assignment or noncanonical error types enter the cleanup context.
        opened, closed = resource_fixture.failed()
        assignment = RESOURCE.outcome(opened)
        proof = self.accepted(self.resource.cleanup_errors, closed, assignment, {'driver_error': -5, 'provider_error': -19})
        self.assertEqual((proof['assignment_error'], proof['cleanup_primary_error'], proof['driver_primary_error'], proof['provider_operation_error']),
                         (-13, -13, -5, -19))
        expected = RESOURCE.cleanup(resource_fixture.CLOSED, RESOURCE.outcome(resource_fixture.OPEN))
        self.assertEqual(self.resource.cleanup(resource_fixture.CLOSED, RESOURCE.outcome(resource_fixture.OPEN)), expected)
        for errors in ({'driver_error': True, 'provider_error': 0}, {'driver_error': False, 'provider_error': 0},
                       {'driver_error': -4096, 'provider_error': 0},
                       {'driver_error': -5, 'provider_error': 1}, {'driver_error': -5},
                       {'driver_error': -5, 'provider_error': 0, 'extra': 0}):
            with self.subTest(errors=errors), self.assertRaises(ValueError): self.resource.cleanup_errors(closed, assignment, errors)

    def test_pending_refused_missing_or_different_release_never_authorizes_provider_cleanup(self):
        # Mutations: trust pending metadata, wrong boot/history, another action or a refused native release.
        session, text = self.closed({'driver_error': -13})
        cases = []
        pending = copy.deepcopy(session); pending.driver_runtime_journal[-1]['completion'] = None
        cases.append((pending, text))
        refused = copy.deepcopy(session); refused.driver_runtime_journal[-1]['completion']['native']['error'] = -16
        cases.append((refused, text.replace('action=release error=0', 'action=release error=-16')))
        before_release = copy.deepcopy(session); before_release.driver_runtime_journal.pop()
        cases.append((before_release, text))
        cases += [(session, text.replace(native_fixture.BOOT, '87654321-1234-1234-1234-123456789abc')),
                  (session, text.replace(native_fixture.BASE, '[ 1.000000] N71_DIFFERENT_BASE private\n')),
                  (session, text.replace('action=release', 'action=cleanup')),
                  (session, text.replace('N71_PCIE_DRIVER_RESULT action=release error=0', 'N71_PCIE_DRIVER_RESULT action=release error=-5'))]
        for current, proof in cases:
            with self.subTest(proof=proof[-200:]), self.assertRaises(ValueError): self.driver.cleanup_cause(current, proof)
        legacy = SimpleNamespace(driver_runtime=False)
        self.assertEqual(self.driver.cleanup_cause(legacy, 'legacy without runtime fields'), 0)

    def test_discarded_cause_and_live_host_ownership_refuse_even_with_complete_release(self):
        # Mutations: erase the first cause or admit a host retained after the claimed provider cleanup.
        session, text = self.closed({'driver_error': -13})
        removed = STAGE.state_text(dict.fromkeys(DRIVER.FIELDS, 0) | dict(requested=1, error=-13))
        invalid = [text.replace(removed, removed.replace('error=-13', 'error=-5')),
                   text.replace(removed, STAGE.state_text(native_fixture.RELEASED | dict(error=-13, operation_error=-13)))]
        for proof in invalid:
            with self.assertRaises(ValueError): self.driver.cleanup_cause(session, proof)


class RuntimeCleanupMutations(unittest.TestCase):
    def test_executed_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeCleanupTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        mutations = [
            ('boot', 'driver', DRIVER, "re.findall(r'^N71_BOOT_ID (' + stage.BOOT + ')$', text, re.M) == [session.result.get('boot_id')]", 'True', 'test_pending_refused_missing_or_different_release_never_authorizes_provider_cleanup'),
            ('release-proof', 'driver', DRIVER, "entry['action'] == 'release' and completion is not None and completion['native']['error'] == 0\n            and not completion['state']['pending']", 'completion is not None', 'test_pending_refused_missing_or_different_release_never_authorizes_provider_cleanup'),
            ('prefix', 'driver', DRIVER, "lines[:len(entry['history'])] == entry['history']", 'True', 'test_pending_refused_missing_or_different_release_never_authorizes_provider_cleanup'),
            ('native-result', 'driver', DRIVER, "native == completion['native']", 'True', 'test_pending_refused_missing_or_different_release_never_authorizes_provider_cleanup'),
            ('first-cause', 'driver', DRIVER, "not error or state['error'] == error", 'True', 'test_discarded_cause_and_live_host_ownership_refuse_even_with_complete_release'),
            ('host-owner', 'driver', DRIVER, "not state['pending'] and not state['held'] and not state['ready']", 'True', 'test_discarded_cause_and_live_host_ownership_refuse_even_with_complete_release'),
            ('error-propagation', 'resources', RESOURCES, 'driver_error = n71_driver_runtime_result.cleanup_cause(session, proof)', 'driver_error = 0', 'test_successful_release_retains_negative_driver_cause_in_real_cleanup_dispatch'),
            ('provider-precedence', 'resource', RESOURCE, 'if not error and driver_error:', 'if False:', 'test_later_provider_error_cannot_replace_the_proved_driver_cause'),
            ('assignment-precedence', 'resource', RESOURCE, 'if not error and driver_error:', 'if driver_error:', 'test_assignment_precedence_and_exact_cause_schema_preserve_legacy_result'),
            ('driver-type', 'resource', RESOURCE, 'type(driver_error) is int', 'isinstance(driver_error, int)', 'test_assignment_precedence_and_exact_cause_schema_preserve_legacy_result'),
            ('provider-context', 'iommu', IOMMU, 'driver_error = n71_driver_runtime_result.cleanup_cause(session, text)', 'driver_error = 0', 'test_later_provider_error_cannot_replace_the_proved_driver_cause'),
        ]
        for name, attribute, original, old, new, method in mutations:
            with self.subTest(name=name):
                source = Path(original.__file__).read_text(); self.assertEqual(source.count(old), 1, name)
                subject = ModuleType('runtime_cleanup_mutant')
                exec(compile(ast.parse(source.replace(old, new, 1)), original.__file__, 'exec'), subject.__dict__)
                case = type('MutatedRuntimeCleanupTests', (RuntimeCleanupTests,), {attribute: subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name)
                self.assertGreater(len(result.failures), 0, name)
                print('N71_RUNTIME_CLEANUP_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
