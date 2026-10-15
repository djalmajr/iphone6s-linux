"""Published driver callbacks may change one vector while providers stay retained."""
import ast
import copy
import importlib.util
import io
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from test_n71_driver_runtime_result import ACTIVE, BOOT, allocation_row, row, runtime_session
from test_n71_iommu_result import ACQUIRED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_result as RESULT
SPEC = importlib.util.spec_from_file_location('runtime_association_coordinator', ROOT / 'scripts/host/n71_iommu_result.py')
COORDINATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COORDINATOR)
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_result.py'
COORDINATOR_SOURCE = ROOT / 'scripts/host/n71_iommu_result.py'


def sample(request=None):
    request = request or {}
    msi = COORDINATOR.MSI_ACTIVE | request.get('msi', {})
    iommu = COORDINATOR.IOMMU_ACTIVE | request.get('iommu', {})
    driver = ACTIVE | request.get('driver', {})
    text = 'N71_BOOT_ID ' + request.get('boot', BOOT) + '\n'
    for marker, fields, state in [('N71_PCIE_MSI ', COORDINATOR.MSI_FIELDS, msi),
                                  ('N71_PCIE_IOMMU ', COORDINATOR.IOMMU_FIELDS, iommu)]:
        text += marker + ' '.join(f'{name}={state[name]}' for name in fields) + '\n'
    text += ('N71_HELD_PARAM msi_parent=Y\nN71_HELD_PARAM iommu_parent=Y\nN71_PCIE_HELD held=1\n'
             'N71_PCIE_STATUS ready=1 retained=1 scan_pending=1 reset_pending=1 powered=4 attached=4 '
             'power_put_pending=0 primary_error=' + str(request.get('primary', 0)) + ' cleanup_error=0\n')
    return text + allocation_row(request.get('allocation')) + row(driver) + ACQUIRED


class RuntimeAssociationTests(unittest.TestCase):
    subject = RESULT
    coordinator = COORDINATOR

    def setUp(self):
        self.session = runtime_session()
        patched = patch.object(self.coordinator, 'n71_driver_runtime_result', self.subject)
        patched.start()
        self.addCleanup(patched.stop)

    def accepted(self, request):
        try:
            self.coordinator.resume(self.session, request['current'], request['prior'])
        except (ValueError, KeyError, AttributeError) as error:
            self.fail('Valid retained driver continuation refused: ' + str(error))

    def test_domain_creation_vector_activity_and_domain_retained_after_free(self):
        # Mutations: require legacy equality, remove IRQ budget, or equate a child domain with live vectors.
        sequence = [sample(), sample({'msi': {'child': 1}, 'allocation': {'child': 1}}),
                    sample({'msi': {'child': 1}, 'allocation': {'child': 1, 'slots': 1}}),
                    sample({'msi': {'child': 1, 'mappings': 1}, 'allocation': {'child': 1, 'slots': 1, 'mappings': 1}}),
                    sample({'msi': {'child': 1}, 'allocation': {'child': 1}})]
        before = copy.deepcopy(vars(self.session))
        for prior, current in zip(sequence, sequence[1:]):
            self.accepted({'prior': prior, 'current': current})
        self.assertEqual(vars(self.session), before)
        self.assertEqual(self.coordinator.live(sequence[-1])['msi']['child'], 1)

    def test_retained_driver_keeps_the_original_software_proof_level(self):
        # Mutation: reject live driver allocation or elevate association/publication to delivered IRQ/DMA/radio.
        text = sample({'msi': {'child': 1, 'mappings': 1}, 'allocation': {'child': 1, 'slots': 1, 'mappings': 1}})
        try:
            self.coordinator.retained(self.session, text)
        except ValueError as error:
            self.fail('Proved published driver must remain observable: ' + str(error))
        actual = self.session.result['iommu_association']
        self.assertEqual(actual['observed_devices'], 2)
        for name in ('irq_delivery_verified', 'dma_translation_verified', 'wifi_verified', 'battery_or_charging_verified'):
            self.assertIs(actual[name], False)
        self.assertIs(actual['dma_topology']['physical_translation_verified'], False)

    def test_publication_requires_complete_ledger_and_complete_current_owners(self):
        # Mutations: trust the flag or getter publication alone, or accept vector drift with a partial owner.
        idle = sample()
        allocated = sample({'msi': {'mappings': 1, 'child': 1}, 'allocation': {'slots': 1, 'mappings': 1, 'child': 1}})
        self.session.driver_runtime_journal = []
        for current in (idle, allocated):
            with self.assertRaises(ValueError): self.coordinator.resume(self.session, current, idle)
            with self.assertRaises(ValueError): self.coordinator.retained(self.session, current)
        self.session = runtime_session()
        failed = self.session.driver_runtime_journal[-1]['completion']
        failed['native']['error'] = -16
        failed['native']['published'] = failed['state']['published'] = 0
        with self.assertRaises(ValueError): self.coordinator.resume(self.session, idle, idle)
        self.session = runtime_session()
        for name in RESULT.OWNERS:
            prior = sample({'driver': {name: 0}})
            current = allocated.replace(f'{name}=1', f'{name}=0') if name in ('root_override', 'endpoint_override') else sample({
                'driver': {name: 0}, 'msi': {'child': 1, 'mappings': 1},
                'allocation': {'child': 1, 'slots': 1, 'mappings': 1}})
            with self.subTest(owner=name), self.assertRaises(ValueError):
                self.coordinator.resume(self.session, current, prior)

    def test_extra_vectors_provider_drift_and_early_domain_removal_are_refused(self):
        # Mutations: permit extra grants, provider removal or MSI child destruction before consumers disappear.
        idle = sample()
        invalid = [sample({'msi': {'mappings': 2, 'child': 1}}),
                   sample({'allocation': {'slots': 2, 'mappings': 1, 'child': 1}}),
                   sample({'allocation': {'slots': 1, 'mappings': 2, 'child': 1}}),
                   sample({'msi': {'associated': 0}}),
                   sample({'iommu': {'owner': 0, 'available': 0, 'mapped': 0, 'observed': 0, 'map_checked': 0}})]
        for current in invalid:
            with self.subTest(current=current[:80]), self.assertRaises(ValueError):
                self.coordinator.resume(self.session, current, idle)
        for prior in (sample({'msi': {'child': 1}}), sample({'allocation': {'child': 1}})):
            with self.assertRaises(ValueError): self.coordinator.resume(self.session, idle, prior)

    def test_manual_lease_cannot_be_mixed_even_when_unchanged(self):
        # Mutation: remove manual lease exclusion while the runtime owns the endpoint.
        manual = sample({'allocation': {'owner': 1, 'phase': 1, 'vector': 120, 'default_irq': 8,
                                       'software_enabled': 1, 'slots': 1, 'mappings': 1, 'child': 1}})
        with self.assertRaises(ValueError): self.coordinator.resume(self.session, manual, manual)
        with self.assertRaises(ValueError): self.coordinator.retained(self.session, manual)

    def test_first_cause_and_latched_caller_precedence_are_preserved(self):
        # Mutations: erase the MSI error, allow arbitrary replacement, or forbid the proved caller precedence.
        idle = sample()
        failed = sample({'allocation': {'error': -5}, 'driver': {'error': -5}})
        self.accepted({'prior': idle, 'current': failed})
        prior = sample({'driver': {'operation_error': -110, 'error': -110}, 'allocation': {'error': -5}})
        latched = sample({'driver': {'operation_error': -110, 'error': -110}, 'allocation': {'error': -110}, 'primary': -110})
        self.accepted({'prior': prior, 'current': latched})
        for current in (sample({'driver': {'operation_error': -110, 'error': -110}}),
                        sample({'driver': {'operation_error': -110, 'error': -110}, 'allocation': {'error': -13}})):
            with self.assertRaises(ValueError): self.coordinator.resume(self.session, current, prior)
        for state in ({'operation_error': -13, 'error': -13}, {'operation_error': 0, 'error': 0}):
            with self.assertRaises(ValueError): self.coordinator.resume(self.session, sample({'driver': state}), prior)

    def test_same_boot_immutable_snapshot_and_legacy_strictness(self):
        # Mutations: omit boot/snapshot dispatch or apply the runtime exception to old sessions.
        idle = sample()
        for current in (sample({'boot': '87654321-1234-1234-1234-123456789abc'}),
                        idle + 'N71_BOOT_ID ' + BOOT + '\n', idle.replace('driver_runtime=Y', 'driver_runtime=N'),
                        idle.replace('scan_pending=1', 'scan_pending=0'), idle.replace('N71_BOOT_ID ', 'OTHER_BOOT ')):
            with self.assertRaises(ValueError): self.coordinator.resume(self.session, current, idle)
        legacy = SimpleNamespace(iommu_parent=True)
        old = idle.replace(row(ACTIVE), '')
        self.coordinator.resume(legacy, old, old)
        with self.assertRaises(ValueError):
            self.coordinator.resume(legacy, old.replace('mappings=0 child=0', 'mappings=1 child=1'), old)


class RuntimeAssociationMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeAssociationTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        source = SOURCE.read_text()
        mutations = [
            ('unproved-publication', "not state['published'] or observation['published']", 'True'),
            ('exposure-owners', 'all(state[name] == 1 for name in OWNERS)', 'True'),
            ('iommu-provider', "actual['iommu'] == initial['iommu']", 'True'),
            ('msi-provider', "{name: value for name, value in actual['msi'].items() if name not in ('mappings', 'child')}\n            == {name: value for name, value in initial['msi'].items() if name not in ('mappings', 'child')}", 'True'),
            ('extra-parent-vector', "actual['msi']['mappings'] in (0, 1)", 'True'),
            ('manual-lease', "all(allocation[name] == 0 for name in\n            ('owner', 'phase', 'vector', 'default_irq', 'software_enabled'))", 'True'),
            ('extra-slot', "allocation['slots'] in (0, 1)", 'True'),
            ('extra-allocation-vector', "allocation['mappings'] in (0, 1)", 'True'),
            ('early-allocation-domain-removal', "not before['child'] or after['child']", 'True'),
            ('early-parent-domain-removal', "not observation['before']['msi']['child'] or observation['after']['msi']['child']", 'True'),
            ('erased-allocation-cause', "before['error'] == 0 or before['error'] == after['error'] or override", 'True'),
            ('caller-precedence-refused', ' or override,', ','),
            ('legacy-equality-for-driver', 'if not all(exposed):', 'if True:'),
        ]
        for name, old, new in mutations:
            with self.subTest(name=name):
                target, prefix, suffix = source, '', ''
                if name == 'exposure-owners':
                    node = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'association')
                    lines = source.splitlines(keepends=True)
                    prefix, target, suffix = ''.join(lines[:node.lineno - 1]), ''.join(lines[node.lineno - 1:node.end_lineno]), ''.join(lines[node.end_lineno:])
                self.assertEqual(target.count(old), 1, old)
                module = ModuleType('runtime_association_mutant')
                exec(compile(ast.parse(prefix + target.replace(old, new) + suffix), str(SOURCE), 'exec'), module.__dict__)
                case = type('MutatedRuntimeAssociationTests', (RuntimeAssociationTests,), {'subject': module})
                outcome = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
                self.assertEqual(outcome.errors, [], name)
                self.assertGreater(len(outcome.failures), 0, name)
                print('N71_DRIVER_CONTINUATION_MUTATION_KILLED', name, 'AssertionError')
        source = COORDINATOR_SOURCE.read_text()
        for name, old, new in [
            ('coordinator-retained', 'require(exposed or live(text) == initial,', 'require(live(text) == initial,'),
            ('coordinator-boot', "require(row.group(1) == boot,", 'require(True,'),
            ('coordinator-snapshot', '            snapshot(session, text, True)', '            pass'),
            ('coordinator-publication', "entry['completion']['native']['published'] == 1", 'True'),
        ]:
            with self.subTest(name=name):
                self.assertEqual(source.count(old), 1, old)
                module = ModuleType('runtime_coordinator_mutant')
                exec(compile(ast.parse(source.replace(old, new)), str(COORDINATOR_SOURCE), 'exec'), module.__dict__)
                case = type('MutatedRuntimeCoordinatorTests', (RuntimeAssociationTests,), {'coordinator': module})
                outcome = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
                self.assertEqual(outcome.errors, [], name)
                self.assertGreater(len(outcome.failures), 0, name)
                print('N71_DRIVER_CONTINUATION_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
