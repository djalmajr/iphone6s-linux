"""Prove durable intent, native outcomes and recovery without replaying effects."""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_result as RESULT
import n71_driver_runtime_stage as STAGE
import n71_held_session as HELD

SOURCE = ROOT / 'scripts/host/n71_driver_runtime_stage.py'
HELD_SOURCE = ROOT / 'scripts/host/n71_held_session.py'
BOOT = '12345678-1234-1234-1234-123456789abc'
INITIAL = dict.fromkeys(RESULT.FIELDS, 0) | dict(requested=1, ready=1, held=1)
PREPARED = INITIAL | dict.fromkeys(('pending',) + RESULT.OWNERS, 1)
PUBLISHED = PREPARED | dict(published=1, reads=7)
RELEASED = INITIAL | dict(published=1, reads=9)
BASE = '[ 1.000000] N71_TEST_BASELINE private\n'


def snapshot(state, history=BASE, options=None):
    options = options or {}
    exit_value, action, boot = options.get('exit_value'), options.get('action', 'prepare'), options.get('boot', BOOT)
    text = 'N71_BOOT_ID ' + boot + '\n' + STAGE.state_text(state)
    if exit_value is not None:
        text += f'N71_DRIVER_ACTION_EXIT action={action} exit={exit_value}\n'
    return text + history


def native(action, state, options=None):
    options = options or {}
    error, stamp = options.get('error', 0), options.get('stamp', 2)
    values = {name: state[name] for name in RESULT.ACTION_FIELDS} | {'error': error}
    return f'[ {stamp}.000000] N71_PCIE_DRIVER_RESULT action={action} ' + ' '.join(
        f'{name}={values[name]}' for name in RESULT.ACTION_FIELDS) + RESULT.SUFFIX + '\n'


class DriverJournalTests(unittest.TestCase):
    subject = STAGE
    held = HELD

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'runtime').mkdir(mode=0o700)
        self.output = self.root / 'runtime' / 'transaction'
        self.output.mkdir(mode=0o700)
        self.session = self.make_session(self.output)
        hook = patch.object(self.held, 'n71_driver_runtime_stage', self.subject)
        hook.start()
        self.addCleanup(hook.stop)
        self.journal = self.held.Journal(self.session, {'modules': {}})
        self.calls = []
        self.response = None
        self.session.capture = self.capture

    def make_session(self, output):
        return SimpleNamespace(output=output, driver_runtime=True, driver_runtime_journal=[],
                               release='7.2.0-iphone6s-dart-serdev-power2',
                               result={'boot_id': BOOT, 'kernel_release': '7.2.0-iphone6s-dart-serdev-power2'},
                               module_directory='/run/n71-link-' + 'a' * 24, modules=[],
                               reg_attempted=False, activation_attempted=False, pcie_attempted=False,
                               resource_capable=False, resource_attempted=False, iommu_parent=False)

    def capture(self, name, command):
        saved = json.loads(self.journal.path.read_text())
        # This is the observable storage boundary before a simulated kernel effect.
        self.assertIs(saved.get('driver_runtime'), True)
        self.assertTrue(saved['driver_runtime_journal'], 'Effect preceded durable intent')
        self.assertEqual(saved['driver_runtime_journal'][-1]['completion'], None)
        self.assertEqual(name, self.subject.stage(len(saved['driver_runtime_journal']) - 1,
                                                saved['driver_runtime_journal'][-1]['action']))
        self.calls.append((name, command))
        if isinstance(self.response, Exception):
            raise self.response
        path = self.output / (name + '-private.log')
        path.write_text(self.response.stdout + '\nSTDERR\n')
        path.chmod(0o600)
        return SimpleNamespace(returncode=self.response.returncode, stdout=self.response.stdout.replace(BASE, ''))

    def act(self, request):
        action, before, after = request['action'], request['before'], request['after']
        history, error, exit_value = request.get('history', BASE), request.get('error', 0), request.get('exit_value', 0)
        next_history = history + native(action, after, {'error': error, 'stamp': len(self.calls) + 2})
        self.response = SimpleNamespace(returncode=exit_value,
                                        stdout=snapshot(after, next_history, {'exit_value': exit_value, 'action': action}))
        return self.subject.act(self.session, self.journal, {'action': action, 'live': snapshot(before, history)}), next_history

    def test_ordered_actions_persist_private_intent_and_native_outcomes(self):
        # Mutations: skip durable intent, forget journal fields, allow publish before preparation.
        prepared, history = self.act({'action': 'prepare', 'before': INITIAL, 'after': PREPARED})
        published, history = self.act({'action': 'publish', 'before': PREPARED, 'after': PUBLISHED, 'history': history})
        released, history = self.act({'action': 'release', 'before': PUBLISHED, 'after': RELEASED, 'history': history})
        self.assertEqual([item['action'] for item in self.session.driver_runtime_journal], list(STAGE.ACTIONS))
        self.assertEqual((prepared['native']['published'], published['native']['published'], released['native']['pending']), (0, 1, 0))
        self.assertEqual(len(self.calls), 3)
        data = json.loads(self.journal.path.read_text())
        self.assertEqual(data['driver_runtime_journal'], self.session.driver_runtime_journal)
        self.assertEqual(set(data['proofs']), set(self.subject.extra_proofs(self.session, data)))
        for path in [self.journal.path] + list(self.output.glob('*-proof-private.log')):
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            self.subject.act(self.session, self.journal, {'action': 'release', 'live': snapshot(RELEASED, history)})
        self.assertEqual(len(self.calls), 3)

    def test_interrupted_intent_is_reconciled_by_observation_without_capture(self):
        # Mutations: replay an incomplete intent or invent a successful SSH exit after transport loss.
        self.response = OSError('transport lost')
        with self.assertRaises(OSError):
            self.subject.act(self.session, self.journal, {'action': 'prepare', 'live': snapshot(INITIAL)})
        with self.assertRaises(ValueError):
            self.subject.act(self.session, self.journal, {'action': 'prepare', 'live': snapshot(INITIAL)})
        self.assertEqual(len(self.calls), 1)
        for text in (snapshot(INITIAL), snapshot(PREPARED, BASE + native('prepare', PREPARED), {'boot': 'a' * 36})):
            with self.assertRaises(ValueError): self.subject.reconcile(self.session, self.journal, text)
        outcome = self.subject.reconcile(self.session, self.journal, snapshot(PREPARED, BASE + native('prepare', PREPARED)))
        self.assertEqual(outcome['mode'], 'observed')
        self.assertIsNone(outcome['shell_exit'])
        self.assertEqual(outcome['state'], PREPARED)
        self.assertEqual(len(self.calls), 1)

    def test_pending_proof_recovers_after_crash_for_both_modes(self):
        # Mutation: demand replay when the proof exists but its completion update did not persist.
        for mode in ('direct', 'observed'):
            with self.subTest(mode=mode):
                history = BASE + native('prepare', PREPARED)
                text = snapshot(PREPARED, history, {'exit_value': 0 if mode == 'direct' else None})
                entry = dict(action='prepare', before=INITIAL, history=BASE.splitlines(), completion=None)
                data = dict(driver_runtime=True, driver_runtime_journal=[entry], result={'boot_id': BOOT})
                restored = self.make_session(self.output)
                try:
                    self.subject.load_source(restored, data, {'driver-runtime-0000-prepare': text})
                except ValueError as error:
                    self.fail('Existing native proof must recover without replay: ' + str(error))
                actual = restored.driver_runtime_journal[0]['completion']
                self.assertEqual(actual['mode'], mode)
                self.assertEqual(actual['shell_exit'], 0 if mode == 'direct' else None)
                self.assertEqual(actual['native']['pending'], 1)

    def test_real_held_source_loader_preserves_proof_and_rejects_tampered_summary(self):
        # Mutations: drop source-loader integration or trust a journal summary instead of native proof.
        _, history = self.act({'action': 'prepare', 'before': INITIAL, 'after': PREPARED})
        name = 'held-checkpoint-' + 'b' * 12 + '-private.log'
        checkpoint = self.output / name
        checkpoint.write_text(snapshot(PREPARED, history))
        checkpoint.chmod(0o600)
        self.journal.checkpoint = {'name': name, 'sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
        self.journal.baseline = BASE.splitlines()
        self.journal.save()
        restored = self.make_session(self.output)
        _, _, proofs = self.held.load_source(restored, self.root, self.output, {'modules': {}})
        self.assertEqual(restored.driver_runtime_journal, self.session.driver_runtime_journal)
        self.assertIn('driver-runtime-0000-prepare', proofs)
        data = json.loads(self.journal.path.read_text())
        data['driver_runtime_journal'][0]['completion']['state']['reads'] = 7
        self.journal.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.held.load_source(self.make_session(self.output), self.root, self.output, {'modules': {}})

    def test_refusal_and_partial_owners_keep_first_cause_for_release(self):
        # Mutations: discard partial ownership or overwrite the cause with a later release failure.
        partial = INITIAL | dict(pending=1, root=1, operation_error=-5, error=-5, reads=2)
        outcome, history = self.act({'action': 'prepare', 'before': INITIAL, 'after': partial, 'error': -5, 'exit_value': 1})
        self.assertEqual(outcome['native']['error'], -5)
        refused = partial | dict(reads=3)
        outcome, history = self.act({'action': 'release', 'before': partial, 'after': refused,
                                    'history': history, 'error': -16, 'exit_value': 1})
        self.assertEqual((outcome['native']['error'], outcome['state']['error'], outcome['state']['root']), (-16, -5, 1))
        final = INITIAL | dict(operation_error=-5, error=-5, reads=4)
        outcome, _ = self.act({'action': 'release', 'before': refused, 'after': final, 'history': history})
        self.assertEqual((outcome['native']['pending'], outcome['state']['error']), (0, -5))

    def test_proof_drift_and_exit_disagreement_leave_intent_pending(self):
        # Mutations: accept owner drift, backwards reads, missing first cause or mismatched exits/history.
        before = PREPARED | dict(reads=5, operation_error=-5, error=-5)
        entry = dict(action='release', before=before, history=BASE.splitlines(), completion=None)
        final = INITIAL | dict(reads=6, operation_error=-5, error=-5)
        text = snapshot(final, BASE + native('release', final), {'exit_value': 0, 'action': 'release'})
        good = {'text': text, 'boot': BOOT, 'mode': 'direct', 'shell_exit': 0}
        self.assertEqual(self.subject.completion(self.session, entry, good)['state']['error'], -5)
        invalid = [good | {'shell_exit': 255}, good | {'mode': 'observed', 'shell_exit': None},
                   good | {'text': text.replace(BASE, '')}, good | {'text': text + native('release', final)},
                   good | {'text': text.replace(BASE, BASE.replace('BASELINE', 'CHANGED'))},
                   good | {'text': text.replace('action=release exit=0', 'action=prepare exit=0')},
                   good | {'text': text.replace('exit=0', 'exit=00')},
                   good | {'text': text.replace(' root=0 endpoint=0', ' root=1 endpoint=0', 1)}]
        for state in (final | dict(reads=4), final | dict(error=-13), final | dict(operation_error=0),
                      final | dict(pending=1, root=1)):
            invalid.append(good | {'text': snapshot(state, BASE + native('release', final), {'exit_value': 0, 'action': 'release'})})
        for observation in invalid:
            with self.subTest(observation=observation['text'][:80]), self.assertRaises(ValueError):
                self.subject.completion(self.session, entry, observation)
        with self.assertRaises(ValueError):
            self.subject.completion(self.session, entry, good | {'text': text.replace('exit=0', 'exit=1'), 'shell_exit': 1})

    def test_schema_order_history_and_fsync_failure_stop_before_effect(self):
        # Mutations: weaken selection/schema/order/history or send an effect after fsync failed.
        for data in ({'driver_runtime': 1}, {'driver_runtime': False},
                     {'driver_runtime': True, 'driver_runtime_journal': {}},
                     {'driver_runtime': True, 'driver_runtime_journal': [dict(action='publish', before=INITIAL,
                                                                             history=BASE.splitlines(), completion=None)]}):
            with self.assertRaises(ValueError): self.subject.ledger(self.session, data)
        with patch.object(self.held.os, 'fsync', side_effect=OSError('disk sync failed')):
            with self.assertRaises(OSError):
                self.subject.act(self.session, self.journal, {'action': 'prepare', 'live': snapshot(INITIAL)})
        self.assertEqual(self.calls, [])
        self.assertEqual(json.loads(self.journal.path.read_text()).get('driver_runtime_journal'), [])
        self.session.driver_runtime_journal = []
        self.response = SimpleNamespace(returncode=0, stdout=snapshot(PREPARED, BASE + native('prepare', PREPARED), {'exit_value': 0}))
        original = self.held.os.fsync
        def fail_directory(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError('directory sync failed')
            original(descriptor)
        with patch.object(self.held.os, 'fsync', side_effect=fail_directory):
            with self.assertRaises(OSError):
                self.subject.act(self.session, self.journal, {'action': 'prepare', 'live': snapshot(INITIAL)})
        self.assertEqual(self.calls, [])

    def test_failed_release_cannot_be_followed_by_publication(self):
        # Mutation: permit publication after a refused release instead of retrying only release.
        _, history = self.act({'action': 'prepare', 'before': INITIAL, 'after': PREPARED})
        _, history = self.act({'action': 'release', 'before': PREPARED, 'after': PREPARED,
                               'history': history, 'error': -16, 'exit_value': 1})
        with self.assertRaises(ValueError):
            self.subject.act(self.session, self.journal, {'action': 'publish', 'live': snapshot(PREPARED, history)})
        self.assertEqual(len(self.calls), 2)

    def test_posix_command_writes_only_selected_action_with_live_boot_guard(self):
        # Mutations: send another action, remove immutable/boot guard or stop collecting native readback.
        sysfs = self.root / 'sysfs'
        sysfs.mkdir(mode=0o700)
        for name, content in {'driver_runtime': 'Y\n', 'held': 'held=1\n', 'action': '',
                              'driver_runtime_status': STAGE.state_text(PREPARED).splitlines()[0].removeprefix(RESULT.MARKER) + '\n'}.items():
            (sysfs / name).write_text(content)
        dmesg = self.root / 'dmesg'
        dmesg.write_text(BASE + native('prepare', PREPARED))
        with patch.object(RESULT, 'PCIE', str(sysfs) + '/'):
            command = self.subject.command(self.session, 'prepare')
        shell = ('uname() { printf "%s\\n" "' + self.session.release + '"; }; '
                 'cat() { if test "$1" = /proc/sys/kernel/random/boot_id; then printf "%s\\n" "' + BOOT
                 + '"; else command cat "$@"; fi; }; dmesg() { command cat "' + str(dmesg) + '"; }; ')
        subprocess.run(['sh', '-n'], input=command, text=True, check=True)
        process = subprocess.run(['sh', '-c', shell + command], text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual((sysfs / 'action').read_text(), 'driver-prepare\n')
        self.assertEqual(RESULT.live(process.stdout, required=True), PREPARED)
        (sysfs / 'action').write_text('unchanged')
        (sysfs / 'driver_runtime').write_text('N\n')
        process = subprocess.run(['sh', '-c', shell + command], text=True, capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual((sysfs / 'action').read_text(), 'unchanged')
        (sysfs / 'driver_runtime').write_text('Y\n')
        process = subprocess.run(['sh', '-c', shell.replace(BOOT, 'a' * 36) + command], text=True, capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual((sysfs / 'action').read_text(), 'unchanged')


class DriverJournalMutations(unittest.TestCase):
    def test_executed_source_mutations_fail_by_assertion(self):
        source = SOURCE.read_text()
        mutations = [
            ('selection', "data.get('driver_runtime', False) is selected", 'True'),
            ('publish-order', "previous['action'] == 'prepare' and previous['completion'] is not None\n                and previous['completion']['native']['error'] == 0", "previous['completion'] is not None"),
            ('intent-save', '    journal.save()\n    name = stage(len(entries) - 1', '    name = stage(len(entries) - 1'),
            ('native-owner', "all(native[name] == state[name] for name in ('pending', 'published') + result.OWNERS)", 'True'),
            ('counter', "state['reads'] >= entry['before']['reads']", 'True'),
            ('first-cause', 'old == 0 or old == new', 'True'),
            ('history-prefix', "history[:len(before)] == before", 'True'),
            ('ssh-exit', "int(rows[0]) == observation['shell_exit']", 'True'),
            ('native-exit', "(int(rows[0]) == 0) == (native['error'] == 0)", 'True'),
            ('saved-summary', 'saved is None or saved == proved', 'True'),
            ('observed-exit', "observation['shell_exit'] is None and EXIT not in text", 'True'),
            ('incomplete-observed-proof', "('observed', None)", "('direct', 0)"),
        ]
        for name, old, new in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(old), 1, old)
                module = ModuleType('driver_stage_mutant')
                exec(compile(ast.parse(source.replace(old, new)), str(SOURCE), 'exec'), module.__dict__)
                case = type('MutatedDriverJournalTests', (DriverJournalTests,), {'subject': module})
                outcome = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
                self.assertEqual(outcome.errors, [], name)
                self.assertGreater(len(outcome.failures), 0, name)
                print('N71_DRIVER_JOURNAL_MUTATION_KILLED', name, 'AssertionError')
        held_source = HELD_SOURCE.read_text()
        hooks = [
            ('journal-fields', '                 **n71_driver_runtime_stage.fields(session),\n', ''),
            ('source-loader', '    n71_driver_runtime_stage.load_source(session, data, verified)', '    pass'),
            ('directory-sync', '                os.fsync(descriptor)', '                pass'),
        ]
        for name, old, new in hooks:
            with self.subTest(name=name):
                self.assertEqual(held_source.count(old), 1, old)
                module = ModuleType('held_driver_hook_mutant')
                exec(compile(ast.parse(held_source.replace(old, new)), str(HELD_SOURCE), 'exec'), module.__dict__)
                case = type('MutatedHeldDriverJournalTests', (DriverJournalTests,), {'held': module})
                outcome = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(case))
                self.assertEqual(outcome.errors, [], name)
                self.assertGreater(len(outcome.failures), 0, name)
                print('N71_DRIVER_JOURNAL_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
