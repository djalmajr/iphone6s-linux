"""Interrupted runtime actions recover from live evidence without changing the source."""
import ast
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from test_n71_driver_runtime_stage import BASE, BOOT, INITIAL, PREPARED, native, snapshot as driver_snapshot
import test_n71_held_session as fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_recovery as RECOVERY
import n71_driver_runtime_stage as STAGE
import n71_held_session as HELD
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_recovery.py'
HELD_SOURCE = ROOT / 'scripts/host/n71_held_session.py'
ACQUIRED = BASE + fixture.timestamp(fixture.LINK + fixture.INVENTORY + fixture.ACQUIRED, 10)


class RuntimeRecoveryTests(unittest.TestCase):
    subject = RECOVERY
    held = HELD

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'runtime').mkdir(mode=0o700)
        self.source = self.root / 'runtime' / 'source'
        self.output = self.root / 'runtime' / 'restored'
        for directory in (self.source, self.output): directory.mkdir(mode=0o700)
        self.modules = [({'module': name, 'sha256': hashlib.sha256(name.encode()).hexdigest()}, name.encode())
                        for name in HELD.MODULES]
        self.identity = {'modules': {record['module']: record['sha256'] for record, _ in self.modules}}
        self.saved = self.session(self.source)
        self.journal = HELD.Journal(self.saved, self.identity)
        self.journal.baseline = BASE.splitlines()
        self.saved.driver_runtime_journal = [{'action': 'prepare', 'before': dict(INITIAL),
                                             'history': ACQUIRED.splitlines(), 'completion': None}]
        self.journal.save()
        self.history = ACQUIRED + native('prepare', PREPARED, {'stamp': 500})
        self.state = dict(PREPARED)
        self.boot = BOOT
        self.calls = []
        self.corrupt = lambda text: text
        self.restored = self.session(self.output)

    def session(self, output):
        return SimpleNamespace(output=output, driver_runtime=True, driver_runtime_journal=[],
                               release='7.2.0-iphone6s-dart-serdev-power2',
                               result={'boot_id': BOOT, 'kernel_release': '7.2.0-iphone6s-dart-serdev-power2'},
                               module_directory='/run/n71-link-' + 'a' * 24, modules=self.modules, history=None,
                               reg_attempted=True, activation_attempted=True, pcie_attempted=True,
                               resource_capable=False, resource_attempted=False, iommu_parent=False)

    def text(self, state=None, history=None):
        text = ('N71_BOOT_ID ' + self.boot + '\nN71_PCIE_CMDLINE rdinit=/init pcie_aspm=off\n'
                'N71_HELD_PCIE_PRESENT=1\nN71_HELD_REG_PRESENT=1\nN71_HELD_PCI_EMPTY=0\n'
                'N71_PCIE_HELD held=1\n' + fixture.ACTIVE + fixture.REG_ACTIVE)
        text += ''.join(record['sha256'] + '  ' + self.saved.module_directory + '/' + record['module'] + '\n'
                        for record, _ in self.modules)
        text += ''.join('N71_HELD_PARAM ' + name + '=' + ('Y' if name in HELD.TRUE_PARAMETERS else 'N') + '\n'
                        for name in HELD.TRUE_PARAMETERS + HELD.FALSE_PARAMETERS)
        return text + STAGE.state_text(state or self.state) + (self.history if history is None else history)

    def capture(self, name, command):
        self.calls.append((name, command))
        if name == 'held-cleanup': raise OSError('Cleanup transport interrupted; owners retained')
        self.assertNotIn('rmmod ', command)
        self.assertNotIn(' > ' + STAGE.result.PCIE + 'action', command)
        self.history += fixture.timestamp('N71_REG_ON_READ error=0 value_valid=1 value=81', 1000 + len(self.calls))
        text = self.corrupt(self.text())
        path = self.output / (name + '-private.log')
        with path.open('x') as stream: stream.write(text + '\nSTDERR\n')
        path.chmod(0o600)
        return SimpleNamespace(returncode=0, stdout=text)

    def load(self, source=None):
        self.restored.capture = self.capture
        return self.subject.load(self.restored, {'root': self.root, 'source': source or self.source,
            'identity': self.identity, 'allowed_proofs': HELD.PROOFS,
            'loader': self.held.load_source, 'snapshot': self.held.snapshot})

    def accepted(self, source=None):
        try: return self.load(source)
        except (ValueError, OSError, KeyError, AttributeError) as error:
            self.fail('Proved interrupted action must recover: ' + str(error))

    def files(self):
        return {path.name: (path.read_bytes(), path.stat().st_mode & 0o777) for path in self.source.iterdir()}

    def checkpoint(self, text):
        name = 'held-checkpoint-' + 'b' * 12 + '-private.log'
        path = self.source / name
        path.write_text(text); path.chmod(0o600)
        self.journal.checkpoint = {'name': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        self.journal.save()

    def registered(self, complete=False):
        text = driver_snapshot(PREPARED, self.history, {'exit_value': 0})
        self.journal.proof('driver-runtime-0000-prepare', text)
        if complete:
            self.saved.driver_runtime_journal[-1]['completion'] = STAGE.completion(self.saved,
                self.saved.driver_runtime_journal[-1], {'text': text, 'boot': BOOT, 'mode': 'direct', 'shell_exit': 0})
            self.journal.save()

    def test_missing_checkpoint_and_orphan_proof_recover_only_by_fresh_observation(self):
        # Mutations: require old checkpoint, trust orphan transport exit, overwrite the source or replay a setter.
        orphan = self.source / 'driver-runtime-0000-prepare-proof-private.log'
        orphan.write_text('incomplete orphan; transport result unknown\n'); orphan.chmod(0o600)
        before = self.files()
        data, text, proofs = self.accepted()
        outcome = data['driver_runtime_journal'][-1]['completion']
        self.assertEqual((outcome['mode'], outcome['shell_exit'], outcome['state']), ('observed', None, PREPARED))
        self.assertIn(native('prepare', PREPARED, {'stamp': 500}), proofs['driver-runtime-0000-prepare'])
        self.assertEqual(self.files(), before)
        self.assertEqual(text, proofs['driver-runtime-0000-prepare'])
        fork = Path(self.restored.result['runtime_recovery_source'])
        self.assertNotEqual(fork, self.source)
        self.assertEqual(fork.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in fork.iterdir()))
        HELD.Journal(self.restored, self.identity).proof('driver-runtime-0000-prepare', proofs['driver-runtime-0000-prepare'])
        next_output = self.root / 'runtime' / 'next'; next_output.mkdir(mode=0o700)
        self.restored = self.session(next_output)
        reused, _, _ = self.accepted(fork)
        self.assertEqual(reused['driver_runtime_journal'][-1]['completion']['mode'], 'observed')
        self.assertEqual(len(self.calls), 1)

    def registered_recovery(self, complete):
        self.checkpoint(self.text(INITIAL, ACQUIRED))
        self.registered(complete)
        before = self.files()
        data, text, _ = self.accepted()
        self.assertEqual(data['driver_runtime_journal'][-1]['completion']['mode'], 'direct')
        self.assertEqual(data['driver_runtime_journal'][-1]['completion']['shell_exit'], 0)
        self.assertEqual(self.files(), before)
        self.assertIn('N71_REG_ON_READ', text)

    def test_registered_proof_recovers_an_interrupted_completion_without_inventing_exit(self):
        # Mutation: reject a stale checkpoint when the registered native proof is complete.
        self.registered_recovery(False)

    def test_completed_action_and_stale_checkpoint_preserve_the_direct_proof(self):
        # Mutation: reinterpret the registered direct proof as an observed transport exit.
        self.registered_recovery(True)

    def test_pending_action_already_in_checkpoint_is_observed_without_transport_exit(self):
        # Mutation: require a new native result after the old checkpoint rather than after its intent.
        self.checkpoint(self.text())
        before = self.files()
        data, _, _ = self.accepted()
        completion = data['driver_runtime_journal'][-1]['completion']
        self.assertEqual((completion['mode'], completion['shell_exit']), ('observed', None))
        self.assertEqual(completion['native']['pending'], 1)
        self.assertEqual(self.files(), before)

    def test_checkpoint_prefix_is_preserved_even_after_the_action_is_completed(self):
        # Mutation: ignore the older checkpoint prefix while trusting its valid action proof.
        self.registered(True)
        old = self.history + fixture.timestamp('N71_REG_ON_READ error=0 value_valid=1 value=81', 777)
        data = json.loads(self.journal.path.read_text())
        proof = (self.source / 'driver-runtime-0000-prepare-proof-private.log').read_text()
        request = {'session': self.saved, 'data': data, 'entries': data['driver_runtime_journal'],
                   'proofs': {'driver-runtime-0000-prepare': proof}, 'checkpoint': self.text(PREPARED, old)}
        self.subject.continuation(self.text(PREPARED, old), request)
        changed = self.text(PREPARED, old.replace('[ 777.000000]', '[ 778.000000]'))
        with self.assertRaises(ValueError): self.subject.continuation(changed, request)

    def test_no_native_result_never_promotes_orphan_or_repeats_action(self):
        # Mutation: accept intent without its single native action result.
        self.history = ACQUIRED
        orphan = self.source / 'driver-runtime-0000-prepare-proof-private.log'
        orphan.write_text(driver_snapshot(PREPARED, ACQUIRED + native('prepare', PREPARED), {'exit_value': 0}))
        orphan.chmod(0o600)
        before = self.files()
        with self.assertRaises(ValueError): self.load()
        self.assertEqual(self.files(), before)
        self.assertEqual(list((self.root / 'runtime').glob('n71-driver-recovered-*')), [])
        self.assertEqual(self.restored.driver_runtime_journal, self.saved.driver_runtime_journal)

    def test_source_identity_hash_permissions_and_invalid_existing_checkpoint_refuse_before_read(self):
        # Mutations: ignore identity, attempt types, capabilities, registered hash or checkpoint integrity.
        self.checkpoint(self.text(INITIAL, ACQUIRED)); self.registered()
        path = self.journal.path; original = path.read_text()
        changes = [('identity', {}), ('pcie_attempted', 1), ('iommu_parent', True),
                   ('proofs', {'driver-runtime-0000-prepare': '0' * 64}),
                   ('checkpoint', {'name': self.journal.checkpoint['name'], 'sha256': '0' * 64})]
        for key, value in changes:
            data = json.loads(original); data[key] = value; path.write_text(json.dumps(data))
            with self.subTest(key=key), self.assertRaises(ValueError): self.load()
            self.assertEqual(self.calls, [])
        path.write_text(original); path.chmod(0o644)
        with self.assertRaises(ValueError): self.load()
        self.assertEqual(self.calls, [])

    def test_current_boot_module_hash_history_and_native_owner_drift_refuse(self):
        # Mutations: ignore boot/prefix/extra-operation guards or native/getter ownership coherence.
        text = self.text()
        cases = [text.replace(BOOT, '87654321-1234-1234-1234-123456789abc'),
                 text.replace(self.modules[0][0]['sha256'], '0' * 64),
                 text.replace(BASE, '[ 1.000000] N71_OTHER_BASE private\n'),
                 text + native('publish', PREPARED | {'published': 1}, {'stamp': 600}),
                 text.replace('root=1 endpoint=1', 'root=0 endpoint=1', 1),
                 text + '[ 600.000000] N71_PCIE_RESOURCE_RESTORED error=0 pending=0\n']
        for index, invalid in enumerate(cases):
            self.output = self.root / 'runtime' / ('invalid-' + str(index)); self.output.mkdir(mode=0o700)
            self.restored = self.session(self.output)
            self.corrupt = lambda current, value=invalid: value
            with self.subTest(index=index), self.assertRaises(ValueError): self.load()
        self.assertEqual(list((self.root / 'runtime').glob('n71-driver-recovered-*')), [])

    def test_partial_owners_and_first_cause_remain_in_the_observed_completion(self):
        # Mutation: turn a native refusal into success or discard a partial owner/first cause.
        self.state = INITIAL | dict(pending=1, root=1, operation_error=-5, error=-5, reads=2)
        self.history = ACQUIRED + native('prepare', self.state, {'error': -5, 'stamp': 500})
        before = self.files()
        data, _, _ = self.accepted()
        outcome = data['driver_runtime_journal'][-1]['completion']
        self.assertEqual((outcome['native']['error'], outcome['state']['root'], outcome['state']['error']), (-5, 1, -5))
        self.assertIsNone(outcome['shell_exit'])
        self.assertEqual(self.files(), before)

    def test_no_ledger_and_legacy_missing_checkpoint_keep_the_original_refusal(self):
        # Mutation: enable runtime recovery solely from a flag or admit missing legacy checkpoint.
        self.saved.driver_runtime_journal = []; self.journal.save()
        with self.assertRaises(ValueError): self.load()
        self.assertEqual(self.calls, [])
        self.checkpoint(self.text(INITIAL, ACQUIRED))
        data, _, _ = self.accepted()
        self.assertEqual(data['driver_runtime_journal'], [])
        self.assertEqual(self.calls, [])
        self.restored.driver_runtime = False
        with self.assertRaises(ValueError): self.load()

    def test_real_coordinator_recovers_before_cleanup_without_repeating_prepare(self):
        # Mutation: omit the runtime recovery dispatch and fail before preserving the observed intent.
        self.restored.capture = self.capture
        with patch.object(self.held, 'n71_driver_runtime_recovery', self.subject), contextlib.redirect_stdout(io.StringIO()):
            code = self.held.run(self.restored, self.identity, root=self.root, source=self.source)
        self.assertEqual(code, 1)
        self.assertIn('runtime_recovery_source', self.restored.result)
        self.assertTrue(self.restored.result['driver_intent_reconciled'])
        data = json.loads((self.output / 'held-state-private.json').read_text())
        self.assertEqual(data['driver_runtime_journal'][-1]['completion']['mode'], 'observed')
        self.assertIn('driver-runtime-0000-prepare', data['proofs'])
        self.assertFalse(data['result']['cleanup_verified'])
        self.assertIn('Cleanup transport interrupted', data['result']['held_error'])
        self.assertTrue(all('driver-prepare' not in command for _, command in self.calls))


class RuntimeRecoveryMutations(unittest.TestCase):
    def test_executed_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeRecoveryTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        source = SOURCE.read_text()
        mutations = [
            ('identity', "data.get('identity') == request['identity']", 'True'),
            ('attempt-types', "type(data.get(name)) is bool", 'True'),
            ('capabilities', "data.get('iommu_parent', False) is n71_iommu_result.capable(session)", 'True'),
            ('registered-hash', "hashlib.sha256((directory / (name + '-proof-private.log')).read_bytes()).hexdigest() == expected", 'True'),
            ('checkpoint-hash', "hashlib.sha256((directory / record['name']).read_bytes()).hexdigest() == record['sha256']", 'True'),
            ('history-prefix', 'all(current[:len(anchor)] == anchor for anchor in anchors)', 'True'),
            ('intent-window', "request['entries'][-1]['history'] if pending else proved", 'max(anchors, key=len)'),
            ('unproved-operation', 'all(line in native or re.fullmatch(readback, line) for line in extra)', 'True'),
            ('missing-checkpoint-refused', "if not entries:", "if not entries or prior is None:"),
        ]
        for name, old, new in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(old), 1, name)
                subject = ModuleType('runtime_recovery_mutant')
                exec(compile(ast.parse(source.replace(old, new, 1)), str(SOURCE), 'exec'), subject.__dict__)
                case = type('MutatedRuntimeRecoveryTests', (RuntimeRecoveryTests,), {'subject': subject})
                outcome = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
                self.assertEqual(outcome.errors, [], name)
                self.assertGreater(len(outcome.failures), 0, name)
                print('N71_DRIVER_RECOVERY_MUTATION_KILLED', name, 'AssertionError')
        source = HELD_SOURCE.read_text()
        old = "if n71_driver_runtime_stage.result.capable(session):"
        self.assertEqual(source.count(old), 1)
        subject = ModuleType('runtime_recovery_coordinator_mutant')
        exec(compile(ast.parse(source.replace(old, 'if False:', 1)), str(HELD_SOURCE), 'exec'), subject.__dict__)
        case = type('MutatedRecoveryCoordinatorTests', (RuntimeRecoveryTests,), {'held': subject})
        outcome = unittest.TextTestRunner(stream=io.StringIO()).run(case('test_real_coordinator_recovers_before_cleanup_without_repeating_prepare'))
        self.assertEqual(outcome.errors, [])
        self.assertGreater(len(outcome.failures), 0)
        print('N71_DRIVER_RECOVERY_MUTATION_KILLED coordinator-dispatch AssertionError')


if __name__ == '__main__':
    unittest.main()
