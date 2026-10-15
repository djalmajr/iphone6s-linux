"""Persist WCC intent and recover exact ownership from same-boot remote receipts."""
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from test_n71_driver_runtime_stage import BASE, BOOT, INITIAL, PREPARED, native, snapshot as native_snapshot
import test_n71_driver_runtime_stage as native_fixture
import test_n71_held_session as held_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_modules as MODULES
import n71_driver_module_stage as STAGE
import n71_driver_runtime_stage as DRIVER
import n71_driver_runtime_recovery as RECOVERY
import n71_held_session as HELD
SOURCE = ROOT / 'scripts/host/n71_driver_module_stage.py'


class ModuleJournalTests(unittest.TestCase):
    subject = STAGE
    recovery = RECOVERY

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); (self.root / 'runtime').mkdir(mode=0o700)
        self.output = self.root / 'runtime' / 'transaction'; self.output.mkdir(mode=0o700)
        self.session = self.make_session(self.output)
        patched = patch.object(HELD, 'n71_driver_module_stage', self.subject); patched.start(); self.addCleanup(patched.stop)
        self.journal = HELD.Journal(self.session, {'modules': {}}); self.journal.baseline = BASE.splitlines()
        self.kernel_history = BASE + native('prepare', PREPARED)
        proof = native_snapshot(PREPARED, self.kernel_history, {'exit_value': 0})
        entry = dict(action='prepare', before=dict(INITIAL), history=BASE.splitlines(), completion=None)
        entry['completion'] = DRIVER.completion(self.session, entry, {'text': proof, 'boot': BOOT, 'mode': 'direct', 'shell_exit': 0})
        self.session.driver_runtime_journal = [entry]; self.journal.proof('driver-runtime-0000-prepare', proof)
        self.present = set(); self.receipts = {}; self.calls = []; self.refs = {}; self.exception = None
        self.exit_code = 0; self.ssh_exit = None; self.current_driver = dict(PREPARED); self.complete_receipt = True
        self.session.capture = self.capture

    def make_session(self, output):
        session = native_fixture.DriverJournalTests('test_ordered_actions_persist_private_intent_and_native_outcomes').make_session(output)
        session.driver_modules = MODULES.qualified(ROOT); session.driver_module_journal = []
        return session

    def text(self):
        states = {}
        for name in MODULES.OBSERVED:
            holders = sorted(record['name'] for record in self.session.driver_modules
                             if record['name'] in self.present and name in record['depends'])
            states[name] = {'present': int(name in self.present), 'state': 'live' if name in self.present else '-',
                            'refs': len(holders) + self.refs.get(name, 0), 'holders': holders}
        state = {'boot': BOOT, 'directory': self.session.module_directory,
                 'registered': int('brcmfmac' in self.present), 'states': states}
        text = 'N71_BOOT_ID ' + BOOT + '\n' + self.subject.state_text(self.session.driver_modules, state)
        text += DRIVER.state_text(self.current_driver) + self.kernel_history
        if self.session.driver_module_journal:
            entry = self.session.driver_module_journal[-1]
            name = MODULES.tag(self.subject.operation(self.session, len(self.session.driver_module_journal) - 1, entry))
            text += self.receipts.get(name, 'N71_WLAN_RECEIPT_MISSING\n')
        return text

    def capture(self, name, command):
        saved = json.loads(self.journal.path.read_text())
        self.assertTrue(saved['driver_module_journal'], 'Kernel effect preceded durable intent')
        entry = saved['driver_module_journal'][-1]
        self.assertEqual(entry['completion'], None, 'Kernel effect preceded durable intent')
        self.assertEqual(saved['driver_module_manifest'], self.session.driver_modules)
        self.calls.append((name, command))
        index = len(saved['driver_module_journal']) - 1
        record = self.session.driver_modules[MODULES.NAMES.index(entry['name'])]
        started = ('N71_WLAN_STARTED index=' + str(index) + ' action=' + entry['action'] + ' name=' + entry['name']
                   + ' boot=' + BOOT + ' sha256=' + record['sha256'] + '\n')
        self.receipts[name] = started
        if self.exception == 'before': raise OSError('transport before effect')
        if self.exit_code == 0:
            if entry['action'] == 'load': self.present.add(entry['name'])
            else: self.present.remove(entry['name'])
        if self.complete_receipt:
            self.receipts[name] += ('N71_WLAN_EXIT index=' + str(index) + ' action=' + entry['action']
                                    + ' name=' + entry['name'] + ' exit=' + str(self.exit_code) + '\n')
        if self.exception == 'after': raise OSError('transport after effect')
        text = self.text(); path = self.output / (name + '-private.log')
        path.write_text(text + '\nSTDERR\n'); path.chmod(0o600)
        return SimpleNamespace(returncode=self.exit_code if self.ssh_exit is None else self.ssh_exit,
                               stdout='filtered collector output')

    def snapshot(self, session, name):
        self.kernel_history += '[ ' + str(100 + len(self.calls)) + '.000000] N71_REG_ON_READ error=0 value_valid=1 value=81\n'
        return self.text(), (1, 1, 0)

    def act(self, action, name):
        return self.subject.act(self.session, self.journal, {'action': action, 'name': name,
                                'live': self.text(), 'snapshot': self.snapshot})


    def publish(self):
        self.current_driver = PREPARED | dict(published=1)
        history = self.kernel_history + native('publish', self.current_driver, {'stamp': 400})
        proof = native_snapshot(self.current_driver, history, {'exit_value': 0, 'action': 'publish'})
        entry = dict(action='publish', before=dict(PREPARED), history=self.kernel_history.splitlines(), completion=None)
        entry['completion'] = DRIVER.completion(self.session, entry, {'text': proof, 'boot': BOOT, 'mode': 'direct', 'shell_exit': 0})
        self.session.driver_runtime_journal.append(entry); self.journal.proof('driver-runtime-0001-publish', proof)
        self.kernel_history = history

    def full_text(self):
        text = ('N71_PCIE_CMDLINE rdinit=/init pcie_aspm=off\nN71_HELD_PCIE_PRESENT=1\n'
                'N71_HELD_REG_PRESENT=1\nN71_HELD_PCI_EMPTY=0\nN71_PCIE_HELD held=1\n'
                + held_fixture.ACTIVE + held_fixture.REG_ACTIVE)
        for name in HELD.TRUE_PARAMETERS + HELD.FALSE_PARAMETERS:
            text += 'N71_HELD_PARAM ' + name + '=' + ('Y' if name in HELD.TRUE_PARAMETERS else 'N') + '\n'
        return text + self.text()

    def recover(self):
        output = self.root / 'runtime' / ('restored-' + str(len(list((self.root / 'runtime').iterdir()))))
        output.mkdir(mode=0o700); restored = self.make_session(output); reads = []
        def capture(name, command):
            self.assertNotIn('insmod ', command); self.assertNotIn('rmmod ', command)
            self.assertNotIn(' > ' + DRIVER.result.PCIE + 'action', command)
            self.assertIn('wlan-module-', command); reads.append(name)
            self.kernel_history += '[ 600.000000] N71_REG_ON_READ error=0 value_valid=1 value=81\n'
            text = self.full_text(); path = output / (name + '-private.log')
            path.write_text(text + '\nSTDERR\n'); path.chmod(0o600)
            return SimpleNamespace(returncode=0, stdout='filtered collector output')
        restored.capture = capture
        result = self.recovery.load(restored, {'root': self.root, 'source': self.output,
            'identity': {'modules': {}}, 'allowed_proofs': HELD.PROOFS,
            'loader': HELD.load_source, 'snapshot': HELD.snapshot})
        return restored, result, reads
    def accepted(self, function, *args):
        try: return function(*args)
        except (ValueError, KeyError, AttributeError, OSError) as error:
            self.fail('Proved module outcome refused: ' + str(error))

    def test_ordered_load_and_reverse_unload_persist_only_the_proved_owners(self):
        # Mutations: omit intent/proof save, reorder modules or discard the real operation/transport result.
        for name in MODULES.NAMES:
            result = self.accepted(self.act, 'load', name)
            self.assertTrue(result['applied']); self.assertEqual((result['mode'], result['shell_exit'], result['operation_exit']), ('direct', 0, 0))
        self.publish()
        observation = {'after': dict(self.current_driver), 'before': dict(PREPARED), 'history': self.kernel_history.splitlines()}
        invalid_publication = dict(observation, history=[line.replace('action=publish', 'action=release') for line in observation['history']])
        with self.assertRaises(ValueError): self.subject.driver_continuation(self.session, invalid_publication)
        invalid_counter = dict(observation, before=PREPARED | dict(reads=20))
        with self.assertRaises(ValueError): self.subject.driver_continuation(self.session, invalid_counter)
        for name in reversed(MODULES.NAMES): self.accepted(self.act, 'unload', name)
        self.assertEqual(self.present, set())
        data = json.loads(self.journal.path.read_text())
        self.assertEqual(len(data['driver_module_journal']), 10)
        self.assertEqual(len([name for name in data['proofs'] if name.startswith('wlan-module-')]), 10)
        self.assertEqual(data['driver_module_journal'], self.session.driver_module_journal)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.output.glob('*proof-private.log')))
        with self.assertRaises(ValueError): self.act('load', 'rfkill')
        self.assertEqual(len(self.calls), 10)
        invalid = copy.deepcopy(self.subject.fields(self.session))
        invalid['driver_module_journal'][5]['history'] = invalid['driver_module_journal'][4]['history']
        with self.assertRaises(ValueError): self.subject.ledger(self.session, invalid)

    def test_pending_module_source_recovers_read_only_and_preserves_orphan_and_old_checkpoint(self):
        # Mutations: skip pending-module recovery, trust an orphan or replay insmod after its effect.
        name = 'held-checkpoint-' + 'b' * 12 + '-private.log'; checkpoint = self.output / name
        checkpoint.write_text(self.full_text()); checkpoint.chmod(0o600)
        self.journal.checkpoint = {'name': name, 'sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
        self.exception = 'after'
        with self.assertRaises(OSError): self.act('load', 'rfkill')
        orphan = self.output / 'wlan-module-0000-load-rfkill-proof-private.log'
        orphan.write_text('unregistered transport output; never promote\n'); orphan.chmod(0o600)
        source = {path.name: (path.read_bytes(), path.stat().st_mode & 0o777) for path in self.output.iterdir()}
        restored, (data, text, proofs), reads = self.accepted(self.recover)
        result = data['driver_module_journal'][-1]['completion']
        self.assertEqual((result['mode'], result['operation_exit'], result['shell_exit'], result['applied']), ('observed', 0, None, True))
        self.assertTrue(restored.result['driver_module_intent_reconciled']); self.assertFalse(restored.result['driver_intent_reconciled'])
        self.assertEqual(proofs['wlan-module-0000-load-rfkill'], text)
        self.assertEqual(reads, ['held-runtime-recovery-live']); self.assertEqual(len(self.calls), 1)
        self.assertEqual(source, {path.name: (path.read_bytes(), path.stat().st_mode & 0o777) for path in self.output.iterdir()})
        fork = Path(restored.result['runtime_recovery_source'])
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in fork.iterdir()))

    def test_incomplete_module_source_and_unproved_owner_drift_never_trigger_another_effect(self):
        # Mutations: infer success from receipt STARTED alone or accept live owners not proved by an intent.
        self.exception = 'before'
        with self.assertRaises(OSError): self.act('load', 'rfkill')
        with self.assertRaises(ValueError): self.recover()
        self.assertEqual(list((self.root / 'runtime').glob('n71-driver-recovered-*')), [])
        self.present.add('rfkill')
        _, (data, _, _), _ = self.accepted(self.recover)
        result = data['driver_module_journal'][-1]['completion']
        self.assertEqual((result['operation_exit'], result['shell_exit'], result['applied']), (None, None, True))
        self.accepted(self.subject.reconcile, self.session, self.journal, self.text())
        self.present.add('brcmutil')
        with self.assertRaises(ValueError): self.subject.resume(self.session, self.text())
        self.assertEqual(len(self.calls), 1)

    def test_pending_normal_wcc_unload_recovers_the_same_published_lifetime(self):
        # Mutation: reconcile a lost unload as a fresh load or lose the proved publication between module intents.
        for name in MODULES.NAMES: self.accepted(self.act, 'load', name)
        self.publish(); self.exception = 'after'
        with self.assertRaises(OSError): self.act('unload', 'brcmfmac_wcc')
        _, (data, _, proofs), _ = self.accepted(self.recover)
        result = data['driver_module_journal'][-1]['completion']
        self.assertEqual((result['mode'], result['shell_exit'], result['operation_exit'], result['applied']), ('observed', None, 0, True))
        self.assertEqual(result['driver_after']['published'], 1)
        self.assertEqual(self.present, set(MODULES.NAMES[:-1])); self.assertEqual(len(self.calls), 6)
        self.assertIn('wlan-module-0005-unload-brcmfmac_wcc', proofs)

    def test_lost_transport_recovers_receipt_without_repeating_load(self):
        # Mutations: replay pending intent or invent SSH success while observing a complete operation receipt.
        self.exception = 'after'
        with self.assertRaises(OSError): self.act('load', 'rfkill')
        with self.assertRaises(ValueError): self.act('load', 'rfkill')
        result = self.accepted(self.subject.reconcile, self.session, self.journal, self.text())
        self.assertEqual((result['mode'], result['shell_exit'], result['operation_exit'], result['applied']), ('observed', None, 0, True))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.present, {'rfkill'})

    def test_incomplete_receipt_requires_exact_observed_transition(self):
        # Mutations: turn an incomplete receipt into success without a transition or infer a fake operation exit.
        self.exception = 'before'
        with self.assertRaises(OSError): self.act('load', 'rfkill')
        with self.assertRaises(ValueError): self.subject.reconcile(self.session, self.journal, self.text())
        self.present.add('rfkill')
        result = self.accepted(self.subject.reconcile, self.session, self.journal, self.text())
        self.assertEqual((result['operation_exit'], result['shell_exit'], result['applied']), (None, None, True))
        self.assertEqual(len(self.calls), 1)

    def test_failed_operation_is_proved_and_retry_keeps_the_owned_prefix(self):
        # Mutation: equate nonzero exit with applied ownership or discard a completed failure before retry.
        self.exit_code = 1
        result = self.accepted(self.act, 'load', 'rfkill')
        self.assertEqual((result['applied'], result['operation_exit'], result['shell_exit']), (False, 1, 1))
        self.assertEqual(self.present, set())
        self.exit_code = 0; result = self.accepted(self.act, 'load', 'rfkill')
        self.assertTrue(result['applied']); self.assertEqual(self.present, {'rfkill'})

    def test_transport_disagreement_boot_and_unrelated_owner_changes_stay_pending(self):
        # Mutations: skip transport agreement, boot binding or one-target ownership validation.
        self.ssh_exit = 255
        with self.assertRaises(ValueError): self.act('load', 'rfkill')
        text = self.text()
        entry = self.session.driver_module_journal[-1]
        marked = STAGE.SSH_EXIT + 'tag=wlan-module-0000-load-rfkill exit=255\n' + text
        with self.assertRaises(ValueError):
            self.subject.completion(self.session, entry, {'text': marked, 'index': 0, 'mode': 'direct', 'shell_exit': 255})
        for current in (text.replace(BOOT, '87654321-1234-1234-1234-123456789abc'),
                        text.replace('name=brcmutil present=0 state=- refs=0', 'name=brcmutil present=1 state=live refs=0')):
            with self.subTest(current=current[:70]), self.assertRaises(ValueError): self.subject.reconcile(self.session, self.journal, current)
        self.assertIsNone(self.session.driver_module_journal[-1]['completion'])
        self.assertEqual(len(self.calls), 1)

    def test_proved_native_lifetime_and_healthy_prepublication_guard_precede_intent(self):
        # Mutations: omit native proof/cause/publication guard and load without proved preparation.
        for field, value in [('published', 1), ('error', -5), ('operation_error', -5)]:
            self.current_driver = PREPARED | {field: value}
            with self.subTest(field=field), self.assertRaises(ValueError): self.act('load', 'rfkill')
            self.assertEqual(self.calls, [])
            self.assertEqual(json.loads(self.journal.path.read_text())['driver_module_journal'], [])
        self.current_driver = PREPARED | dict(published=1)
        history = self.kernel_history + native('publish', self.current_driver, {'stamp': 3})
        proof = native_snapshot(self.current_driver, history, {'exit_value': 0, 'action': 'publish'})
        entry = dict(action='publish', before=dict(PREPARED), history=self.kernel_history.splitlines(), completion=None)
        entry['completion'] = DRIVER.completion(self.session, entry, {'text': proof, 'boot': BOOT, 'mode': 'direct', 'shell_exit': 0})
        self.session.driver_runtime_journal.append(entry); self.journal.proof('driver-runtime-0001-publish', proof)
        self.kernel_history = history
        with self.assertRaises(ValueError): self.act('load', 'rfkill')
        self.assertEqual(self.calls, [])
        self.current_driver = dict(PREPARED)
        self.session.driver_runtime_journal.pop(); self.journal.proofs.clear()
        with self.assertRaises(ValueError): self.act('load', 'rfkill')
        self.assertEqual(self.calls, [])

    def test_source_loader_recovers_registered_completion_and_rejects_scope_or_summary_tampering(self):
        # Mutations: bypass source hooks/hash-derived outcome or allow an intent from another boot/directory.
        self.accepted(self.act, 'load', 'rfkill')
        name = 'held-checkpoint-' + 'b' * 12 + '-private.log'
        checkpoint = self.output / name; checkpoint.write_text(self.text()); checkpoint.chmod(0o600)
        self.journal.checkpoint = {'name': name, 'sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest()}; self.journal.save()
        original = self.journal.path.read_text(); data = json.loads(original)
        data['driver_module_journal'][-1]['completion'] = None; self.journal.path.write_text(json.dumps(data))
        restored = self.make_session(self.output)
        _, _, proofs = self.accepted(HELD.load_source, restored, self.root, self.output, {'modules': {}})
        self.assertTrue(restored.driver_module_journal[-1]['completion']['applied'])
        self.assertIn('wlan-module-0000-load-rfkill', proofs)
        mixed = copy.deepcopy(self.subject.fields(self.session))
        other = '87654321-1234-1234-1234-123456789abc'
        mixed['driver_module_journal'][0]['before']['boot'] = other
        mixed['driver_module_journal'][0]['completion']['after']['boot'] = other
        with self.assertRaises(ValueError): self.subject.ledger(self.session, mixed)
        for field in ('summary', 'boot', 'directory'):
            data = json.loads(original)
            entry = data['driver_module_journal'][-1]
            if field == 'summary': entry['completion']['operation_exit'] = 1
            else: entry['before'][field] = '87654321-1234-1234-1234-123456789abc' if field == 'boot' else '/run/n71-link-' + 'b' * 24
            self.journal.path.write_text(json.dumps(data))
            with self.subTest(field=field), self.assertRaises(ValueError):
                HELD.load_source(self.make_session(self.output), self.root, self.output, {'modules': {}})

    def test_unowned_stack_legacy_selection_and_pending_schema_refuse(self):
        # Mutations: begin with unload, permit legacy effects or append another intent after an unproved one.
        self.accepted(self.act, 'load', 'rfkill')
        data = copy.deepcopy(self.subject.fields(self.session))
        entry = data['driver_module_journal'][0]; entry['action'] = 'unload'
        entry['before'] = copy.deepcopy(entry['completion']['after']); entry['completion'] = None
        with self.assertRaises(ValueError): self.subject.ledger(self.session, data)
        data = copy.deepcopy(self.subject.fields(self.session)); data['driver_module_journal'][0]['completion'] = None
        data['driver_module_journal'].append(copy.deepcopy(data['driver_module_journal'][0]))
        with self.assertRaises(ValueError): self.subject.ledger(self.session, data)
        legacy = SimpleNamespace(driver_runtime=False)
        self.assertEqual(self.subject.fields(legacy), {'driver_module_manifest': None, 'driver_module_journal': []})
        self.assertEqual(self.subject.getter(legacy), '')
        legacy.driver_modules = self.session.driver_modules
        with self.assertRaises(ValueError): self.subject.fields(legacy)


class ModuleJournalMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(ModuleJournalTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        source = SOURCE.read_text()
        mutations = [
            ('intent-save', 'ledger(session, fields(session)); journal.save()', 'ledger(session, fields(session))', 'test_ordered_load_and_reverse_unload_persist_only_the_proved_owners'),
            ('proof-save', 'journal.proof(name, text); entry[', 'entry[', 'test_ordered_load_and_reverse_unload_persist_only_the_proved_owners'),
            ('completion-save', "journal.proof(name, text); entry['completion'] = proved; journal.save()", 'journal.proof(name, text); journal.save()', 'test_ordered_load_and_reverse_unload_persist_only_the_proved_owners'),
            ('unrelated-owner', "after['states'][name]['present'] == expected", 'True', 'test_transport_disagreement_boot_and_unrelated_owner_changes_stay_pending'),
            ('transport', "completion['shell_exit'] == operation_exit", 'True', 'test_transport_disagreement_boot_and_unrelated_owner_changes_stay_pending'),
            ('native-proof', 'native_name in journal.proofs', 'True', 'test_proved_native_lifetime_and_healthy_prepublication_guard_precede_intent'),
            ('native-publication', "native_entries[-1]['action'] == 'prepare' and not state['published'] and not state['error']\n                and not state['operation_error'] and all(state[name] == 1 for name in driver.result.OWNERS)", 'True', 'test_proved_native_lifetime_and_healthy_prepublication_guard_precede_intent'),
            ('source-scope', "entry['before']['boot'] == scope.get('boot_id')", 'True', 'test_source_loader_recovers_registered_completion_and_rejects_scope_or_summary_tampering'),
            ('empty-origin', "previous is not None or (entry['action'] == 'load' and entry['name'] == modules.NAMES[0])", 'True', 'test_unowned_stack_legacy_selection_and_pending_schema_refuse'),
            ('observed-transport', "else completion['shell_exit'] is None", "else completion['shell_exit'] == 0", 'test_lost_transport_recovers_receipt_without_repeating_load'),
            ('publication-result', "driver.result.action('\\n'.join(lines[len(entry['history']):]), 'publish')\n                == entry['completion']['native']", 'True', 'test_ordered_load_and_reverse_unload_persist_only_the_proved_owners'),
            ('publication-counter', "driver.result.resume(session, driver.state_text(entry['before']), driver.state_text(before))", 'pass', 'test_ordered_load_and_reverse_unload_persist_only_the_proved_owners'),
            ('live-owner', "value['present'] == (before['states'][name]['present'] if before else 0)", 'True', 'test_incomplete_module_source_and_unproved_owner_drift_never_trigger_another_effect'),
        ]
        for name, old, new, method in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(old), 1, name)
                subject = ModuleType('wcc_journal_mutant')
                exec(compile(ast.parse(source.replace(old, new, 1)), str(SOURCE), 'exec'), subject.__dict__)
                case = type('MutatedModuleJournalTests', (ModuleJournalTests,), {'subject': subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name)
                self.assertGreater(len(result.failures), 0, name)
                print('N71_WCC_JOURNAL_MUTATION_KILLED', name, 'AssertionError')
        source = (ROOT / 'scripts/host/n71_driver_runtime_recovery.py').read_text()
        mutations = [
            ('module-recovery', "module_pending = bool(module_entries and module_entries[-1]['completion'] is None)\n    if module_pending:", 'module_pending = False\n    if module_pending:'),
            ('pending-checkpoint', "all(entry['completion'] is not None for entry in entries + module_entries)", "all(entry['completion'] is not None for entry in entries)"),
            ('fresh-proof', 'proof.encode() if name in observed', 'proof.encode() if False'),
        ]
        for name, old, new in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(old), 1, name)
                subject = ModuleType('wcc_recovery_mutant')
                exec(compile(ast.parse(source.replace(old, new, 1)), str(RECOVERY.__file__), 'exec'), subject.__dict__)
                case = type('MutatedModuleRecoveryTests', (ModuleJournalTests,), {'recovery': subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(
                    case('test_pending_module_source_recovers_read_only_and_preserves_orphan_and_old_checkpoint'))
                self.assertEqual(result.errors, [], name)
                self.assertGreater(len(result.failures), 0, name)
                print('N71_WCC_JOURNAL_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
