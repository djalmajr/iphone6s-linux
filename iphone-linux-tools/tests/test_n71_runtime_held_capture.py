"""Runtime teardown keeps complete same-boot proofs and observable module ownership."""
import ast
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
import unittest
import test_n71_driver_modules as shell_fixture
import test_n71_driver_runtime_lifetime as lifetime_fixture
import test_n71_driver_runtime_stage as native_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_held_session as HELD
import n71_driver_runtime_recovery as RECOVERY
import n71_session_history as HISTORY
SOURCE = ROOT / 'scripts/host/n71_held_session.py'


class RuntimeHeldShellTests(unittest.TestCase):
    subject = HELD

    def setUp(self):
        self.tree = shell_fixture.DriverModuleTests('test_getter_and_parser_preserve_order_identity_and_canonical_states')
        self.tree.setUp(); self.addCleanup(self.tree.doCleanups)
        root = self.tree.root
        shutil.rmtree(self.tree.control.parent)
        (root / 'sys/bus/pci/devices').mkdir(parents=True)
        (root / 'proc/cmdline').write_text('rdinit=/init pcie_aspm=off\n')
        tool = self.tree.tools / 'dmesg'; tool.write_text('#!/bin/sh\nprintf "%s\\n" "PCIe ASPM is disabled"\n'); tool.chmod(0o700)
        modules = []
        for name in HELD.MODULES:
            raw = name.encode(); (self.tree.target / name).write_bytes(raw)
            modules.append(({'module': name, 'sha256': hashlib.sha256(raw).hexdigest()}, raw))
        output = root / 'runtime'; output.mkdir(mode=0o700)
        self.session = SimpleNamespace(module_directory=shell_fixture.DIRECTORY, release=shell_fixture.MODULES.RELEASE,
            result={'boot_id': native_fixture.BOOT}, modules=modules, driver_runtime=True,
            driver_modules=self.tree.records, driver_runtime_journal=[], driver_module_journal=[],
            resource_capable=True, iommu_parent=True, output=output)
        self.session.capture = self.capture

    def capture(self, name, command):
        process = self.tree.run_shell(command)
        path = self.session.output / (name + '-private.log')
        stdout = process.stdout.replace(str(self.tree.target), self.session.module_directory)
        path.write_text(stdout + '\nSTDERR\n' + process.stderr); path.chmod(0o600)
        return SimpleNamespace(returncode=process.returncode, stdout='filtered collector output')

    def accepted(self, function, *args):
        try: return function(*args)
        except ValueError as error: self.fail('Proved held capture refused: ' + str(error))

    def test_snapshot_reads_real_module_files_without_the_diagnostic_host(self):
        # Mutation: put the M1 getter back inside the absent PCIe diagnostic branch.
        text, presence = self.accepted(self.subject.snapshot, self.session, 'removed-snapshot')
        current = self.accepted(shell_fixture.MODULES.live, text, {'manifest': self.session.driver_modules,
            'directory': self.session.module_directory, 'boot': native_fixture.BOOT})
        self.assertEqual(presence, (0, 0, 1)); self.assertEqual(current['registered'], 0)
        self.assertTrue(all(state['present'] == state['refs'] == 0 and state['holders'] == [] for state in current['states'].values()))
        self.assertNotIn('N71_PCIE_DRIVER ', text)
        self.assertEqual(text, HISTORY.read_private(self.session.output, 'removed-snapshot-private.log'))

    def test_effect_guard_checks_the_actual_boot_before_writing(self):
        # Mutation: omit the effect's boot equality test and allow a write in another boot.
        target = self.tree.root / 'effect'
        command = 'set -e; ' + self.subject.effect_boot(self.session) + 'printf done > ' + str(target)
        process = self.tree.run_shell(command)
        self.assertEqual(process.returncode, 0, process.stderr); self.assertEqual(target.read_text(), 'done')
        self.assertEqual(process.stdout.splitlines(), ['N71_BOOT_ID ' + native_fixture.BOOT])
        target.unlink()
        (self.tree.root / 'proc/sys/kernel/random/boot_id').write_text('87654321-1234-1234-1234-123456789abc\n')
        process = self.tree.run_shell(command)
        self.assertNotEqual(process.returncode, 0); self.assertFalse(target.exists())

    def test_raw_capture_rejects_other_duplicate_missing_boot_or_failed_transport(self):
        # Mutations: trust filtered stdout, ignore boot/uniqueness/returncode or change the legacy collector.
        process = SimpleNamespace(returncode=0, stdout='filtered')
        raw = 'N71_BOOT_ID ' + native_fixture.BOOT + '\n[ 1.000000] N71_COMPLETE proof\n\nSTDERR\nprivate detail\n'
        path = self.session.output / 'effect-private.log'; path.write_text(raw); path.chmod(0o600)
        self.assertEqual(self.accepted(self.subject.proof_output, self.session, 'effect', process), raw)
        for invalid in (raw.replace(native_fixture.BOOT, '87654321-1234-1234-1234-123456789abc'), raw + raw, raw.split('\n', 1)[1]):
            path.write_text(invalid)
            with self.subTest(invalid=invalid[:70]), self.assertRaises(ValueError): self.subject.proof_output(self.session, 'effect', process)
        path.write_text(raw); process.returncode = 1
        with self.assertRaises(ValueError): self.subject.proof_output(self.session, 'effect', process)
        legacy = SimpleNamespace(driver_runtime=False)
        self.assertEqual(self.subject.effect_boot(legacy), '')
        self.assertEqual(self.subject.proof_output(legacy, 'absent', process), 'filtered')

    def test_capture_stage_permissions_symlinks_and_size_are_bounded(self):
        # Mutations: bypass private file protection, stage scope or the capture size budget.
        process = SimpleNamespace(returncode=0, stdout='filtered')
        path = self.session.output / 'effect-private.log'; path.write_text('N71_BOOT_ID ' + native_fixture.BOOT + '\n'); path.chmod(0o600)
        with self.assertRaises(ValueError): self.subject.proof_output(self.session, '../runtime/effect', process)
        path.chmod(0o644)
        with self.assertRaises(ValueError): self.subject.proof_output(self.session, 'effect', process)
        path.chmod(0o600); alias = self.session.output / 'alias-private.log'; alias.symlink_to(path)
        with self.assertRaises(ValueError): self.subject.proof_output(self.session, 'alias', process)
        header = path.read_text(); path.write_text(header + 'x' * (2 * 1024 * 1024 - len(header)))
        self.assertEqual(len(self.accepted(self.subject.proof_output, self.session, 'effect', process)), 2 * 1024 * 1024)
        with path.open('a') as stream: stream.write('x')
        with self.assertRaises(ValueError): self.subject.proof_output(self.session, 'effect', process)


class RuntimeHeldSourceTests(unittest.TestCase):
    subject = HELD

    def setUp(self):
        self.life = lifetime_fixture.RuntimeLifetimeTests('test_registered_publication_vector_activity_and_retained_domain_are_passive')
        self.life.setUp(); self.addCleanup(self.life.doCleanups)
        self.session = self.life.session; self.journal = self.life.phone.journal
        self.output = self.life.phone.output; self.pcie = self.reg = self.active = True
        self.calls = []; self.bad_stage = None
        self.cleanup_proof = self.life.cleanup()
        path = self.output / 'pcie-cleanup-proof-private.log'; path.rename(self.output / 'generated-cleanup-private.log')
        self.journal.proofs.pop('pcie-cleanup'); self.journal.save()
        self.full_history = self.life.phone.kernel_history
        proof = HISTORY.read_private(self.output, 'driver-runtime-0002-release-proof-private.log')
        self.life.phone.kernel_history = '\n'.join(HISTORY.kernel_lines(proof)) + '\n'
        self.session.capture = self.capture

    def accepted(self, function, *args):
        try: return function(*args)
        except ValueError as error: self.fail('Proved held source refused: ' + str(error))

    def capture(self, name, command):
        self.calls.append((name, command))
        raw = 'N71_BOOT_ID ' + native_fixture.BOOT + '\n'; code = 0
        if name == 'held-cleanup':
            self.life.phone.kernel_history = self.full_history; raw = self.cleanup_proof
        elif name == 'held-pci-empty': raw = 'N71_PCI_CLEANUP_EMPTY\n'
        elif name == 'held-pcie-unload':
            self.pcie = False; raw += 'N71_PCIE_UNLOADED\n' + self.life.phone.kernel_history
        elif name == 'held-restore':
            self.active = False
            self.life.phone.kernel_history += '[ 1000.000000] N71_REG_ON_READ error=0 value_valid=1 value=80\n'
            raw += 'bound=1 active=0 restore_pending=0 original=80\nN71_REG_ON_CONTROL_READBACK value=80\n' + self.life.phone.kernel_history
        elif name == 'held-reg-unload':
            self.reg = False
            self.life.phone.kernel_history += '[ 1100.000000] N71_REG_ON_REMOVE error=0 restore_pending=0\n'
            raw += 'N71_REG_UNLOADED\n' + self.life.phone.kernel_history
        else:
            self.assertNotIn('rmmod ', command); self.assertNotIn('insmod ', command)
            self.assertNotIn(' > ' + HELD.PCIE + 'action', command)
            raw = self.removed_text()
        if name == self.bad_stage: raw = raw.replace(native_fixture.BOOT, '87654321-1234-1234-1234-123456789abc')
        path = self.session.output / (name + '-private.log'); path.write_text(raw + '\nSTDERR\nprivate detail\n'); path.chmod(0o600)
        return SimpleNamespace(returncode=code, stdout='filtered collector output')

    def removed_text(self):
        text = self.life.removed_text(self.pcie)
        text += 'N71_PCIE_CMDLINE rdinit=/init pcie_aspm=off\nN71_HELD_REG_PRESENT=' + str(int(self.reg)) + '\n'
        if self.reg:
            text += 'bound=1 active=' + str(int(self.active)) + ' restore_pending=' + str(int(self.active)) + ' original=80\n'
            text += 'N71_REG_ON_CONTROL_READBACK value=' + ('81' if self.active else '80') + '\n'
        for record, _ in self.session.modules:
            text += record['sha256'] + '  ' + self.session.module_directory + '/' + record['module'] + '\n'
        return text

    def release(self):
        return self.subject.release(self.session, self.journal, (1, 1, 0), self.life.text())

    def checkpoint(self):
        text = self.removed_text(); path = self.output / ('held-checkpoint-' + 'b' * 12 + '-private.log')
        path.write_text(text); path.chmod(0o600)
        self.journal.checkpoint = {'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}; self.journal.save()

    def restored(self, output):
        session = self.life.phone.make_session(output)
        session.resource_capable = session.iommu_parent = True; session.modules = self.session.modules
        session.result = {'kernel_release':session.release}
        return session

    def test_release_records_complete_private_logs_before_discarding_owners(self):
        # Mutations: keep stdout as proof or omit boot/raw validation from cleanup/unload/restore.
        self.accepted(self.release)
        self.assertFalse(self.pcie or self.reg or self.active); self.assertTrue(self.session.result['cleanup_verified'])
        self.assertEqual(self.session.result['stop_error'], 0)
        stages = dict(zip(HELD.PROOFS, ('held-cleanup','held-pcie-unload','held-restore','held-reg-unload')))
        for name, stage in stages.items():
            proof = (self.output / (name + '-proof-private.log')).read_text()
            self.assertEqual(proof, (self.output / (stage + '-private.log')).read_text())
            self.assertIn('\nSTDERR\nprivate detail\n', proof)
            self.assertEqual(HISTORY.kernel_lines(proof)[:1], native_fixture.BASE.splitlines())

    def test_bad_cleanup_capture_retains_diagnostic_and_reg_owners(self):
        # Mutation: ignore the boot of the complete cleanup output before unloading the retained providers.
        self.bad_stage = 'held-cleanup'
        with self.assertRaises(ValueError): self.release()
        self.assertTrue(self.pcie and self.reg and self.active)
        self.assertEqual([name for name, _ in self.calls], ['held-cleanup'])
        self.assertNotIn('pcie-cleanup', self.journal.proofs)

    def test_already_clean_host_registers_the_complete_observation_without_replay(self):
        # Mutation: strip the baseline from the clean runtime observation and lose its native release history.
        self.life.phone.kernel_history = self.full_history
        self.accepted(self.subject.release, self.session, self.journal, (1, 1, 1), self.cleanup_proof)
        self.assertFalse(self.pcie or self.reg or self.active)
        self.assertNotIn('held-cleanup', [name for name, _ in self.calls])
        self.assertEqual((self.output / 'pcie-cleanup-proof-private.log').read_text(), self.cleanup_proof)

    def test_bad_unload_capture_preserves_reg_owners_without_registering_unload(self):
        # Mutation: ignore unload's capture boot after its effect and proceed with unproved REG_ON restoration.
        self.bad_stage = 'held-pcie-unload'
        with self.assertRaises(ValueError): self.release()
        self.assertFalse(self.pcie); self.assertTrue(self.reg and self.active)
        self.assertIn('pcie-cleanup', self.journal.proofs); self.assertNotIn('pcie-unload', self.journal.proofs)
        self.assertNotIn('held-restore', [name for name, _ in self.calls])

    def test_removed_source_loader_and_read_only_recovery_preserve_origin(self):
        # Mutations: retain delta-only proof rules, skip empty lifetime validation or replay an effect during recovery.
        self.accepted(self.release); self.checkpoint()
        source = {path.name:path.read_bytes() for path in self.output.iterdir()}
        restored = self.restored(self.output)
        data, text, proofs = self.accepted(self.subject.load_source, restored, self.life.root, self.output, {'modules':{}})
        self.assertEqual(source, {path.name:path.read_bytes() for path in self.output.iterdir()})
        self.assertEqual(set(proofs).intersection(HELD.PROOFS), set(HELD.PROOFS)); self.assertIn('N71_HELD_PCI_EMPTY=1\n', text)
        self.assertEqual(restored.result['boot_id'], native_fixture.BOOT)
        checkpoint = self.output / data['checkpoint']['name']; checkpoint.unlink()
        data['checkpoint'] = None; self.journal.path.write_text(json.dumps(data))
        source = {path.name:path.read_bytes() for path in self.output.iterdir()}
        target = self.life.root / 'runtime' / 'restored'; target.mkdir(mode=0o700)
        restored = self.restored(target)
        def capture(name, command):
            self.assertNotIn('rmmod ', command); self.assertNotIn('insmod ', command)
            self.assertNotIn(' > ' + HELD.PCIE + 'action', command)
            path = target / (name + '-private.log'); path.write_text(self.removed_text() + '\nSTDERR\n'); path.chmod(0o600)
            return SimpleNamespace(returncode=0, stdout='filtered')
        restored.capture = capture
        result = self.accepted(RECOVERY.load, restored, {'root':self.life.root,'source':self.output,'identity':{'modules':{}},
            'allowed_proofs':HELD.PROOFS,'loader':self.subject.load_source,'snapshot':self.subject.snapshot})
        self.assertIn('N71_HELD_PCIE_PRESENT=0\n', result[1])
        self.assertFalse(restored.result['driver_intent_reconciled'] or restored.result['driver_module_intent_reconciled'])
        self.assertEqual(source, {path.name:path.read_bytes() for path in self.output.iterdir()})

    def test_removed_source_rejects_wrong_boot_owner_or_history_and_missing_proofs(self):
        # Mutations: skip full held proof boot, removed lifetime validation or complete proof registration.
        self.accepted(self.release); self.checkpoint()
        original = self.journal.path.read_text(); data = json.loads(original)
        checkpoint = self.output / data['checkpoint']['name']; original_checkpoint = checkpoint.read_text()
        proof_path = self.output / 'reg-unload-proof-private.log'; original_proof = proof_path.read_text()
        wrong = original_proof.replace(native_fixture.BOOT, '87654321-1234-1234-1234-123456789abc')
        proof_path.write_text(wrong); data['proofs']['reg-unload'] = hashlib.sha256(proof_path.read_bytes()).hexdigest()
        self.journal.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError): self.subject.load_source(self.restored(self.output), self.life.root, self.output, {'modules':{}})
        proof_path.write_text(original_proof); self.journal.path.write_text(original)
        invalid = [original_checkpoint.replace('name=rfkill present=0 state=-', 'name=rfkill present=1 state=live'),
                   original_checkpoint + '[ 1200.000000] N71_OTHER_ACTION unknown\n']
        for text in invalid:
            checkpoint.write_text(text); data = json.loads(original)
            data['checkpoint']['sha256'] = hashlib.sha256(checkpoint.read_bytes()).hexdigest(); self.journal.path.write_text(json.dumps(data))
            with self.subTest(text=text[-100:]), self.assertRaises(ValueError):
                self.subject.load_source(self.restored(self.output), self.life.root, self.output, {'modules':{}})
        checkpoint.write_text(original_checkpoint)
        for name in ('pcie-cleanup', 'pcie-unload', 'restore'):
            data = json.loads(original); data['proofs'].pop(name); self.journal.path.write_text(json.dumps(data))
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.subject.load_source(self.restored(self.output), self.life.root, self.output, {'modules':{}})
        self.journal.path.write_text(original)


class RuntimeHeldMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite(
            unittest.defaultTestLoader.loadTestsFromTestCase(case) for case in (RuntimeHeldShellTests, RuntimeHeldSourceTests)))
        self.assertTrue(baseline.wasSuccessful(), baseline.failures + baseline.errors)
        source = SOURCE.read_text()
        mutations = [
            ('module-getter', 'command += n71_driver_module_stage.getter(session)', 'command += ""', RuntimeHeldShellTests, 'test_snapshot_reads_real_module_files_without_the_diagnostic_host'),
            ('effect-boot-test', "'test \"$(cat /proc/sys/kernel/random/boot_id)\" = \"' + expected + '\"; '", "''", RuntimeHeldShellTests, 'test_effect_guard_checks_the_actual_boot_before_writing'),
            ('effect-boot-print', "'printf \"N71_BOOT_ID \"; cat /proc/sys/kernel/random/boot_id; '", "''", RuntimeHeldShellTests, 'test_effect_guard_checks_the_actual_boot_before_writing'),
            ('filtered-stdout', 'raw = path.read_text()', 'raw = process.stdout', RuntimeHeldShellTests, 'test_raw_capture_rejects_other_duplicate_missing_boot_or_failed_transport'),
            ('stripped-stderr', 'raw = path.read_text()', "raw = path.read_text().split('\\nSTDERR\\n', 1)[0]", RuntimeHeldShellTests, 'test_raw_capture_rejects_other_duplicate_missing_boot_or_failed_transport'),
            ('capture-boot', "one(raw, 'N71_BOOT_ID ', r'^N71_BOOT_ID ([0-9a-f-]{36})$') == session.result.get('boot_id')", 'True', RuntimeHeldSourceTests, 'test_bad_unload_capture_preserves_reg_owners_without_registering_unload'),
            ('capture-transport', "process.returncode == 0, 'Runtime held effect did not complete'", "True, 'Runtime held effect did not complete'", RuntimeHeldShellTests, 'test_raw_capture_rejects_other_duplicate_missing_boot_or_failed_transport'),
            ('capture-private', 'device_profile.protected(path)', 'pass', RuntimeHeldShellTests, 'test_capture_stage_permissions_symlinks_and_size_are_bounded'),
            ('capture-stage', "isinstance(stage, str) and re.fullmatch(r'[a-z][a-z0-9-]*', stage)", 'True', RuntimeHeldShellTests, 'test_capture_stage_permissions_symlinks_and_size_are_bounded'),
            ('capture-budget', 'path.stat().st_size <= 2 * 1024 * 1024', 'True', RuntimeHeldShellTests, 'test_capture_stage_permissions_symlinks_and_size_are_bounded'),
            ('budget-boundary', 'path.stat().st_size <= 2 * 1024 * 1024', 'path.stat().st_size < 2 * 1024 * 1024', RuntimeHeldShellTests, 'test_capture_stage_permissions_symlinks_and_size_are_bounded'),
            ('full-held-history', 'expected_history = n71_session_history.kernel_lines(text)', 'pass', RuntimeHeldSourceTests, 'test_removed_source_loader_and_read_only_recovery_preserve_origin'),
            ('loaded-boot-context', 'session.result = dict(result)', 'pass', RuntimeHeldSourceTests, 'test_removed_source_loader_and_read_only_recovery_preserve_origin'),
            ('held-proof-boot', "one(proof, 'N71_BOOT_ID ', r'^N71_BOOT_ID ([0-9a-f-]{36})$') == result['boot_id']", 'True', RuntimeHeldSourceTests, 'test_removed_source_rejects_wrong_boot_owner_or_history_and_missing_proofs'),
            ('removed-lifetime', "if n71_driver_module_stage.selected(session) is not None and 'pcie-cleanup' in verified:", 'if False:', RuntimeHeldSourceTests, 'test_removed_source_rejects_wrong_boot_owner_or_history_and_missing_proofs'),
            ('clean-observation', 'proof = live_text if n71_driver_module_stage.selected(session) is not None else fresh', 'proof = fresh', RuntimeHeldSourceTests, 'test_already_clean_host_registers_the_complete_observation_without_replay'),
            ('unload-output', "proof = proof_output(session, 'held-pcie-unload', process)", 'proof = process.stdout', RuntimeHeldSourceTests, 'test_release_records_complete_private_logs_before_discarding_owners'),
            ('restore-output', "proof = proof_output(session, 'held-restore', process)", 'proof = process.stdout', RuntimeHeldSourceTests, 'test_release_records_complete_private_logs_before_discarding_owners'),
            ('reg-unload-output', "proof = proof_output(session, 'held-reg-unload', process)", 'proof = process.stdout', RuntimeHeldSourceTests, 'test_release_records_complete_private_logs_before_discarding_owners'),
        ]
        for name, old, new, case, method in mutations:
            with self.subTest(name=name):
                prefix = suffix = ''; target = source
                if name == 'effect-boot-print':
                    node = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'effect_boot')
                    lines = source.splitlines(keepends=True)
                    prefix, target, suffix = ''.join(lines[:node.lineno - 1]), ''.join(lines[node.lineno - 1:node.end_lineno]), ''.join(lines[node.end_lineno:])
                self.assertEqual(target.count(old), 1, name)
                subject = ModuleType('runtime_held_capture_mutant')
                exec(compile(ast.parse(prefix + target.replace(old, new, 1) + suffix), str(SOURCE), 'exec'), subject.__dict__)
                mutant = type('MutatedRuntimeHeldTests', (case,), {'subject': subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(mutant(method))
                self.assertEqual(result.errors, [], name); self.assertGreater(len(result.failures), 0, name)
                print('N71_RUNTIME_HELD_CAPTURE_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
