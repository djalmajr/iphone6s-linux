"""Runtime continuation requires registered effects and preserves software ownership."""
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
import test_n71_driver_module_stage as module_fixture
import test_n71_driver_runtime_stage as native_fixture
import test_n71_driver_runtime_result as runtime_fixture
import test_n71_iommu_result as iommu_fixture
import test_n71_resource_result as resource_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_lifetime as LIFETIME
import n71_driver_runtime_stage as DRIVER
import n71_driver_module_stage as MODULES
import n71_driver_runtime_recovery as RECOVERY
import n71_held_session as HELD
import n71_resource_stage as RESOURCE


class RuntimeLifetimeTests(unittest.TestCase):
    subject = LIFETIME
    recovery = RECOVERY

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); (self.root / 'runtime').mkdir(mode=0o700)
        self.phone = module_fixture.ModuleJournalTests('test_ordered_load_and_reverse_unload_persist_only_the_proved_owners')
        phone = self.phone; phone.root = self.root; phone.output = self.root / 'runtime' / 'source'; phone.output.mkdir(mode=0o700)
        phone.session = phone.make_session(phone.output); self.session = phone.session
        self.session.resource_capable = self.session.resource_attempted = self.session.iommu_parent = True
        self.session.reg_attempted = self.session.activation_attempted = self.session.pcie_attempted = True
        self.session.modules = [({'module': name, 'sha256': char * 64}, b'fixture') for name, char in zip(HELD.MODULES, ('b', 'c'))]
        self.session.history = HELD.Baseline(native_fixture.BASE.splitlines())
        phone.present = set(); phone.receipts = {}; phone.calls = []; phone.refs = {}; phone.exception = None
        phone.exit_code = 0; phone.ssh_exit = None; phone.current_driver = dict(native_fixture.PREPARED); phone.complete_receipt = True
        phone.session.capture = phone.capture
        phone.journal = HELD.Journal(self.session, {'modules': {}}); phone.journal.baseline = native_fixture.BASE.splitlines()
        phone.kernel_history = native_fixture.BASE + iommu_fixture.held_fixture.timestamp(iommu_fixture.ACQUIRED + resource_fixture.RESULT, 10)
        proof = ('N71_PCIE_RESOURCE_ACTION exit=0\n' + resource_fixture.GETTER + 'N71_PCIE_HELD held=1\n'
                 + iommu_fixture.held_fixture.ACTIVE + phone.kernel_history.removeprefix(native_fixture.BASE))
        self.session.resource_assignment = RESOURCE.n71_resource_result.outcome(proof)
        self.session.result['resource_assignment'] = self.session.resource_assignment
        phone.journal.proof('resource-assignment', proof)
        before = list(phone.kernel_history.splitlines())
        phone.kernel_history += native_fixture.native('prepare', native_fixture.PREPARED, {'stamp': 20})
        proof = native_fixture.snapshot(native_fixture.PREPARED, phone.kernel_history, {'exit_value': 0})
        entry = dict(action='prepare', before=dict(native_fixture.INITIAL), history=before, completion=None)
        entry['completion'] = DRIVER.completion(self.session, entry, {'text': proof, 'boot': native_fixture.BOOT, 'mode': 'direct', 'shell_exit': 0})
        self.session.driver_runtime_journal = [entry]; phone.journal.proof('driver-runtime-0000-prepare', proof)
        for name in MODULES.modules.NAMES: phone.act('load', name)
        phone.publish()
        self.primary = 0; self.vector = {'child': 0, 'slots': 0, 'mappings': 0}
        self.session.result['iommu_association'] = iommu_fixture.RESULT.acquisition(self.text())
        phone.journal.save()
        patched = patch.dict(sys.modules, {'n71_driver_runtime_lifetime': self.subject}); patched.start(); self.addCleanup(patched.stop)

    def context(self, checkpoint=None):
        return {'baseline': self.phone.journal.baseline, 'checkpoint': checkpoint,
                'proofs': {name: HELD.n71_session_history.read_private(self.phone.output, name + '-proof-private.log')
                           for name in self.phone.journal.proofs}}

    def text(self):
        text = self.phone.full_text()
        text = text.replace(iommu_fixture.held_fixture.ACTIVE,
            iommu_fixture.held_fixture.ACTIVE.replace('primary_error=0', 'primary_error=' + str(self.primary)))
        msi = iommu_fixture.getters().replace('mappings=0 child=0',
            'mappings=' + str(self.vector['mappings']) + ' child=' + str(self.vector['child']))
        text += msi + runtime_fixture.allocation_row(self.vector | dict(error=self.primary or self.vector.get('error', 0)))
        text += resource_fixture.GETTER.replace('assigned=1', 'assigned=' + str(int(self.primary == 0))).replace('error=0', 'error=' + str(self.primary))
        for record, _ in self.session.modules:
            text += record['sha256'] + '  ' + self.session.module_directory + '/' + record['module'] + '\n'
        return text

    def accepted(self, function, *args):
        try: return function(*args)
        except ValueError as error: self.fail('Proved runtime lifetime refused: ' + str(error))

    def retained(self, text=None, context=None):
        return RESOURCE.retained_runtime(self.session, text or self.text(), context or self.context())

    def fault(self):
        self.phone.current_driver.update(error=-5, operation_error=-5)
        self.phone.kernel_history += '[ 500.000000] device: N71_PCIE_SCAN_WRITE_REFUSED bus=1 devfn=00 where=004 size=2 value=00000006 error=-5\n'

    def release(self, failed=False):
        for name in reversed(MODULES.modules.NAMES): self.phone.act('unload', name)
        before = dict(self.phone.current_driver); history = self.phone.kernel_history.splitlines()
        after = dict(before, root_override=0) if failed else native_fixture.RELEASED | dict(error=before['error'], operation_error=before['operation_error'])
        self.phone.kernel_history += native_fixture.native('release', after, {'stamp': 700, 'error': -5 if failed else 0})
        proof = native_fixture.snapshot(after, self.phone.kernel_history, {'exit_value': int(failed), 'action': 'release'})
        entry = dict(action='release', before=before, history=history, completion=None)
        entry['completion'] = DRIVER.completion(self.session, entry, {'text': proof, 'boot': native_fixture.BOOT, 'mode': 'direct', 'shell_exit': int(failed)})
        self.session.driver_runtime_journal.append(entry); self.phone.current_driver = after
        self.phone.journal.proof('driver-runtime-0002-release', proof)

    def test_registered_publication_vector_activity_and_retained_domain_are_passive(self):
        # Mutations: trust a publication flag, borrow the manual lease or elevate software state to IRQ/DMA/radio proof.
        before = copy.deepcopy({key: value for key, value in vars(self.session).items() if key not in ('history', 'capture')})
        prior_history = self.session.history; calls = list(self.phone.calls)
        for vector in ({'child': 0, 'slots': 0, 'mappings': 0}, {'child': 1, 'slots': 1, 'mappings': 1},
                       {'child': 1, 'slots': 0, 'mappings': 0}):
            self.vector = vector; result = self.accepted(self.retained)
            self.assertTrue(result['software_ownership_retained'])
            for name in ('irq_delivery_verified', 'dma_translation_verified', 'wifi_verified', 'battery_or_charging_verified'):
                self.assertIs(result[name], False)
        self.assertEqual({key: value for key, value in vars(self.session).items() if key not in ('history', 'capture')}, before)
        self.assertIs(self.session.history, prior_history); self.assertEqual(self.phone.calls, calls)

    def test_async_refusal_and_latched_first_cause_keep_resources_in_same_boot(self):
        # Mutations: discard a callback refusal or demand the original assignment-only caller error.
        self.fault(); calls = list(self.phone.calls)
        self.assertEqual(self.accepted(self.retained)['primary_error'], 0)
        self.primary = -5
        self.assertEqual(self.accepted(self.retained)['primary_error'], -5)
        with self.assertRaises(ValueError): RESOURCE.retained(self.session, self.session.history.fresh(self.text()))
        self.assertEqual(self.phone.calls, calls)

    def test_boot_hash_proof_prefix_scope_manual_lease_and_unproved_action_refuse(self):
        # Mutations: ignore boot/proof/intent prefixes, accept another endpoint, manual lease or unknown kernel action.
        text = self.text(); context = self.context(); lost = copy.deepcopy(context)
        lost['proofs'].pop('driver-runtime-0001-publish')
        with self.assertRaises(ValueError): self.retained(text, lost)
        invalid = [text.replace(native_fixture.BOOT, '87654321-1234-1234-1234-123456789abc'),
                   text.replace(self.session.driver_modules[0]['sha256'], '0' * 64),
                   text.replace(native_fixture.BASE, '[ 1.000000] N71_OTHER_BASE private\n'),
                   text.replace('owner=0 phase=0 vector=0', 'owner=1 phase=0 vector=0'),
                   text + '[ 600.000000] N71_OTHER_ACTION unknown\n',
                   text.replace('claimed=1 active=0', 'claimed=0 active=0'),
                   text.replace('observed=2 map_checked=1', 'observed=0 map_checked=0')]
        for proof in invalid:
            with self.subTest(proof=proof[-120:]), self.assertRaises(ValueError): self.retained(proof, context)
        self.fault(); text = self.text()
        for old, new in [('devfn=00 where=004', 'devfn=01 where=004'), ('where=004 size=2', 'where=005 size=2'),
                         ('value=00000006 error=-5', 'value=00000006 error=-13'),
                         ('device: N71_PCIE_SCAN_WRITE_REFUSED', 'N71_OTHER_ACTION unknown; N71_PCIE_SCAN_WRITE_REFUSED')]:
            with self.subTest(new=new), self.assertRaises(ValueError): self.retained(text.replace(old, new), context)

    def test_release_success_or_partial_refusal_requires_empty_modules_and_registered_result(self):
        # Mutations: infer a release from changed owners, omit its registered result or demand old owners after a proved release.
        self.vector = {'child': 1, 'slots': 0, 'mappings': 0}; self.release()
        result = self.accepted(self.retained); self.assertTrue(result['software_ownership_retained'])
        self.assertEqual(self.phone.present, set()); self.assertEqual(self.phone.current_driver['pending'], 0)
        lost = self.context(); lost['proofs'].pop('driver-runtime-0002-release')
        with self.assertRaises(ValueError): self.retained(self.text(), lost)
        with self.assertRaises(ValueError): MODULES.resume(self.session, self.text())
        self.phone.present.add('rfkill')
        with self.assertRaises(ValueError): self.retained()

    def test_partial_release_keeps_its_remaining_native_owners(self):
        # Mutation: treat a failed but proved release as success or discard the remaining override/root ownership.
        self.release(failed=True); self.primary = -5
        self.phone.current_driver.update(error=-5)
        # The refusal is latched by the caller before its final getter/proof.
        entry = self.session.driver_runtime_journal[-1]
        proof = HELD.n71_session_history.read_private(self.phone.output, 'driver-runtime-0002-release-proof-private.log')
        proof = proof.replace(DRIVER.state_text(entry['completion']['state']), DRIVER.state_text(self.phone.current_driver))
        path = self.phone.output / 'driver-runtime-0002-release-proof-private.log'; path.write_text(proof)
        entry['completion'] = DRIVER.completion(self.session, entry, {'text': proof, 'boot': native_fixture.BOOT, 'mode': 'direct', 'shell_exit': 1})
        self.phone.journal.proofs['driver-runtime-0002-release'] = hashlib.sha256(path.read_bytes()).hexdigest(); self.phone.journal.save()
        self.assertEqual(self.accepted(self.retained)['primary_error'], -5)
        self.assertEqual(entry['completion']['native']['error'], -5); self.assertEqual(entry['completion']['state']['pending'], 1)

    def test_release_retains_providers_without_admitting_a_manual_lease(self):
        # Mutations: admit a manual lease or changed IOMMU providers after the native owners have been released.
        self.release(); text = self.text()
        self.accepted(self.retained, text)
        for invalid in (text.replace('owner=0 phase=0 vector=0', 'owner=1 phase=0 vector=0'),
                        text.replace('observed=2 map_checked=1', 'observed=0 map_checked=0')):
            with self.subTest(invalid=invalid[-120:]), self.assertRaises(ValueError): self.retained(invalid)

    def test_pending_source_unload_is_observed_without_replay_and_preserves_source(self):
        # Mutations: skip runtime history/recovery, replay rmmod, alter source or invent SSH success.
        checkpoint = self.phone.output / ('held-checkpoint-' + 'b' * 12 + '-private.log')
        checkpoint.write_text(self.text()); checkpoint.chmod(0o600)
        self.phone.journal.checkpoint = {'name': checkpoint.name, 'sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
        self.phone.exception = 'after'
        with self.assertRaises(OSError): self.phone.act('unload', 'brcmfmac_wcc')
        source = {path.name: path.read_bytes() for path in self.phone.output.iterdir()}
        output = self.root / 'runtime' / 'restored'; output.mkdir(mode=0o700)
        restored = self.phone.make_session(output)
        restored.resource_capable = restored.iommu_parent = True; restored.modules = self.session.modules
        def capture(name, command):
            self.assertNotIn('rmmod ', command); self.assertNotIn('insmod ', command)
            self.phone.kernel_history += '[ 800.000000] N71_REG_ON_READ error=0 value_valid=1 value=81\n'
            text = self.text(); path = output / (name + '-private.log'); path.write_text(text + '\nSTDERR\n'); path.chmod(0o600)
            return SimpleNamespace(returncode=0, stdout='filtered output')
        restored.capture = capture
        data, _, _ = self.accepted(self.recovery.load, restored, {'root': self.root, 'source': self.phone.output,
            'identity': {'modules': {}}, 'allowed_proofs': HELD.PROOFS, 'loader': HELD.load_source, 'snapshot': HELD.snapshot})
        completion = data['driver_module_journal'][-1]['completion']
        self.assertEqual((completion['mode'], completion['shell_exit'], completion['operation_exit']), ('observed', None, 0))
        self.assertEqual(len(self.phone.calls), 6)
        self.assertEqual(source, {path.name: path.read_bytes() for path in self.phone.output.iterdir()})

    def recover(self):
        source = {path.name: path.read_bytes() for path in self.phone.output.iterdir()}
        output = self.root / 'runtime' / 'restored'; output.mkdir(mode=0o700)
        restored = self.phone.make_session(output)
        restored.resource_capable = restored.iommu_parent = True; restored.modules = self.session.modules
        reads = []
        def capture(name, command):
            self.assertNotIn('rmmod ', command); self.assertNotIn('insmod ', command)
            self.assertNotIn(' > ' + DRIVER.result.PCIE + 'action', command)
            reads.append(name)
            text = self.text(); path = output / (name + '-private.log'); path.write_text(text + '\nSTDERR\n'); path.chmod(0o600)
            return SimpleNamespace(returncode=0, stdout='filtered output')
        restored.capture = capture
        data, text, _ = self.accepted(self.recovery.load, restored, {'root': self.root, 'source': self.phone.output,
            'identity': {'modules': {}}, 'allowed_proofs': HELD.PROOFS, 'loader': HELD.load_source, 'snapshot': HELD.snapshot})
        self.assertEqual(source, {path.name: path.read_bytes() for path in self.phone.output.iterdir()})
        return data, text, reads

    def test_pending_native_publication_recovers_from_live_without_promoting_orphan(self):
        # Mutations: skip pending native completion or promote an orphan's transport exit instead of live observation.
        self.session.driver_runtime_journal[-1]['completion'] = None
        self.phone.journal.proofs.pop('driver-runtime-0001-publish'); self.phone.journal.save()
        self.fault()
        data, text, reads = self.recover()
        completion = data['driver_runtime_journal'][-1]['completion']
        self.assertEqual((completion['mode'], completion['shell_exit'], completion['native']['published']), ('observed', None, 1))
        self.assertEqual(completion['state']['operation_error'], -5)
        self.assertIn('N71_PCIE_SCAN_WRITE_REFUSED', text); self.assertEqual(reads, ['held-runtime-recovery-live'])

    def test_pending_native_release_recovers_without_repeating_unloads_or_setter(self):
        # Mutations: demand old native owners after release, skip its completion or invent transport success.
        self.release(); self.session.driver_runtime_journal[-1]['completion'] = None
        self.phone.journal.proofs.pop('driver-runtime-0002-release'); self.phone.journal.save()
        data, _, reads = self.recover()
        completion = data['driver_runtime_journal'][-1]['completion']
        self.assertEqual((completion['mode'], completion['shell_exit'], completion['state']['pending']), ('observed', None, 0))
        self.assertEqual(len(self.phone.calls), 10); self.assertEqual(reads, ['held-runtime-recovery-live'])

    def test_completed_checkpoint_revalidates_async_history_before_legacy_loader(self):
        # Mutation: take the completed-source shortcut without verifying runtime callback history.
        self.fault()
        checkpoint = self.phone.output / ('held-checkpoint-' + 'b' * 12 + '-private.log')
        checkpoint.write_text(self.text()); checkpoint.chmod(0o600)
        self.phone.journal.checkpoint = {'name': checkpoint.name, 'sha256': hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
        self.phone.journal.save()
        _, _, reads = self.recover(); self.assertEqual(reads, [])
        invalid = checkpoint.read_text().replace('devfn=00 where=004', 'devfn=01 where=004')
        checkpoint.write_text(invalid)
        self.phone.journal.checkpoint['sha256'] = hashlib.sha256(checkpoint.read_bytes()).hexdigest(); self.phone.journal.save()
        restored = self.phone.make_session(self.phone.output)
        restored.resource_capable = restored.iommu_parent = True; restored.modules = self.session.modules
        with self.assertRaises(ValueError): self.recovery.load(restored, {'root': self.root, 'source': self.phone.output,
            'identity': {'modules': {}}, 'allowed_proofs': HELD.PROOFS, 'loader': HELD.load_source, 'snapshot': HELD.snapshot})

    def cleanup(self):
        self.release()
        fixture = iommu_fixture.held_fixture
        self.phone.kernel_history += fixture.timestamp(fixture.REMOVED + iommu_fixture.DART_CLEAN + resource_fixture.RESTORE
            + fixture.CONFIG + resource_fixture.RELEASE + fixture.PME_RESTORED + fixture.TLS_RESTORED
            + fixture.RESET + fixture.POWER + fixture.FINISHED, 900)
        empty = dict.fromkeys(DRIVER.result.FIELDS, 0) | dict(requested=1)
        proof = ('N71_BOOT_ID ' + native_fixture.BOOT + '\n' + iommu_fixture.getters(False)
            + runtime_fixture.allocation_row(dict(ready=0, held=0)) + DRIVER.state_text(empty)
            + 'N71_PCIE_HELD held=0\n' + fixture.CLEAN + resource_fixture.EMPTY + self.phone.kernel_history)
        self.phone.journal.proof('pcie-cleanup', proof)
        return proof

    def removed_text(self, present=False):
        original = self.phone.text()
        wire = original[original.index(MODULES.modules.IDENTITY):original.index('N71_WLAN_REGISTERED=')]
        wire += 'N71_WLAN_REGISTERED=0\n'
        text = ('N71_BOOT_ID ' + native_fixture.BOOT + '\nN71_HELD_PCIE_PRESENT=' + str(int(present))
            + '\nN71_HELD_PCI_EMPTY=1\n' + wire + self.phone.kernel_history)
        if present: text += DRIVER.state_text(dict.fromkeys(DRIVER.result.FIELDS, 0) | dict(requested=1))
        return text

    def test_removed_host_uses_registered_cleanup_unload_and_fresh_empty_module_getter(self):
        # Mutations: fabricate a missing driver getter, omit cleanup/unload or accept an unrecorded module disappearance.
        self.cleanup()
        self.assertTrue(self.accepted(self.subject.removed, self.session, self.removed_text(True), self.context())['resource_cleanup_verified'])
        self.phone.journal.proof('pcie-unload', 'N71_PCIE_UNLOADED\n' + self.phone.kernel_history)
        self.accepted(self.subject.removed, self.session, self.removed_text(), self.context())
        invalid = self.removed_text().replace('N71_BOOT_ID ' + native_fixture.BOOT, 'N71_BOOT_ID 87654321-1234-1234-1234-123456789abc')
        with self.assertRaises(ValueError): self.subject.removed(self.session, invalid, self.context())
        try: MODULES.resume(self.session, self.removed_text(), context=self.context())
        except ValueError as error: self.fail('Proved removed lifetime must resume: ' + str(error))
        for name in ('pcie-cleanup', 'pcie-unload'):
            context = self.context(); context['proofs'].pop(name)
            with self.subTest(name=name), self.assertRaises(ValueError): self.subject.removed(self.session, self.removed_text(), context)
        self.phone.present.add('rfkill')
        with self.assertRaises(ValueError): self.subject.removed(self.session, self.removed_text(), self.context())

    def test_removed_history_and_module_disappearance_need_recorded_effects(self):
        # Mutations: skip pre-cleanup history validation or infer normal module unload from a fresh empty getter.
        self.cleanup(); context = self.context()
        saved = self.session.driver_module_journal
        self.session.driver_module_journal = saved[:5]
        for name in list(context['proofs']):
            if '-unload-' in name: context['proofs'].pop(name)
        with self.assertRaises(ValueError): self.subject.removed(self.session, self.removed_text(True), context)
        self.session.driver_module_journal = saved; context = self.context()
        name = 'driver-runtime-0002-release'
        prefix = HELD.n71_session_history.kernel_lines(context['proofs'][name])
        unknown = '[ 850.000000] N71_OTHER_ACTION unknown\n'
        old = self.phone.kernel_history
        self.phone.kernel_history = '\n'.join(prefix) + '\n' + unknown + old[len('\n'.join(prefix)) + 1:]
        context['proofs'][name] += unknown
        context['proofs']['pcie-cleanup'] = context['proofs']['pcie-cleanup'].replace(old, self.phone.kernel_history)
        with self.assertRaises(ValueError): self.subject.removed(self.session, self.removed_text(True), context)


class RuntimeLifetimeMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeLifetimeTests))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        path = ROOT / 'scripts/host/n71_driver_runtime_lifetime.py'; source = path.read_text()
        mutations = [
            ('proof-registration', "(name in proofs) == (saved is not None), 'Runtime native completion lacks its registered proof'", "saved is None, 'Runtime native completion lacks its registered proof'", 'test_registered_publication_vector_activity_and_retained_domain_are_passive'),
            ('boot', "re.findall(r'^N71_BOOT_ID (' + driver.BOOT + ')$', text, re.M) == [session.result.get('boot_id')]", 'True', 'test_removed_host_uses_registered_cleanup_unload_and_fresh_empty_module_getter'),
            ('baseline-equality', 'current[:len(baseline)] == baseline', 'current[:len(baseline)] != baseline', 'test_registered_publication_vector_activity_and_retained_domain_are_passive'),
            ('endpoint', "row.group(1, 2) in (('0', '08'), ('1', '00'))", 'True', 'test_boot_hash_proof_prefix_scope_manual_lease_and_unproved_action_refuse'),
            ('config-alignment', 'int(row[3], 16) % int(row[4]) == 0', 'True', 'test_boot_hash_proof_prefix_scope_manual_lease_and_unproved_action_refuse'),
            ('refusal-cause', "error in (state['operation_error'], observation.get('action_error', 0))", 'True', 'test_boot_hash_proof_prefix_scope_manual_lease_and_unproved_action_refuse'),
            ('unknown-action', "refusal(line, observation), 'Runtime history includes an unproved operation'", "True, 'Runtime history includes an unproved operation'", 'test_boot_hash_proof_prefix_scope_manual_lease_and_unproved_action_refuse'),
            ('embedded-action', "line.count('N71_') == 1", 'True', 'test_boot_hash_proof_prefix_scope_manual_lease_and_unproved_action_refuse'),
            ('valid-refusal', 'return True\n\n\ndef segment', 'return False\n\n\ndef segment', 'test_async_refusal_and_latched_first_cause_keep_resources_in_same_boot'),
            ('manual-lease', "all(vector[name] == 0 for name in ('owner', 'phase', 'vector', 'default_irq', 'software_enabled'))", 'True', 'test_release_retains_providers_without_admitting_a_manual_lease'),
            ('resource-owner', 'resources.live_status(text) == expected', 'True', 'test_boot_hash_proof_prefix_scope_manual_lease_and_unproved_action_refuse'),
            ('provider-owner', "providers['iommu'] == iommu.IOMMU_ACTIVE", 'True', 'test_release_retains_providers_without_admitting_a_manual_lease'),
            ('irq-proof', "'irq_delivery_verified': False", "'irq_delivery_verified': True", 'test_registered_publication_vector_activity_and_retained_domain_are_passive'),
            ('release-bridge', "driver.result.resume(session, text, driver.state_text(result['state']))", "require(False, 'Missing release bridge')", 'test_release_success_or_partial_refusal_requires_empty_modules_and_registered_result'),
            ('recorded-empty-stack', "not wlan or not any(state['present'] for state in wlan[-1]['completion']['after']['states'].values())", 'True', 'test_removed_history_and_module_disappearance_need_recorded_effects'),
            ('removed-timeline', "_, proved, _, _ = timeline(session, last, dict(value, checkpoint=None))", 'proved = history.kernel_lines(last)', 'test_removed_history_and_module_disappearance_need_recorded_effects'),
            ('registered-unload', "'pcie-unload' in proofs and proofs['pcie-unload'].splitlines().count('N71_PCIE_UNLOADED') == 1", 'True', 'test_removed_host_uses_registered_cleanup_unload_and_fresh_empty_module_getter'),
        ]
        for name, old, new, method in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(old), 1, name)
                subject = ModuleType('runtime_lifetime_mutant')
                exec(compile(ast.parse(source.replace(old, new, 1)), str(path), 'exec'), subject.__dict__)
                case = type('MutatedRuntimeLifetimeTests', (RuntimeLifetimeTests,), {'subject': subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name); self.assertGreater(len(result.failures), 0, name)
                print('N71_RUNTIME_LIFETIME_MUTATION_KILLED', name, 'AssertionError')
        path = ROOT / 'scripts/host/n71_driver_runtime_recovery.py'; source = path.read_text()
        mutations = [
            ('runtime-history-dispatch', "n71_driver_runtime_lifetime.verify_history(request['session'], text, {", "require(False, 'Missing runtime dispatch'); n71_driver_runtime_lifetime.verify_history(request['session'], text, {", 'test_pending_source_unload_is_observed_without_replay_and_preserves_source'),
            ('pending-native-transport', "'text': live, 'boot': session.result['boot_id'], 'mode': 'observed', 'shell_exit': None", "'text': live, 'boot': session.result['boot_id'], 'mode': 'observed', 'shell_exit': 0", 'test_pending_native_publication_recovers_from_live_without_promoting_orphan'),
            ('release-context', 'n71_driver_module_stage.resume(session, live, context=context)', 'n71_driver_module_stage.resume(session, live)', 'test_pending_native_release_recovers_without_repeating_unloads_or_setter'),
            ('completed-shortcut', "if n71_driver_module_stage.selected(session) is not None and 'pcie-cleanup' not in proofs:", 'if False:', 'test_completed_checkpoint_revalidates_async_history_before_legacy_loader'),
        ]
        for name, old, new, method in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(old), 1, name)
                subject = ModuleType('runtime_lifetime_recovery_mutant')
                exec(compile(ast.parse(source.replace(old, new, 1)), str(path), 'exec'), subject.__dict__)
                case = type('MutatedRuntimeRecoveryTests', (RuntimeLifetimeTests,), {'recovery': subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name); self.assertGreater(len(result.failures), 0, name)
                print('N71_RUNTIME_LIFETIME_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
