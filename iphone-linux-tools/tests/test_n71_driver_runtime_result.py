"""Driver getter/action contracts and the actual passive association coordinator."""
import ast
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_result.py'
SPEC = importlib.util.spec_from_file_location('driver_result_under_test', SOURCE)
RESULT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESULT)
FIELDS = ('requested', 'ready', 'held', 'pending', 'active', 'published', 'root', 'endpoint',
          'pm', 'root_override', 'endpoint_override', 'reads', 'operation_error', 'error', 'session_error')
EMPTY = dict.fromkeys(FIELDS, 0)
ACTIVE = EMPTY | dict(requested=1, ready=1, held=1, pending=1, active=1, published=1,
                      root=1, endpoint=1, pm=1, root_override=1, endpoint_override=1, reads=3)
CALLER = dict(ready=1, scan_pending=1, primary_error=0, cleanup_error=0)
SELECTED = SimpleNamespace(driver_runtime=True, iommu_parent=True)
ASSOCIATION = ('N71_PCIE_MSI requested=1 ready=1 held=1 associated=1 owner=1 domain=1 mappings=0 child=0 session_error=0\n'
               'N71_PCIE_IOMMU requested=1 ready=1 held=1 owner=1 available=1 mapped=1 observed=2 map_checked=1 session_error=0\n'
               'N71_HELD_PARAM msi_parent=Y\nN71_HELD_PARAM iommu_parent=Y\nN71_PCIE_HELD held=1\n'
               'N71_PCIE_STATUS ready=1 retained=1 scan_pending=1 reset_pending=1 powered=4 attached=4 power_put_pending=0 primary_error=0 cleanup_error=0\n')


def row(state, *, parameter=True):
    value = 'N71_PCIE_DRIVER ' + ' '.join(f'{name}={state[name]}' for name in FIELDS) + '\n'
    return value + ('N71_HELD_PARAM driver_runtime=' + ('Y' if state['requested'] else 'N') + '\n' if parameter else '')


def action_row(action, **changes):
    state = {name: ACTIVE[name] for name in RESULT.ACTION_FIELDS}
    if action == 'prepare': state['published'] = 0
    if action in ('release', 'cleanup'):
        state.update(dict.fromkeys(('pending',) + RESULT.OWNERS, 0))
    state.update(changes)
    return '[  12.345] N71_PCIE_DRIVER_RESULT action=' + action + ' ' + ' '.join(
        f'{name}={state[name]}' for name in RESULT.ACTION_FIELDS) + '; not firmware or radio proof\n'


class DriverContract(unittest.TestCase):
    subject = RESULT

    def test_complete_partial_removed_and_async_states(self):
        # Mutation: lose a partial owner or first error, or confuse publication with host presence.
        states = [EMPTY, EMPTY | dict(requested=1, error=-5, session_error=-16), ACTIVE,
                  ACTIVE | dict(operation_error=-5, error=-5), ACTIVE | dict(reads=4294967295)]
        states += [EMPTY | dict(ready=1, pending=1) | {owner:1} for owner in RESULT.OWNERS]
        for state in states:
            self.assertEqual(self.subject.live(row(state)), state)
        self.assertIsNone(self.subject.live('legacy\n'))
        with self.assertRaises(ValueError): self.subject.live('legacy\n', required=True)
        for selected in (0, 1, 'Y', None):
            with self.assertRaises(ValueError): self.subject.capable(SimpleNamespace(driver_runtime=selected))

    def test_protocol_bounds_and_removed_host(self):
        # Mutation: weaken uniqueness, canonical integers, range or ownership invariants.
        invalid = [row(ACTIVE) * 2, row(ACTIVE).replace(' reads=3', ''),
                   row(ACTIVE).replace('active=1', 'active=01'), row(EMPTY).replace('error=0', 'error=-0'),
                   row(ACTIVE).replace('requested=1 ready=1', 'ready=1 requested=1'),
                   row(ACTIVE).replace(' reads=3', ' reads=3 extra=0'), 'prefix ' + row(ACTIVE),
                   'x' * (2 * 1024 * 1024 + 1), 'N71_HELD_PARAM driver_runtime=N\n',
                   row(ACTIVE | dict(pending=0)), row(EMPTY | dict(ready=1, pending=1)),
                   row(ACTIVE | dict(ready=0, held=0)), row(EMPTY | dict(held=1)),
                   row(ACTIVE | dict(operation_error=-5, error=0))]
        for name in FIELDS[:11]: invalid += [row(ACTIVE | {name:2})]
        for name, values in {'reads':(-1, 4294967296), 'operation_error':(-4096, 1),
                             'error':(-4096, 1), 'session_error':(-4096, 1)}.items():
            invalid += [row(ACTIVE | {name:value}) for value in values]
        for text in invalid:
            with self.subTest(text=text[:160]), self.assertRaises(ValueError): self.subject.live(text)

    def test_snapshot_selection_caller_and_causal_precedence(self):
        # Mutation: omit selection/lifetime checks or discard an asynchronous cause before the caller latch.
        self.assertEqual(self.subject.snapshot(SELECTED, row(ACTIVE), {'caller': CALLER, 'held': 1}), ACTIVE)
        failed = ACTIVE | dict(operation_error=-5, error=-5)
        self.subject.snapshot(SELECTED, row(failed), {'caller': CALLER, 'held': 1})
        try:
            actual = self.subject.snapshot(SELECTED, row(failed | dict(error=-110)), {'caller': CALLER | dict(primary_error=-110), 'held': 1})
        except ValueError as error:
            self.fail('Earlier caller cause must remain accepted: ' + str(error))
        self.assertEqual(actual, failed | dict(error=-110))
        for caller, held in [(CALLER | dict(scan_pending=0), 1), (CALLER, 0),
                             (CALLER | dict(cleanup_error=-16), 1), (CALLER | dict(primary_error=-13), 1)]:
            with self.assertRaises(ValueError): self.subject.snapshot(SELECTED, row(failed), {'caller': caller, 'held': held})
        for text in [row(ACTIVE).replace('driver_runtime=Y', 'driver_runtime=N'),
                     row(ACTIVE, parameter=False), row(ACTIVE) + 'N71_HELD_PARAM driver_runtime=Y\n',
                     row(failed | dict(error=-13)), row(ACTIVE | dict(requested=0))]:
            with self.assertRaises(ValueError): self.subject.snapshot(SELECTED, text, {'caller': CALLER, 'held': 1})
        legacy = SimpleNamespace(driver_runtime=False)
        self.assertIsNone(self.subject.snapshot(legacy, 'legacy\n', {'caller': CALLER, 'held': 1}))
        self.subject.snapshot(legacy, row(EMPTY | dict(ready=1, held=1)), {'caller': CALLER, 'held': 1})
        with self.assertRaises(ValueError): self.subject.snapshot(legacy, row(ACTIVE | dict(requested=0)), {'caller': CALLER, 'held': 1})

    def test_resume_only_counter_and_first_async_error_progress(self):
        # Mutation: accept owner drift, backwards reads, erased causes or immutable parameter changes.
        self.subject.resume(SELECTED, row(ACTIVE | dict(reads=4, operation_error=-5, error=-5)), row(ACTIVE))
        failed = ACTIVE | dict(operation_error=-5, error=-5)
        self.subject.resume(SELECTED, row(failed | dict(reads=5)), row(failed))
        for changed in [ACTIVE | dict(reads=2), ACTIVE | dict(published=0), ACTIVE | dict(root=0),
                        ACTIVE | dict(ready=0, held=0, pending=0, active=0, root=0, endpoint=0, pm=0,
                                      root_override=0, endpoint_override=0, published=0, reads=0),
                        ACTIVE | dict(session_error=-5)]:
            with self.assertRaises(ValueError): self.subject.resume(SELECTED, row(changed), row(ACTIVE))
        for changed in (ACTIVE, failed | dict(operation_error=-13), failed | dict(error=-13)):
            with self.assertRaises(ValueError): self.subject.resume(SELECTED, row(changed), row(failed))
        with self.assertRaises(ValueError): self.subject.resume(SELECTED, 'legacy\n', row(ACTIVE))
        with self.assertRaises(ValueError): self.subject.resume(SELECTED, row(ACTIVE).replace('driver_runtime=Y', 'driver_runtime=N'), row(ACTIVE))
        legacy = SimpleNamespace()
        self.subject.resume(legacy, 'legacy\n', 'legacy\n')
        with self.assertRaises(ValueError): self.subject.resume(legacy, row(EMPTY), 'legacy\n')
        state = EMPTY | dict(ready=1, held=1)
        with self.assertRaises(ValueError): self.subject.resume(legacy, row(state | dict(error=-5)), row(state))

    def test_native_action_shape_owners_and_async_error(self):
        # Mutation: trust the wrong action, a false-zero release or malformed native result.
        for name in ('prepare', 'publish', 'release', 'cleanup'):
            state = self.subject.action(action_row(name), name)
            self.assertEqual(state['error'], 0)
            self.assertEqual(state['pending'], int(name in ('prepare', 'publish')))
        # Native action=0 can precede an async error observed by its report; it is not radio readiness.
        self.assertEqual(self.subject.action(action_row('publish', operation_error=-5), 'publish')['operation_error'], -5)
        self.assertEqual(self.subject.action(action_row('release', error=-16, pending=1, pm=1), 'release')['error'], -16)
        for text, expected in [(action_row('prepare'), 'publish'), (action_row('publish') * 2, 'publish'),
                               (action_row('prepare') + action_row('release'), 'prepare'),
                               (action_row('release', pending=1, pm=1), 'release'),
                               (action_row('publish', endpoint_override=0), 'publish'),
                               (action_row('prepare', published=1), 'prepare'),
                               (action_row('release', error=1), 'release'),
                               (action_row('release').replace('error=0', 'error=-0'), 'release'),
                               (action_row('release').replace('radio proof', 'radio ready'), 'release')]:
            with self.assertRaises(ValueError): self.subject.action(text, expected)

    def test_shell_is_optional_and_read_only(self):
        # Mutation: omit a getter/immutable parameter read or write into the sysfs fixture.
        with tempfile.TemporaryDirectory(prefix='n71-driver-getter-') as directory:
            folder = Path(directory)
            command = self.subject.getter().replace(self.subject.PCIE, str(folder) + '/')
            absent = subprocess.run(['sh', '-c', command], text=True, capture_output=True, timeout=5)
            self.assertEqual((absent.returncode, absent.stdout, absent.stderr), (0, '', ''))
            status = folder / 'driver_runtime_status'; status.write_text(row(ACTIVE, parameter=False).split(' ', 1)[1])
            parameter = folder / 'driver_runtime'; parameter.write_text('Y\n')
            before = {p.name:p.read_bytes() for p in folder.iterdir()}
            present = subprocess.run(['sh', '-c', command], text=True, capture_output=True, timeout=5)
            self.assertEqual((present.returncode, present.stdout, present.stderr), (0, row(ACTIVE), ''))
            self.assertEqual({p.name:p.read_bytes() for p in folder.iterdir()}, before)

    def test_real_association_coordinator_collects_validates_and_resumes(self):
        import n71_iommu_result
        # Mutation: omit actual collection/snapshot/resume integration before held continuation.
        coordinator = getattr(self, 'coordinator', n71_iommu_result)
        self.assertIn(RESULT.getter(), coordinator.getter(SELECTED))
        self.assertEqual(coordinator.getter(SimpleNamespace(iommu_parent=False)), '')
        coordinator.snapshot(SELECTED, ASSOCIATION + row(ACTIVE), True)
        with self.assertRaises(ValueError): coordinator.snapshot(SELECTED, ASSOCIATION + row(ACTIVE | dict(ready=0)), True)
        coordinator.resume(SELECTED, row(ACTIVE), row(ACTIVE))
        with self.assertRaises(ValueError): coordinator.resume(SELECTED, row(ACTIVE | dict(root=0)), row(ACTIVE))
        legacy = SimpleNamespace(iommu_parent=True)
        coordinator.snapshot(legacy, ASSOCIATION, True)
        self.assertEqual(coordinator.saved(legacy, {'iommu_parent':True, 'result':{}}, ASSOCIATION), None)

    def test_source_mutations_fail_by_assertion(self):
        mutations = (
            ('nonboolean-selection', 'type(value) is bool', 'True'),
            ('duplicate-row', 'len(rows) == text.count(marker) == 1', 'len(rows) == text.count(marker) and bool(rows)'),
            ('noncanonical', "rows[0].group('fields') ==", "True or rows[0].group('fields') =="),
            ('partial-owner-lost', "state['pending'] == int(any(state[name] for name in OWNERS))", 'True'),
            ('errno-out-of-range', '-4095 <= state[name] <= 0', '-4096 <= state[name] <= 1'),
            ('counter-overflow', "state['reads'] <= 4294967295", "state['reads'] <= 4294967296"),
            ('first-cause-lost', "not state['operation_error'] or state['error'] < 0", 'True'),
            ('removed-host-owned', "if not state['ready']:", 'if False:'),
            ('missing-required-getter', 'not required and PARAMETER not in text', 'PARAMETER not in text'),
            ('immutable-selection-changed', "parameter[0] == ('Y' if selected else 'N')", 'True'),
            ('caller-host-disagreement', "state['ready'] == caller.get('scan_pending', 0)", 'True'),
            ('caller-cleanup-disagreement', "state['session_error'] == caller.get('cleanup_error', 0)", 'True'),
            ('wrong-causal-precedence', "primary or state['operation_error']", "state['operation_error'] or primary"),
            ('backwards-counter', "after['reads'] >= before['reads']", 'True'),
            ('ownership-drift', 'all(before[name] == after[name] for name in stable)', 'True'),
            ('erased-first-cause', "before[name] == 0 or before[name] == after[name]", 'True'),
            ('false-zero-release', "state['pending'] == 0", 'True'),
            ('incomplete-activation', 'all(state[name] == 1 for name in OWNERS)', 'True'),
            ('omit-getter-read', "'cat ' + PCIE + 'driver_runtime_status; printf", "'true; printf"),
        )
        source = SOURCE.read_text()
        methods = [name for name in unittest.defaultTestLoader.getTestCaseNames(DriverContract)
                   if name not in ('test_source_mutations_fail_by_assertion', 'test_real_association_coordinator_collects_validates_and_resumes')]
        for name, before, after in mutations:
            self.assertEqual(source.count(before), 1, name)
            subject = ModuleType('mutated_driver_result')
            exec(compile(ast.parse(source.replace(before, after, 1)), str(SOURCE), 'exec'), subject.__dict__)
            tests = [DriverContract(method) for method in methods]
            for test in tests: test.subject = subject
            result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite(tests))
            self.assertFalse(result.errors, name)
            self.assertGreater(len(result.failures), 0, name)
            print('N71_DRIVER_RESULT_ASSERTION_KILL', name, flush=True)
        path = ROOT / 'scripts/host/n71_iommu_result.py'
        source = path.read_text()
        for name, before, after in (
            ('coordinator-collection', '+ n71_driver_runtime_result.getter()', "+ ''"),
            ('coordinator-snapshot', "n71_driver_runtime_result.snapshot(session, text, {'caller': caller, 'held': state['iommu']['held']})", 'pass'),
            ('coordinator-continuation', 'n71_driver_runtime_result.resume(session, live_text, prior)', 'pass'),
        ):
            self.assertEqual(source.count(before), 1, name)
            coordinator = ModuleType('mutated_driver_coordinator')
            exec(compile(ast.parse(source.replace(before, after, 1)), str(path), 'exec'), coordinator.__dict__)
            test = DriverContract('test_real_association_coordinator_collects_validates_and_resumes')
            test.coordinator = coordinator
            result = unittest.TextTestRunner(stream=io.StringIO()).run(test)
            self.assertFalse(result.errors, name)
            self.assertGreater(len(result.failures), 0, name)
            print('N71_DRIVER_RESULT_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
