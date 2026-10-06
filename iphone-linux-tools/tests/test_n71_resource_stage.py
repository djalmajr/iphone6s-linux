"""Assign once, retain errors and resume proved cleanup without another boot."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_n71_held_session as held_fixture
import test_n71_resource_result as resource_fixture

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('resource_stage_under_test',
                                            os.environ.get('N71_RESOURCE_STAGE_SCRIPT', ROOT / 'scripts/host/n71_resource_stage.py'))
STAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE)
HELD = held_fixture.HELD
LINK = held_fixture.LINK_SESSION


class ResourcePhone(held_fixture.Phone):
    def __init__(self):
        super().__init__()
        self.resources = dict(STAGE.INITIAL)
        self.assignments = 0
        self.assignment_error = 0
        self.early_refusal = False
        self.failure = None
        self.corrupt_final = False
        self.removed = self.configured = self.pme_tls_restored = False

    def getter(self):
        return 'N71_PCIE_RESOURCES ' + ' '.join(name + '=' + str(self.resources[name])
                                               for name in STAGE.n71_resource_result.FIELDS) + '\n'

    def snapshot(self, session):
        text = super().snapshot(session)
        if self.pcie and session.resource_capable:
            getter = self.getter()
            if self.corrupt_final and self.assignments:
                getter = getter.replace('assigned=1', 'assigned=0')
            return getter + text
        return text

    def capture(self, session, stage, command, raw=None):
        if stage not in ('held-assign', 'held-cleanup'):
            return super().capture(session, stage, command, raw)
        self.calls.append((stage, command))
        code = 0
        if stage == 'held-assign':
            state = json.loads((session.output / 'held-state-private.json').read_text())
            if state.get('resource_attempted') is not True:
                raise AssertionError('Assignment preceded durable intent')
            if 'printf "assign\n"' not in command or self.resources != STAGE.INITIAL:
                code, text = 1, ''
            else:
                self.assignments += 1
                error = self.assignment_error
                self.status = held_fixture.ACTIVE.replace('primary_error=0', 'primary_error=' + str(error))
                self.resources = dict(ready=1, attempted=int(not self.early_refusal), assigned=int(error == 0),
                                      pending=int(not self.early_refusal), claimed=int(not self.early_refusal),
                                      active=0, error=error)
                if not self.early_refusal:
                    event = resource_fixture.RESULT.replace('error=0 assigned=1',
                                                             f'error={error} assigned={int(error == 0)}')
                    self.history += held_fixture.timestamp(event, 60)
                code = int(error != 0)
                text = f'N71_PCIE_RESOURCE_ACTION exit={code}\n' + self.getter() + 'N71_PCIE_HELD held=1\n' + self.status + self.history
        else:
            self.cleanup_calls += 1
            error = self.assignment_error
            cleanup_error = -5
            if not self.removed:
                extra = ''
                stop = error if not self.early_refusal else 0
                if self.failure == 'late-stop':
                    extra = 'N71_PCIE_SCAN_WRITE_REFUSED bus=1 devfn=00 where=004 size=2 value=00000000 error=-1\n'
                    stop = -1
                self.history += held_fixture.timestamp(extra + held_fixture.REMOVED.replace('stop-error=0', 'stop-error=' + str(stop)), 70)
                self.removed = True
            self.held = False
            self.empty = True
            self.resources['assigned'] = 0
            if self.resources['pending']:
                if self.failure == 'extra-once':
                    self.failure = None
                    self.history += held_fixture.timestamp(resource_fixture.RESTORE.replace('error=0 pending=0', 'error=-5 pending=1'), 80)
                    self.resources['error'] = error
                    code = 1
                else:
                    self.history += held_fixture.timestamp(resource_fixture.RESTORE, 90)
                    self.resources['pending'] = 0
            if not code and not self.configured:
                self.history += held_fixture.timestamp(held_fixture.CONFIG, 100)
                self.configured = True
            if not code and self.resources['claimed']:
                if self.failure == 'window-once':
                    self.failure = None
                    cleanup_error = -16
                    code = 1
                else:
                    self.history += held_fixture.timestamp(resource_fixture.RELEASE, 110)
                    self.resources['claimed'] = 0
            if not code and not self.pme_tls_restored:
                self.history += held_fixture.timestamp(held_fixture.PME_RESTORED + held_fixture.TLS_RESTORED, 120)
                self.pme_tls_restored = True
            if not code and self.failure == 'late-stop':
                self.failure = None
                self.resources = dict.fromkeys(STAGE.n71_resource_result.FIELDS, 0)
                self.resources['error'] = error
                cleanup_error = -1
                code = 1
            if code:
                scan_pending = int(not self.pme_tls_restored)
                self.status = (held_fixture.ACTIVE.replace('primary_error=0', 'primary_error=' + str(error))
                               .replace('cleanup_error=0', 'cleanup_error=' + str(cleanup_error)).replace('scan_pending=1', 'scan_pending=' + str(scan_pending)))
                final = ('N71_PCIE_SESSION_CLEANUP error=' + str(cleanup_error) + ' retained=1 scan_pending=' + str(scan_pending)
                         + f' reset_pending=1 powered=4 attached=4 power_put_pending=0 primary_error={error}\n')
                self.history += held_fixture.timestamp(final, 150)
            else:
                self.status = held_fixture.CLEAN.replace('primary_error=0', 'primary_error=' + str(error))
                final = held_fixture.FINISHED.replace('primary_error=0', 'primary_error=' + str(error))
                self.history += held_fixture.timestamp(held_fixture.RESET + held_fixture.POWER + final, 160)
                self.resources = dict.fromkeys(STAGE.n71_resource_result.FIELDS, 0)
                self.resources['error'] = error
            text = self.getter() + 'N71_PCIE_HELD held=0\n' + self.status + self.history
        if stage in self.overrides:
            changed = self.overrides[stage]
            code, text = changed(self, session, text) if callable(changed) else changed
        path = session.output / (stage + '-private.log')
        with path.open('x') as stream:
            stream.write(text + '\nSTDERR\n')
        path.chmod(0o600)
        return SimpleNamespace(returncode=code, stdout=session.history.fresh(text) if session.history else text)


class ResourceStageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / 'runtime').mkdir(mode=0o700)
        self.phone = ResourcePhone()
        self.modules = [({'module': name, 'sha256': hashlib.sha256(name.encode()).hexdigest()}, name.encode())
                        for name in HELD.MODULES]
        self.identity = {'deployment_sha256': 'a' * 64, 'payload_sha256': 'b' * 64, 'initramfs_sha256': 'c' * 64,
                         'modules': {record['module']: record['sha256'] for record, _ in self.modules}}
        for target, name, value in ((HELD, 'n71_resource_stage', STAGE), (LINK, 'ROOT', ROOT)):
            changed = patch.object(target, name, value)
            changed.start()
            self.addCleanup(changed.stop)

    def execute(self, name, source=None, *, assign=False, capable=True):
        output = self.root / 'runtime' / name
        output.mkdir(mode=0o700)
        with patch.object(LINK.device_profile, 'ssh_options', return_value=[]):
            session = LINK.Session(output, self.modules, host_scan=True, scan_link_target=True,
                                   scan_pme_disable=True, scan_hold=True, resource_capable=capable,
                                   release=LINK.BINDING_RELEASE)
        session.capture = lambda *args, **kwargs: self.phone.capture(session, *args, **kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            code = HELD.run(session, self.identity, root=self.root, source=source, assign=assign)
        return code, session, output

    def acquired(self):
        code, _, path = self.execute('acquire')
        self.assertEqual(code, 0)
        return path

    def assigned(self):
        source = self.acquired()
        code, session, path = self.execute('assign', source, assign=True)
        self.assertEqual(code, 0)
        self.assertTrue(session.result['resource_assignment']['assignment_verified'])
        self.assertTrue((path / (STAGE.PROOF + '-proof-private.log')).is_file())
        return path

    def test_assign_reuse_and_release_preserve_one_scan_and_durable_private_proofs(self):
        # Mutations killed: omit durable intent, setter/proof/getter, reuse guard or assignment-aware cleanup.
        source = self.assigned()
        state = json.loads((source / 'held-state-private.json').read_text())
        self.assertIs(state['resource_capable'], True)
        self.assertIs(state['resource_attempted'], True)
        self.assertIn(STAGE.PROOF, state['proofs'])
        self.assertEqual((source / (STAGE.PROOF + '-proof-private.log')).stat().st_mode & 0o777, 0o600)
        code, reused, path = self.execute('reuse', source, assign=True)
        self.assertEqual(code, 0)
        self.assertIs(reused.result['resource_assignment_reused'], True)
        self.assertEqual(self.phone.assignments, 1)
        self.assertTrue(self.phone.held and self.phone.active and self.phone.pcie and self.phone.reg)
        code, released, clean = self.execute('release', path)
        self.assertEqual(code, 0)
        self.assertTrue(released.result['cleanup_verified'])
        self.assertFalse(self.phone.pcie or self.phone.reg or self.phone.active)
        self.assertEqual(sum(stage == 'pcie' for stage, _ in self.phone.calls), 1)
        self.assertEqual(self.phone.cleanup_calls, 1)
        self.assertEqual(self.execute('release-again', clean)[0], 0)
        self.assertEqual(self.phone.cleanup_calls, 1)

    def test_resource_candidate_can_release_without_an_assignment(self):
        # Mutation killed: make assignment automatic or require an invented assignment event on cleanup.
        source = self.acquired()
        self.assertEqual(self.phone.assignments, 0)
        code, session, _ = self.execute('release', source)
        self.assertEqual(code, 0)
        self.assertTrue(session.result['cleanup_verified'])
        self.assertEqual(self.phone.assignments, 0)

    def test_assignment_scope_requires_saved_resource_mode_and_exact_boolean(self):
        # Mutations killed: assign during acquisition, ignore saved mode or accept nonboolean assignment intent.
        self.assertEqual(self.execute('no-source', assign=True)[0], 1)
        self.assertEqual(self.phone.calls, [])
        source = self.acquired()
        before = len(self.phone.calls)
        self.assertEqual(self.execute('legacy-mode', source, capable=False)[0], 1)
        self.assertEqual(len(self.phone.calls), before)
        self.assertEqual(self.execute('legacy-assign', source, assign=True, capable=False)[0], 1)
        self.assertEqual(len(self.phone.calls), before)
        self.assertEqual(self.execute('nonboolean', source, assign=1)[0], 1)
        self.assertEqual(len(self.phone.calls), before)

    def test_getter_checkpoint_proof_and_intent_tampering_refuse_before_effects(self):
        # Mutations killed: omit source proof hash, mode/intent contract or live getter comparison.
        source = self.assigned()
        state_path = source / 'held-state-private.json'
        original = state_path.read_text()
        data = json.loads(original)
        summary = dict(data['result'], resource_assignment=dict(data['result']['resource_assignment'], error=-5))
        cases = (dict(data, resource_capable=False), dict(data, resource_capable=1), dict(data, result=summary),
                 dict(data, resource_attempted=False), dict(data, resource_attempted=None),
                 dict(data, proofs={}), dict(data, checkpoint=None))
        for index, altered in enumerate(cases):
            state_path.write_text(json.dumps(altered))
            self.assertEqual(self.execute('bad-state-' + str(index), source, assign=True)[0], 1)
            self.assertEqual(self.phone.assignments, 1)
            self.assertEqual(self.phone.cleanup_calls, 0)
        state_path.write_text(original)
        self.phone.overrides['held-resume-live'] = lambda phone, session, text: (0, text.replace('claimed=1 active=0', 'claimed=0 active=0', 1))
        self.assertEqual(self.execute('bad-getter', source)[0], 1)
        self.assertEqual(self.phone.cleanup_calls, 0)
        del self.phone.overrides['held-resume-live']
        proof = source / (STAGE.PROOF + '-proof-private.log')
        proof.write_text(proof.read_text() + 'CHANGED\n')
        self.assertEqual(self.execute('bad-proof', source)[0], 1)
        self.assertEqual(self.phone.cleanup_calls, 0)

    def test_changed_boot_history_or_acquisition_getter_does_not_assign(self):
        # Mutations killed: bypass same-boot/history identity or omit initial resource ownership checks.
        source = self.acquired()
        for index, (before, after) in enumerate(((held_fixture.BOOT, '22345678-1234-1234-1234-123456789abc'),
                                               ('attempted=0 assigned=0', 'attempted=1 assigned=0'))):
            self.phone.overrides['held-resume-live'] = lambda phone, session, text, b=before, a=after: (0, text.replace(b, a, 1))
            self.assertEqual(self.execute('changed-' + str(index), source, assign=True)[0], 1)
        del self.phone.overrides['held-resume-live']
        self.phone.history += held_fixture.timestamp('N71_PCIE_RESOURCE_UNKNOWN pending=0\n', 200)
        self.assertEqual(self.execute('changed-history', source, assign=True)[0], 1)
        self.assertEqual(self.phone.assignments, 0)
        self.assertEqual(self.phone.cleanup_calls, 0)

    def test_negative_assignment_and_early_refusal_keep_error_after_release(self):
        # Mutations killed: mask assignment errors or manufacture counters/owners for an early refusal.
        for early in (False, True):
            with self.subTest(early=early):
                self.phone = ResourcePhone()
                source = self.execute('acquire-' + str(early))[2]
                self.phone.assignment_error = -13
                self.phone.early_refusal = early
                code, session, assigned = self.execute('assign-' + str(early), source, assign=True)
                self.assertEqual(code, 1)
                self.assertEqual(session.result['resource_assignment']['error'], -13)
                self.assertIs(session.result['resource_assignment']['early_refusal'], early)
                self.assertTrue(self.phone.held and self.phone.active)
                self.assertEqual(session.result['resource_assignment']['event'] is None, early)
                code, released, _ = self.execute('release-' + str(early), assigned)
                self.assertEqual(code, 1)
                self.assertTrue(released.result['cleanup_verified'])
                self.assertEqual(released.result['resource_assignment']['error'], -13)
                self.assertFalse(self.phone.pcie or self.phone.reg or self.phone.active)

    def test_extra_restore_and_window_release_retries_never_assign_or_rescan(self):
        # Mutations killed: unload/restore REG_ON before extra config/window cleanup or repeat completed restoration.
        for failure in ('extra-once', 'window-once'):
            self.phone = ResourcePhone()
            source = self.execute('acquire-' + failure)[2]
            self.assertEqual(self.execute('assign-' + failure, source, assign=True)[0], 0)
            assigned = self.root / 'runtime' / ('assign-' + failure)
            self.phone.failure = failure
            code, session, pending = self.execute('pending-' + failure, assigned)
            self.assertEqual(code, 1)
            self.assertFalse(session.result['cleanup_verified'])
            self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)
            code, resumed, _ = self.execute('retry-' + failure, pending)
            self.assertEqual(code, 0)
            self.assertTrue(resumed.result['cleanup_verified'])
            self.assertEqual(self.phone.assignments, 1)
            self.assertEqual(sum(stage == 'pcie' for stage, _ in self.phone.calls), 1)
            self.assertEqual(self.phone.history.count('N71_PCIE_SCAN_CONFIG_RESTORED error=0'), 1)

    def test_negative_stop_after_assignment_remains_negative_when_cleanup_finishes(self):
        # Mutation killed: convert a late PCI stop refusal into successful cleanup/operation.
        source = self.assigned()
        self.phone.failure = 'late-stop'
        code, _, pending = self.execute('stop-pending', source)
        self.assertEqual(code, 1)
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)
        code, session, _ = self.execute('stop-retry', pending)
        self.assertEqual(code, 1)
        self.assertTrue(session.result['cleanup_verified'])
        self.assertEqual(session.result['stop_error'], -1)
        self.assertFalse(self.phone.pcie or self.phone.reg or self.phone.active)

    def test_unload_retry_reuses_assignment_and_completed_pci_cleanup(self):
        # Mutation killed: repeat cleanup after PCI unload failed or discard the assignment proof on continuation.
        source = self.assigned()
        self.phone.overrides['held-pcie-unload'] = lambda phone, session, text: (setattr(phone, 'pcie', True) or 1, '')
        code, _, pending = self.execute('unload-pending', source)
        self.assertEqual(code, 1)
        del self.phone.overrides['held-pcie-unload']
        code, session, _ = self.execute('unload-retry', pending)
        self.assertEqual(code, 0)
        self.assertTrue(session.result['cleanup_verified'])
        self.assertEqual(self.phone.assignments, 1)
        self.assertEqual(self.phone.cleanup_calls, 1)

    def test_incomplete_action_or_wrong_transport_exit_keeps_owners_without_a_proof(self):
        # Mutations killed: ignore action proof or accept transport exit that differs from the recorded setter exit.
        for index, invalid in enumerate((lambda phone, session, text: (255, text),
                                         lambda phone, session, text: (0, text.replace('N71_PCIE_RESOURCE_ACTION exit=0\n', '')))):
            self.phone = ResourcePhone()
            source = self.execute('acquire-' + str(index))[2]
            self.phone.overrides['held-assign'] = invalid
            code, session, pending = self.execute('bad-action-' + str(index), source, assign=True)
            self.assertEqual(code, 1)
            self.assertIn('held_error', session.result)
            self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)
            before = len(self.phone.calls)
            self.assertEqual(self.execute('unproved-release-' + str(index), pending)[0], 1)
            self.assertEqual(len(self.phone.calls), before)
            self.assertEqual(self.phone.cleanup_calls, 0)

    def test_missing_extra_restore_prevents_unload_and_reg_on_release(self):
        # Mutation killed: use the old held parser after assignment and skip resource rollback validation.
        source = self.assigned()
        self.phone.overrides['held-cleanup'] = lambda phone, session, text: (0, text.replace(resource_fixture.RESTORE.rstrip(), 'MISSING_EXTRA_RESTORE'))
        code, session, _ = self.execute('bad-cleanup', source)
        self.assertEqual(code, 1)
        self.assertFalse(session.result['cleanup_verified'])
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)
        self.assertFalse(any(stage in ('held-pcie-unload', 'held-restore') for stage, _ in self.phone.calls))

    def test_pending_getter_change_and_unknown_checkpoint_operation_refuse_before_cleanup(self):
        # Mutations killed: ignore the pending resource getter or allow an unproved operation in the saved history.
        source = self.assigned()
        self.phone.failure = 'window-once'
        code, _, pending = self.execute('window-pending', source)
        self.assertEqual(code, 1)
        self.assertFalse(self.phone.held)
        self.assertEqual((self.phone.resources['pending'], self.phone.resources['claimed']), (0, 1))
        self.assertTrue((pending / 'held-state-private.json').is_file())
        calls = self.phone.cleanup_calls
        self.phone.overrides['held-resume-live'] = lambda phone, session, text: (0, text.replace('active=0 error=0', 'active=0 error=-1', 1))
        self.assertEqual(self.execute('changed-pending-getter', pending)[0], 1)
        self.assertEqual(self.phone.cleanup_calls, calls)
        del self.phone.overrides['held-resume-live']
        state_path = pending / 'held-state-private.json'
        data = json.loads(state_path.read_text())
        checkpoint = pending / data['checkpoint']['name']
        foreign = held_fixture.timestamp('N71_PCIE_RESOURCE_UNKNOWN pending=0\n', 200)
        self.phone.history += foreign
        checkpoint.write_text(checkpoint.read_text().replace('\nSTDERR\n', foreign + '\nSTDERR\n'))
        data['checkpoint']['sha256'] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        state_path.write_text(json.dumps(data))
        self.assertEqual(self.execute('unknown-checkpoint', pending)[0], 1)
        self.assertEqual(self.phone.cleanup_calls, calls)

    def test_final_assignment_getter_mismatch_is_not_reported_as_success(self):
        # Mutation killed: omit the final retained-resource check after saving a positive action proof.
        source = self.acquired()
        self.phone.corrupt_final = True
        code, session, _ = self.execute('changed-final', source, assign=True)
        self.assertEqual(code, 1)
        self.assertIn('held_error', session.result)
        self.assertFalse(session.result['cleanup_verified'])
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)

    def test_shell_rechecks_boot_latch_held_and_resources_before_the_setter(self):
        # Mutations killed: omit an immediate command guard and write assign after live ownership changed.
        source = self.acquired()
        session = SimpleNamespace(resource_capable=True, release=LINK.BINDING_RELEASE, result={'boot_id': held_fixture.BOOT})
        pcie = self.root / 'sys/module/n71_pcie_diagnostic/parameters'
        reg = self.root / 'sys/module/n71_wlan_power_diagnostic/parameters'
        boot = self.root / 'proc/sys/kernel/random/boot_id'
        pcie.mkdir(parents=True)
        reg.mkdir(parents=True)
        boot.parent.mkdir(parents=True)
        tools = self.root / 'bin'
        tools.mkdir()
        for name, program in (('uname', '#!/bin/sh\nprintf "%s\\n" ' + shlex.quote(LINK.BINDING_RELEASE) + '\n'),
                              ('dmesg', '#!/bin/sh\nprintf "%s\\n" "PCIe ASPM is disabled"\n')):
            path = tools / name
            path.write_text(program)
            path.chmod(0o700)
        values = {boot: held_fixture.BOOT + '\n', pcie / 'held': 'held=1\n',
                  pcie / 'status': held_fixture.ACTIVE.removeprefix('N71_PCIE_STATUS '),
                  pcie / 'resources': ResourcePhone().getter().removeprefix('N71_PCIE_RESOURCES '),
                  reg / 'state': LINK.STATE_ACTIVE + '\n', reg / 'control': 'N71_REG_ON_CONTROL_READBACK value=81\n'}
        for path, value in values.items():
            path.write_text(value)
        action = pcie / 'action'
        command = re.sub(r'/(sys|proc)/', lambda match: str(self.root / match[1]) + '/', STAGE.command(session))
        environment = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'])
        action.write_text('UNTOUCHED\n')
        result = subprocess.run(['bash', '-c', command], env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(action.read_text(), 'assign\n')
        self.assertIn('N71_PCIE_RESOURCE_ACTION exit=0\n', result.stdout)
        self.assertIn('N71_PCIE_RESOURCES ready=1 attempted=0', result.stdout)
        for path, bad in ((boot, '22345678-1234-1234-1234-123456789abc\n'), (pcie / 'held', 'held=0\n'),
                           (reg / 'state', held_fixture.REG_CLEAN.splitlines()[0] + '\n'),
                           (reg / 'control', 'N71_REG_ON_CONTROL_READBACK value=80\n'),
                           (pcie / 'resources', values[pcie / 'resources'].replace('attempted=0', 'attempted=1'))):
            action.write_text('UNTOUCHED\n')
            path.write_text(bad)
            result = subprocess.run(['bash', '-c', command], env=environment, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(action.read_text(), 'UNTOUCHED\n')
            path.write_text(values[path])
        session.module_directory = '/run/n71-link-' + 'a' * 24
        session.modules = self.modules
        staged = self.root / 'staged'
        staged.mkdir()
        for record, raw in self.modules:
            (staged / record['module']).write_bytes(raw)
        for name in HELD.TRUE_PARAMETERS + HELD.FALSE_PARAMETERS:
            (pcie / name).write_text(('Y' if name in HELD.TRUE_PARAMETERS else 'N') + '\n')
        (self.root / 'proc/cmdline').write_text('rdinit=/init pcie_aspm=off\n')
        (self.root / 'sys/bus/pci/devices/0001:01:00.0').mkdir(parents=True)
        hashes = tools / 'sha256sum'
        hashes.write_text('#!' + sys.executable + '\nimport hashlib,sys\nfrom pathlib import Path\n'
                          'for name in sys.argv[1:]:\n print(hashlib.sha256(Path(name).read_bytes()).hexdigest()+"  "+name)\n')
        hashes.chmod(0o700)
        command = re.sub(r'/(sys|proc)/', lambda match: str(self.root / match[1]) + '/', HELD.snapshot_command(session))
        command = command.replace(session.module_directory, str(staged))
        result = subprocess.run(['bash', '-c', command], env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('N71_PCIE_RESOURCES ready=1 attempted=0', result.stdout)
        self.assertTrue(source.is_dir())

    def test_cli_assignment_scope_and_local_source_check_do_not_use_ssh(self):
        # Mutations killed: skip CLI assignment mode/scope or source check, or accept a nonboolean saved intent.
        profile, _, argv = held_fixture.HeldSessionTests.resource_cli(self)
        records = STAGE.n71_resource_result.selected_records(self.root, release=LINK.BINDING_RELEASE)
        self.modules = [(record, (self.root / record['module']).read_bytes()) for record in records]
        self.identity = HELD.identity(self.root / 'deployment.json', profile, self.modules)
        source = self.acquired()
        command = argv + ['--assign-held', str(source)]
        with patch.object(LINK, 'ROOT', self.root), patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(LINK.device_profile, 'verify', return_value=profile), \
                patch.object(LINK.device_profile, 'ssh_options', return_value=[]), \
                patch.object(LINK.n71_held_session, 'load_source', wraps=HELD.load_source), \
                patch.object(LINK.subprocess, 'run', side_effect=AssertionError('Unexpected SSH')):
            with patch.object(sys, 'argv', command):
                try:
                    self.assertEqual(LINK.main(), 0)
                except (ValueError, OSError, SystemExit) as error:
                    self.fail('Valid assignment check refused: ' + str(error))
            for omitted in ('--resource-capable', '--scan-hold'):
                with patch.object(sys, 'argv', [arg for arg in command if arg != omitted]), self.assertRaises(ValueError):
                    LINK.main()
            with patch.object(sys, 'argv', command + ['--previous-clean', str(source)]), self.assertRaises(ValueError):
                LINK.main()
            with patch.object(sys, 'argv', command + ['--release-held', str(source)]), self.assertRaises(SystemExit) as error:
                LINK.main()
            self.assertEqual(error.exception.code, 2)
            data_path = source / 'held-state-private.json'
            data = json.loads(data_path.read_text())
            data['resource_attempted'] = 0
            data_path.write_text(json.dumps(data))
            with patch.object(sys, 'argv', command), self.assertRaises(ValueError):
                LINK.main()
            data['resource_attempted'] = False
            data_path.write_text(json.dumps(data))
            live = [arg for arg in command if arg != '--check'] + ['--output-dir', str(self.root / 'runtime/cli-assigned')]
            with patch.object(LINK.n71_held_session, 'run', wraps=HELD.run), \
                    patch.object(LINK.Session, 'capture', autospec=True, side_effect=self.phone.capture), \
                    patch.object(sys, 'argv', live):
                try:
                    self.assertEqual(LINK.main(), 0)
                except (ValueError, OSError, SystemExit) as error:
                    self.fail('Valid assignment CLI refused: ' + str(error))
            result = json.loads((self.root / 'runtime/cli-assigned/result-private.json').read_text())
            self.assertIn('resource_assignment', result)
            self.assertTrue(result['resource_assignment']['assignment_verified'])
            self.assertEqual(self.phone.assignments, 1)

    @unittest.skipIf(os.environ.get('N71_RESOURCE_STAGE_MUTATION_CHILD') == '1', 'Mutation child runs contracts only')
    def test_mutations_fail_behavioral_assertions(self):
        changes = {
            'stage-intent': ('session.resource_attempted = True', 'session.resource_attempted = False'),
            'stage-intent-save': ('    journal.save()\n    process = session.capture', '    pass\n    process = session.capture'),
            'stage-reuse': ('if session.resource_attempted:', 'if False:'),
            'stage-proof-save': ('journal.proof(PROOF, process.stdout)', 'journal.save()'),
            'stage-getter': ("return 'printf \"N71_PCIE_RESOURCES \"; cat ' + PCIE + 'resources; ' if capable(session) else ''", "return ''"),
            'stage-mode': ("data.get('resource_capable', False) is capable(session)", 'True'),
            'stage-intent-type': ("type(attempted) is bool and (not attempted or capable(session)), 'Saved resource", "True, 'Saved resource"),
            'stage-summary': ("data['result'].get('resource_assignment') == assignment", 'True'),
            'stage-live-getter': ('n71_resource_result.live_status(live) == n71_resource_result.live_status(prior)', 'True'),
            'stage-unknown-operation': ('all(marker in allowed for marker in markers) and (assignment is not None or not markers)', 'True'),
            'stage-action-exit': ("process.returncode == assignment['action_exit']", 'True'),
            'stage-error-exit': ("return assignment is None or assignment['error'] == 0", 'return True'),
            'stage-boot-recheck': ("'test \"$(cat /proc/sys/kernel/random/boot_id)\" = \"' + session.result['boot_id'] + '\"; '", "''"),
            'stage-held-recheck': ("'test \"$(cat ' + PCIE + 'held)\" = \"held=1\"; '", "''"),
            'stage-reg-state-recheck': ("'test \"$(cat ' + REG + 'state)\" = \"bound=1 active=1 restore_pending=1 original=80\"; '", "''"),
            'stage-reg-control-recheck': ("'test \"$(cat ' + REG + 'control)\" = \"N71_REG_ON_CONTROL_READBACK value=81\"; '", "''"),
            'stage-resource-recheck': ("'test \"$(cat ' + PCIE + 'resources)\" = \"' + initial + '\"; '", "''"),
            'stage-action-record': ('N71_PCIE_RESOURCE_ACTION exit=%s', 'N71_PCIE_OTHER_ACTION exit=%s'),
        }
        coordinator = {
            'stage-source-load': ('n71_resource_stage.load_source(session, data, verified)', 'pass'),
            'stage-resource-proofs': ('PROOFS + n71_resource_stage.extra_proofs(session)', 'PROOFS'),
            'stage-resume': ('n71_resource_stage.resume(session, live, prior)', 'pass'),
            'stage-snapshot-getter': ('command += n71_resource_stage.getter(session)', "command += ''"),
            'stage-cleanup-parser': ('cleanup = n71_resource_stage.cleanup(session, proof)', 'cleanup = n71_scan_held_result.cleanup(proof)'),
            'stage-final-check': ('n71_resource_stage.retained(session, Baseline(journal.baseline).fresh(final))', 'pass'),
        }
        cli = {
            'stage-cli-source-check': ('if options.release_held or options.assign_held:', 'if options.release_held:'),
            'stage-cli-live-dispatch': ('assign=options.assign_held is not None', 'assign=False'),
        }
        with tempfile.TemporaryDirectory(prefix='n71-resource-stage-mutations-') as directory:
            for source, variable, variants in ((ROOT / 'scripts/host/n71_resource_stage.py', 'N71_RESOURCE_STAGE_SCRIPT', changes),
                                               (ROOT / 'scripts/host/n71_held_session.py', 'N71_HELD_SESSION_SCRIPT', coordinator),
                                               (ROOT / 'scripts/host/n71-link-session.py', 'N71_HELD_LINK_SCRIPT', cli)):
                text = source.read_text()
                for name, (before, after) in variants.items():
                    self.assertEqual(text.count(before), 1, name)
                    path = Path(directory) / (name + '.py')
                    path.write_text(text.replace(before, after))
                    compile(path.read_text(), str(path), 'exec')
                    environment = dict(os.environ, N71_RESOURCE_STAGE_MUTATION_CHILD='1', PYTHONDONTWRITEBYTECODE='1')
                    environment[variable] = str(path)
                    process = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                                              '-p', 'test_n71_resource_stage.py'], env=environment, capture_output=True, text=True, timeout=45)
                    output = process.stdout + process.stderr
                    self.assertNotEqual(process.returncode, 0, name)
                    self.assertIn('AssertionError', output, name + '\n' + output)
                    self.assertNotIn('ERROR:', output, name + '\n' + output)
                    print('N71_RESOURCE_STAGE_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
