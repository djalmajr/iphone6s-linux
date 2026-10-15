"""Exact passive getter, read-only shell and same-boot ownership contracts."""
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
SOURCE = ROOT / 'scripts/host/n71_msi_allocation_result.py'
SPEC = importlib.util.spec_from_file_location('allocation_result_under_test', SOURCE)
RESULT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESULT)
FIELDS = ('ready', 'held', 'owner', 'phase', 'vector', 'default_irq', 'software_enabled',
          'slots', 'mappings', 'child', 'error', 'session_error')
EMPTY = dict.fromkeys(FIELDS, 0)
ACTIVE = dict(zip(FIELDS, (1, 1, 1, 1, 320, 19, 1, 1, 1, 1, 0, 0)))


def row(state):
    return 'N71_PCIE_MSI_ALLOCATION ' + ' '.join(f'{name}={state[name]}' for name in FIELDS) + '\n'


class AllocationContract(unittest.TestCase):
    subject = RESULT

    def test_states_and_partial_errors(self):
        # Mutations killed: omit exact fields, allow ownership without a host or lose error history.
        partial = ACTIVE | dict(vector=0, software_enabled=0, slots=0, mappings=0, error=-5)
        stopped = ACTIVE | dict(phase=2, software_enabled=0, slots=0, mappings=0, error=-13, session_error=-5)
        for state in (EMPTY, EMPTY | dict(error=-13, session_error=-5), ACTIVE, partial, stopped,
                      EMPTY | dict(ready=1, held=1, child=1), EMPTY | dict(ready=1, slots=255, mappings=8)):
            self.assertEqual(self.subject.live(row(state)), state)
        self.assertIsNone(self.subject.live('legacy getter without allocation\n'))

    def test_bad_shapes_and_ranges(self):
        # Mutations killed: weaken canonical shape, bounds, booleans, errno or removed-host checks.
        invalid = [row(ACTIVE) * 2, row(ACTIVE).replace(' vector=320', ''),
                   row(ACTIVE).replace('phase=1 vector=320', 'vector=320 phase=1'),
                   row(ACTIVE).replace('owner=1', 'owner=01'), row(EMPTY).replace('error=0', 'error=-0'),
                   row(ACTIVE).rstrip() + ' unexpected=1\n', 'prefix ' + row(ACTIVE), 'x' * (2 * 1024 * 1024 + 1)]
        for name, values in {'ready':(-1, 2), 'held':(-1, 2), 'owner':(-1, 2),
                             'software_enabled':(-1, 2), 'child':(-1, 2), 'phase':(-1, 3),
                             'vector':(-1, 2147483648), 'default_irq':(-1, 2147483648),
                             'slots':(-1, 256), 'mappings':(-1, 9),
                             'error':(-4096, 1), 'session_error':(-4096, 1)}.items():
            invalid += [row(ACTIVE | {name:value}) for value in values]
        invalid += [row(ACTIVE | dict(ready=0, held=0)), row(EMPTY | dict(held=1))]
        for text in invalid:
            with self.subTest(text=text[:160]), self.assertRaises(ValueError):
                self.subject.live(text)

    def test_snapshot_links_caller(self):
        # Mutations killed: drop host/held/cleanup/first-error agreement with the real caller.
        caller = dict(scan_pending=1, cleanup_error=-5, primary_error=-13)
        state = ACTIVE | dict(error=-13, session_error=-5)
        self.subject.snapshot(row(state), caller, 1)
        self.subject.snapshot('legacy getter\n', caller, 1)
        for changed in (caller | dict(scan_pending=0), caller | dict(cleanup_error=0),
                        caller | dict(primary_error=-5)):
            with self.assertRaises(ValueError): self.subject.snapshot(row(state), changed, 1)
        with self.assertRaises(ValueError): self.subject.snapshot(row(state), caller, 0)
        self.subject.snapshot(row(EMPTY | dict(error=-13)), dict(primary_error=-13), 0)

    def test_continuation_conserves_presence_and_state(self):
        # Mutation killed: ignore a changed vector/owner or missing getter before continuation.
        self.subject.resume(row(ACTIVE), row(ACTIVE))
        self.subject.resume('legacy\n', 'legacy\n')
        for changed in ('legacy\n', row(ACTIVE | dict(vector=321)), row(ACTIVE | dict(owner=0))):
            with self.assertRaises(ValueError): self.subject.resume(changed, row(ACTIVE))
        with self.assertRaises(ValueError): self.subject.resume(row(EMPTY), 'legacy\n')

    def test_shell_reads_only_when_available(self):
        # Mutation killed: omit the getter read; the present-file contract then returns no state.
        with tempfile.TemporaryDirectory(prefix='n71-msi-getter-') as directory:
            folder = Path(directory)
            command = self.subject.getter().replace(self.subject.PCIE, str(folder) + '/')
            absent = subprocess.run(['sh', '-c', command], capture_output=True, text=True, timeout=5)
            self.assertEqual((absent.returncode, absent.stdout, absent.stderr), (0, '', ''))
            getter = folder / 'msi_allocation'; getter.write_text(row(ACTIVE).split(' ', 1)[1])
            present = subprocess.run(['sh', '-c', command], capture_output=True, text=True, timeout=5)
            self.assertEqual((present.returncode, present.stdout, present.stderr), (0, row(ACTIVE), ''))
            self.assertEqual(getter.read_text(), row(ACTIVE).split(' ', 1)[1])
            self.assertEqual(list(folder.iterdir()), [getter])

    def test_actual_association_coordinator_uses_optional_getter_and_resume(self):
        import n71_iommu_result
        # Mutations killed: drop any new producer, snapshot or continuity call in the actual coordinator.
        association = getattr(self, 'association', n71_iommu_result)
        session = SimpleNamespace(iommu_parent=True)
        self.assertIn(self.subject.getter(), association.getter(session))
        self.assertEqual(association.getter(SimpleNamespace(iommu_parent=False)), '')
        association.resume(session, row(ACTIVE), row(ACTIVE))
        with self.assertRaises(ValueError): association.resume(session, row(EMPTY), row(ACTIVE))
        text = ('N71_PCIE_MSI requested=1 ready=1 held=1 associated=1 owner=1 domain=1 mappings=0 child=0 session_error=0\n'
                'N71_PCIE_IOMMU requested=1 ready=1 held=1 owner=1 available=1 mapped=1 observed=2 map_checked=1 session_error=0\n'
                'N71_HELD_PARAM msi_parent=Y\nN71_HELD_PARAM iommu_parent=Y\nN71_PCIE_HELD held=1\n'
                'N71_PCIE_STATUS ready=1 retained=1 scan_pending=1 reset_pending=1 powered=4 attached=4 power_put_pending=0 primary_error=0 cleanup_error=0\n')
        association.snapshot(session, text + row(EMPTY | dict(ready=1, held=1)), True)
        with self.assertRaises(ValueError): association.snapshot(session, text + row(EMPTY), True)

    def test_source_mutations_fail_by_assertion(self):
        mutations = (
            ('duplicate-record', 'len(rows) == text.count(MARKER) == 1', 'len(rows) == text.count(MARKER)'),
            ('noncanonical', 'rows[0].group() == MARKER +', 'True or rows[0].group() == MARKER +'),
            ('nonboolean', 'state[name] in (0, 1)', 'state[name] in (0, 1, 2)'),
            ('phase-overflow', "state['phase'] <= 2", "state['phase'] <= 3"),
            ('irq-overflow', 'state[name] <= 2147483647', 'state[name] <= 4294967295'),
            ('slot-overflow', "state['slots'] <= 0xff", "state['slots'] <= 0x1ff"),
            ('mapping-overflow', "state['mappings'] <= 8", "state['mappings'] <= 9"),
            ('lost-host', "state['ready'] == caller.get('scan_pending', 0)", 'True'),
            ('lost-held', "state['held'] == held", 'True'),
            ('lost-cleanup-error', "state['session_error'] == caller.get('cleanup_error', 0)", 'True'),
            ('lost-first-error', "not caller.get('primary_error', 0) or", 'True or'),
            ('lost-resume', 'live(current) == live(prior)', 'True'),
            ('omitted-shell-read', "return ('if test -e ' + PCIE + 'msi_allocation; then printf \"' + MARKER + '\"; '\n            'cat ' + PCIE + 'msi_allocation; fi; ')", "return ''"),
        )
        source = SOURCE.read_text()
        methods = ('test_states_and_partial_errors', 'test_bad_shapes_and_ranges',
                   'test_snapshot_links_caller', 'test_continuation_conserves_presence_and_state',
                   'test_shell_reads_only_when_available')
        for name, before, after in mutations:
            self.assertEqual(source.count(before), 1, name)
            changed = source.replace(before, after, 1)
            subject = ModuleType('mutated_allocation_result')
            exec(compile(ast.parse(changed), str(SOURCE), 'exec'), subject.__dict__)
            tests = [AllocationContract(method) for method in methods]
            for test in tests: test.subject = subject
            result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite(tests))
            self.assertFalse(result.errors, name)
            self.assertGreater(len(result.failures), 0, name)
            print('N71_MSI_GETTER_ASSERTION_KILL', name, flush=True)
        coordinator = ROOT / 'scripts/host/n71_iommu_result.py'
        source = coordinator.read_text()
        for name, before, after in (
            ('omitted-collection', '+ n71_msi_allocation_result.getter()', "+ ''"),
            ('omitted-snapshot', "n71_msi_allocation_result.snapshot(text, caller, state['iommu']['held'])", 'pass'),
            ('omitted-continuation', 'n71_msi_allocation_result.resume(live_text, prior)', 'pass'),
        ):
            self.assertEqual(source.count(before), 1, name)
            association = ModuleType('mutated_association_coordinator')
            exec(compile(ast.parse(source.replace(before, after, 1)), str(coordinator), 'exec'), association.__dict__)
            test = AllocationContract('test_actual_association_coordinator_uses_optional_getter_and_resume')
            test.association = association
            result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([test]))
            self.assertFalse(result.errors, name)
            self.assertGreater(len(result.failures), 0, name)
            print('N71_MSI_GETTER_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
