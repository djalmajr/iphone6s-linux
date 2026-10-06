"""Held commands preserve live owners and resume cleanup without another boot."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_n71_scan_held_result import ACTIVE, CLEAN, ACQUIRED, REMOVED, CONFIG, PME_RESTORED, TLS_RESTORED, RESET, POWER, FINISHED
from test_n71_link_session import LINK, INVENTORY, OBSERVE, ACTIVE as REG_ACTIVE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
SPEC = importlib.util.spec_from_file_location('held_link_under_test',
                                            os.environ.get('N71_HELD_LINK_SCRIPT', ROOT / 'scripts/host/n71-link-session.py'))
LINK_SESSION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINK_SESSION)
HELD_SPEC = importlib.util.spec_from_file_location('held_session_under_test',
                                                os.environ.get('N71_HELD_SESSION_SCRIPT', ROOT / 'scripts/host/n71_held_session.py'))
HELD = importlib.util.module_from_spec(HELD_SPEC)
HELD_SPEC.loader.exec_module(HELD)
BOOT = '12345678-1234-1234-1234-123456789abc'
BASELINE = '[ 1.000000] N71_TEST_BASELINE private\n'
REG_CLEAN = 'bound=1 active=0 restore_pending=0 original=80\nN71_REG_ON_CONTROL_READBACK value=80\n'


def timestamp(text, start):
    return ''.join(f'[ {start + index}.000000] {line}\n' for index, line in enumerate(text.splitlines()))


class Phone:
    def __init__(self):
        self.boot = BOOT
        self.pcie = self.reg = False
        self.empty = True
        self.active = False
        self.held = False
        self.history = BASELINE
        self.status = ACTIVE
        self.calls = []
        self.overrides = {}
        self.cleanup_calls = 0
        self.reg_reads = 0

    def snapshot(self, session):
        text = 'N71_BOOT_ID ' + self.boot + '\nN71_PCIE_CMDLINE rdinit=/init pcie_aspm=off\n'
        text += ''.join(record['sha256'] + '  ' + session.module_directory + '/' + record['module'] + '\n'
                        for record, _ in session.modules)
        text += f'N71_HELD_PCIE_PRESENT={int(self.pcie)}\nN71_HELD_REG_PRESENT={int(self.reg)}\nN71_HELD_PCI_EMPTY={int(self.empty)}\n'
        if self.pcie:
            text += 'N71_PCIE_HELD held=' + str(int(self.held)) + '\n' + self.status
            text += ''.join('N71_HELD_PARAM ' + name + '=' + ('Y' if name in HELD.TRUE_PARAMETERS else 'N') + '\n'
                            for name in HELD.TRUE_PARAMETERS + HELD.FALSE_PARAMETERS)
        if self.reg:
            self.reg_reads += 1
            value = '81' if self.active else '80'
            self.history += timestamp('N71_REG_ON_READ error=0 value_valid=1 value=' + value + '\n',
                                      160 + self.reg_reads)
            text += REG_ACTIVE if self.active else REG_CLEAN
        return text + self.history

    def capture(self, session, stage, command, raw=None):
        self.calls.append((stage, command))
        state = json.loads((session.output / 'held-state-private.json').read_text()) if (session.output / 'held-state-private.json').exists() else {}
        if stage in ('observe', 'activate', 'pcie'):
            name = {'observe': 'reg_attempted', 'activate': 'activation_attempted', 'pcie': 'pcie_attempted'}[stage]
            if not state.get(name):
                raise AssertionError('Effects preceded durable attempt record')
        code = 0
        if stage == 'preflight':
            text = session.release + '\nN71_BOOT_ID ' + self.boot + '\n' + self.history
        elif stage == 'aspm':
            text = 'N71_PCIE_CMDLINE pcie_aspm=off\nN71_PCIE_ASPM_DISABLED\n'
        elif stage == 'observe':
            self.reg = True
            text = OBSERVE
        elif stage == 'activate':
            self.active = True
            text = REG_ACTIVE
        elif stage == 'pcie':
            self.pcie = self.held = True
            self.empty = False
            self.history += timestamp(LINK + INVENTORY + ACQUIRED, 10)
            text = 'N71_PCIE_HELD held=1\n' + ACTIVE + self.history
        elif stage.startswith('held-checkpoint-') or stage in ('held-acquire-live', 'held-resume-live', 'held-failure-live'):
            text = self.snapshot(session)
        elif stage == 'held-cleanup':
            self.cleanup_calls += 1
            self.held = False
            self.empty = True
            self.status = CLEAN
            self.history += timestamp(REMOVED + CONFIG + PME_RESTORED + TLS_RESTORED + RESET + POWER + FINISHED, 70)
            text = 'N71_PCIE_HELD held=0\n' + CLEAN + self.history
        elif stage == 'held-pcie-unload':
            self.pcie = False
            text = 'N71_PCIE_UNLOADED\n' + self.history
        elif stage == 'held-restore':
            self.active = False
            text = REG_CLEAN + self.history
        elif stage == 'held-reg-unload':
            self.reg = False
            self.history += timestamp('N71_REG_ON_REMOVE error=0 restore_pending=0; parent retained\n', 100)
            text = 'N71_REG_UNLOADED\n' + self.history
        else:
            text = ''
        if stage in self.overrides:
            changed = self.overrides[stage]
            if callable(changed):
                code, text = changed(self, session, text)
            else:
                code, text = changed
        path = session.output / (stage + '-private.log')
        with path.open('x') as stream:
            stream.write(text + '\nSTDERR\n')
        path.chmod(0o600)
        return SimpleNamespace(returncode=code, stdout=session.history.fresh(text) if session.history else text)


class HeldSessionTests(unittest.TestCase):
    def setUp(self):
        root_patch = patch.object(LINK_SESSION, 'ROOT', ROOT)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / 'runtime').mkdir(mode=0o700)
        self.phone = Phone()
        self.modules = [({'module': name, 'sha256': hashlib.sha256(name.encode()).hexdigest()}, name.encode())
                        for name in HELD.MODULES]
        self.identity = {'deployment_sha256': 'a' * 64, 'payload_sha256': 'b' * 64, 'initramfs_sha256': 'c' * 64,
                         'modules': {record['module']: record['sha256'] for record, _ in self.modules}}

    def execute(self, name, source=None, identity=None):
        output = self.root / 'runtime' / name
        output.mkdir(mode=0o700)
        with patch.object(LINK_SESSION.device_profile, 'ssh_options', return_value=[]):
            session = LINK_SESSION.Session(output, self.modules, host_scan=True, scan_link_target=True,
                                           scan_pme_disable=True, scan_hold=True, release=LINK_SESSION.BINDING_RELEASE)
        session.capture = lambda *args, **kwargs: self.phone.capture(session, *args, **kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            code = HELD.run(session, identity or self.identity, root=self.root, source=source)
        return code, session, output

    def test_acquire_then_release_preserves_owners_until_explicit_same_boot_cleanup(self):
        # Mutations killed: remove hold parameter, durable attempt write or held parser dispatch.
        code, session, output = self.execute('acquire')
        self.assertEqual(code, 0)
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active and self.phone.held)
        self.assertFalse(session.result['cleanup_verified'])
        self.assertTrue(session.result['held_verified'])
        self.assertIn('scan_hold=1', dict(self.phone.calls)['pcie'])
        self.assertEqual(json.loads((output / 'held-state-private.json').read_text())['identity'], self.identity)
        self.assertEqual((output / 'held-state-private.json').stat().st_mode & 0o777, 0o600)
        code, released, final = self.execute('release', output)
        self.assertEqual(code, 0)
        self.assertFalse(self.phone.pcie or self.phone.reg or self.phone.active or self.phone.held)
        self.assertTrue(released.result['cleanup_verified'])
        self.assertEqual(self.phone.cleanup_calls, 1)
        self.assertEqual(sum(stage == 'pcie' for stage, _ in self.phone.calls), 1)
        self.assertEqual(released.result['boot_id'], BOOT)
        self.assertIn('reg-unload', json.loads((final / 'held-state-private.json').read_text())['proofs'])

    def test_invalid_acquisition_is_cleaned_without_reporting_positive_hold(self):
        # Mutation killed: preserve positive held state after the acquisition getter failed.
        self.phone.overrides['pcie'] = lambda phone, session, text: (0, text.replace('held=1', 'held=0', 1))
        code, session, _ = self.execute('bad-acquire')
        self.assertEqual(code, 1)
        self.assertFalse(self.phone.pcie or self.phone.reg or self.phone.active)
        self.assertTrue(session.result['cleanup_verified'])
        self.assertFalse(session.result.get('held_verified', False))

    def test_pending_config_retry_keeps_reg_on_and_never_rescans(self):
        # Mutation killed: release REG_ON after failed PCI cleanup or rescan on retry.
        _, _, output = self.execute('acquire')
        def pending(phone, session, text):
            phone.status = ACTIVE.replace('cleanup_error=0', 'cleanup_error=-5')
            phone.history = phone.history[:phone.history.index('[ 70.000000]')]
            phone.history += timestamp(REMOVED + CONFIG.replace('error=0', 'error=-5') +
                                       FINISHED.replace('error=0 retained=0 scan_pending=0 reset_pending=0 powered=0 attached=0',
                                                        'error=-5 retained=1 scan_pending=1 reset_pending=1 powered=4 attached=4'), 70)
            return 1, 'N71_PCIE_HELD held=0\n' + phone.status + phone.history
        self.phone.overrides['held-cleanup'] = pending
        code, session, pending_output = self.execute('pending', output)
        self.assertEqual(code, 1)
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)
        self.assertFalse(session.result['cleanup_verified'])
        del self.phone.overrides['held-cleanup']
        def retry(phone, session, text):
            phone.history = phone.history[:phone.history.index('[ 70.000000]', phone.history.index('[ 70.000000]') + 1)] if phone.history.count('[ 70.000000]') > 1 else phone.history
            phone.history += timestamp(CONFIG + PME_RESTORED + TLS_RESTORED + RESET + POWER + FINISHED, 80)
            return 0, 'N71_PCIE_HELD held=0\n' + CLEAN + phone.history
        self.phone.overrides['held-cleanup'] = retry
        code, session, _ = self.execute('retry', pending_output)
        self.assertEqual(code, 0)
        self.assertTrue(session.result['cleanup_verified'])
        self.assertEqual(sum(stage == 'pcie' for stage, _ in self.phone.calls), 1)

    def test_verified_pci_cleanup_is_not_repeated_after_unload_failure(self):
        # Mutation killed: repeat action=cleanup after it already released the reset and power owners.
        _, _, output = self.execute('acquire')
        self.phone.overrides['held-pcie-unload'] = lambda phone, session, text: (setattr(phone, 'pcie', True) or 1, '')
        code, _, pending = self.execute('pending-unload', output)
        self.assertEqual(code, 1)
        self.assertTrue(self.phone.reg and self.phone.active)
        del self.phone.overrides['held-pcie-unload']
        code, session, _ = self.execute('resume-unload', pending)
        self.assertEqual(code, 0)
        self.assertEqual(self.phone.cleanup_calls, 1)
        self.assertTrue(session.result['cleanup_verified'])

    def test_reg_restore_retry_skips_completed_pci_removal(self):
        # Mutation killed: repeat PCI cleanup/unload when only REG_ON is pending.
        _, _, output = self.execute('acquire')
        self.phone.overrides['held-restore'] = lambda phone, session, text: (setattr(phone, 'active', True) or 1, REG_ACTIVE + phone.history)
        code, _, pending = self.execute('pending-reg', output)
        self.assertEqual(code, 1)
        self.assertFalse(self.phone.pcie)
        self.assertTrue(self.phone.reg and self.phone.active)
        del self.phone.overrides['held-restore']
        code, session, _ = self.execute('resume-reg', pending)
        self.assertEqual(code, 0)
        self.assertEqual(self.phone.cleanup_calls, 1)
        self.assertEqual(sum(stage == 'held-pcie-unload' for stage, _ in self.phone.calls), 1)
        self.assertTrue(session.result['cleanup_verified'])

    def test_wrong_profile_boot_or_history_refuses_before_cleanup(self):
        # Mutations killed: ignore selected profile, live boot or exact diagnostic history.
        _, _, output = self.execute('acquire')
        for name, kind in (('profile', 'profile'), ('boot', 'boot'), ('history', 'history')):
            with self.subTest(kind=kind):
                before = len(self.phone.calls)
                identity = dict(self.identity, deployment_sha256='d' * 64) if kind == 'profile' else self.identity
                if kind == 'boot':
                    self.phone.boot = '22345678-1234-1234-1234-123456789abc'
                if kind == 'history':
                    self.phone.history += timestamp('N71_PCIE_FOREIGN diagnostic\n', 150)
                code, session, _ = self.execute(name, output, identity)
                self.assertEqual(code, 1)
                self.assertIn('held_error', session.result)
                self.assertTrue(all('printf "cleanup' not in command and 'rmmod' not in command
                                    for _, command in self.phone.calls[before:]))
                self.assertTrue(self.phone.reg and self.phone.pcie and self.phone.active)
                self.phone.boot = BOOT
                self.phone.history = self.phone.history.replace(timestamp('N71_PCIE_FOREIGN diagnostic\n', 150), '')

    def test_live_parameters_hash_and_reg_control_are_not_trusted_from_the_journal(self):
        # Mutations killed: omit live immutable parameters, module hashes or REG_ON comparisons.
        _, _, output = self.execute('acquire')
        for index, (before, after) in enumerate((('scan_hold=Y', 'scan_hold=N'), ('dart_cycle=N', 'dart_cycle=Y'),
                                                (self.modules[0][0]['sha256'], '0' * 64),
                                                ('value=81', 'value=82'), ('powered=4', 'powered=3'))):
            self.phone.overrides['held-resume-live'] = lambda phone, session, text, b=before, a=after: (0, text.replace(b, a, 1))
            code, session, _ = self.execute('live-bad-' + str(index), output)
            self.assertEqual(code, 1)
            self.assertIn('held_error', session.result)
            self.assertEqual(self.phone.cleanup_calls, 0)
        self.assertTrue(self.phone.reg and self.phone.pcie)

    def test_cleanup_requires_complete_restore_proof_before_unload_or_reg_release(self):
        # Mutations killed: skip the held cleanup parser or accept a nonzero cleanup exit.
        _, _, output = self.execute('acquire')
        self.phone.overrides['held-cleanup'] = lambda phone, session, text: (0, text.replace('N71_PCIE_SCAN_CONFIG_RESTORED error=0', 'INCOMPLETE_RESTORE error=0'))
        code, session, _ = self.execute('bad-cleanup', output)
        self.assertEqual(code, 1)
        self.assertFalse(session.result['cleanup_verified'])
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)
        self.assertFalse(any(stage in ('held-pcie-unload', 'held-restore') for stage, _ in self.phone.calls))

    def test_prior_cleanup_proof_integrity_is_required_even_after_unload(self):
        # Mutation killed: trust absent modules without validating the saved cleanup proof.
        _, _, output = self.execute('acquire')
        _, _, released = self.execute('release', output)
        proof = released / 'pcie-cleanup-proof-private.log'
        proof.write_text(proof.read_text() + 'changed\n')
        code, session, _ = self.execute('changed-proof', released)
        self.assertEqual(code, 1)
        self.assertFalse(session.result['cleanup_verified'])

    def test_private_checkpoint_and_proofs_reject_tampering_and_links(self):
        # Mutations killed: skip checkpoint integrity, private mode or canonical private path guards.
        _, _, output = self.execute('acquire')
        state_path = output / 'held-state-private.json'
        original = state_path.read_text()
        data = json.loads(original)
        outside = self.root / 'runtime/outside'
        checkpoint = output / data['checkpoint']['name']
        outside.write_bytes(checkpoint.read_bytes())
        outside.chmod(0o600)
        alternate = output / 'alternate-private.log'
        alternate.write_bytes(checkpoint.read_bytes())
        alternate.chmod(0o600)
        for index, altered in enumerate((dict(data, format=True), dict(data, module_directory='/run/../../tmp'),
                                         dict(data, module_directory=1), dict(data, result=dict(data['result'], boot_id=1)),
                                         dict(data, pcie_attempted=1),
                                         dict(data, checkpoint={'name': '../outside', 'sha256': data['checkpoint']['sha256']}),
                                         dict(data, checkpoint={'name': alternate.name, 'sha256': data['checkpoint']['sha256']}),
                                         dict(data, checkpoint=dict(data['checkpoint'], sha256='0' * 64)))):
            state_path.write_text(json.dumps(altered))
            code, _, _ = self.execute('tampered-' + str(index), output)
            self.assertEqual(code, 1)
        state_path.write_text(original)
        state_path.chmod(0o644)
        self.assertEqual(self.execute('public-state', output)[0], 1)
        state_path.chmod(0o600)
        link = self.root / 'runtime/link'
        link.symlink_to(output, target_is_directory=True)
        self.assertEqual(self.execute('symlink', link)[0], 1)
        self.assertEqual(self.phone.cleanup_calls, 0)

    def test_selected_build_and_mode_guards_are_explicit(self):
        # Mutations killed: omit held dispatch or any host/target/PME/power2 requirement.
        mode = dict(host_scan=True, scan_link_target=True, scan_pme_disable=True,
                    scan_hold=True, release=LINK_SESSION.BINDING_RELEASE)
        records = LINK_SESSION.selected_records(False, **mode)
        self.assertEqual(records[0]['bytes'], 76112)
        self.assertEqual(records[0]['sha256'], 'b7e51d4d8ee281ace121c11dc60af04265a63c7395613fa8503af590927520b3')
        for changed in ({'host_scan': False}, {'scan_link_target': False}, {'scan_pme_disable': False},
                        {'scan_pme_noop': True}, {'release': LINK_SESSION.RELEASE}, {'bar_sizing': True}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                LINK_SESSION.selected_records(False, **dict(mode, **changed))
        with patch.object(LINK_SESSION.device_profile, 'ssh_options', return_value=[]):
            for changed in ({'host_scan': False}, {'scan_link_target': False}, {'scan_pme_disable': False},
                            {'release': LINK_SESSION.RELEASE}):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    LINK_SESSION.Session(self.root / 'runtime', self.modules, **dict(mode, **changed))

    def test_resource_build_dispatch_and_exact_capability_scope(self):
        # Mutations killed: use the old build or admit an implicit/nonboolean resource capability.
        mode = dict(host_scan=True, scan_link_target=True, scan_pme_disable=True,
                    scan_hold=True, release=LINK_SESSION.BINDING_RELEASE, resource_capable=True)
        records = LINK_SESSION.selected_records(False, **mode)
        self.assertEqual(records[0]['bytes'], 84696)
        self.assertEqual(records[0]['sha256'], '2dcdebc2251b272246c4b6ae7ee58449ef2973ffe01d66fa5398392730a2f31d')
        self.assertEqual(records[1], LINK_SESSION.selected_records(False, **dict(mode, resource_capable=False))[1])
        invalid = ({'scan_hold': False}, {'host_scan': False}, {'scan_link_target': False},
                   {'scan_pme_disable': False}, {'release': LINK_SESSION.RELEASE},
                   {'resource_capable': 1}, {'resource_capable': None}, {'resource_capable': 'yes'})
        with patch.object(LINK_SESSION.device_profile, 'ssh_options', return_value=[]):
            selected = LINK_SESSION.Session(self.root / 'runtime', self.modules, **mode)
            self.assertIs(selected.resource_capable, True)
            self.assertIs(LINK_SESSION.Session(self.root / 'runtime', self.modules,
                          **dict(mode, resource_capable=False)).resource_capable, False)
            for changed in invalid:
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    LINK_SESSION.selected_records(False, **dict(mode, **changed))
                with self.subTest(session=changed), self.assertRaises(ValueError):
                    LINK_SESSION.Session(self.root / 'runtime', self.modules, **dict(mode, **changed))

    def resource_cli(self):
        records = []
        for index, name in enumerate(HELD.MODULES):
            raw = bytearray(128)
            raw[:7] = b'\x7fELF\x02\x01\x01'
            struct.pack_into('<HH', raw, 16, 1, 183)
            raw.extend(('vermagic=' + LINK_SESSION.BINDING_RELEASE + ' SMP preempt mod_unload aarch64\0').encode())
            raw.extend(('RESOURCE_FIXTURE_' + str(index)).encode())
            path = self.root / name
            path.write_bytes(raw)
            path.chmod(0o600)
            records.append({'module': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                            'vermagic': LINK_SESSION.BINDING_RELEASE + ' SMP preempt mod_unload aarch64'})
        folder = self.root / 'docs/evidence'
        folder.mkdir(parents=True)
        held = json.loads((ROOT / 'docs/evidence/n71-pci-held-caller.json').read_text())
        resource = json.loads((ROOT / 'docs/evidence/n71-pci-resource-assignment.json').read_text())
        held['kernel_build']['modules'].update({row['module']: {k: v for k, v in row.items() if k != 'module'}
                                               for row in records})
        held['kernel_build']['modules']['n71-pcie-diagnostic.ko']['sha256'] = '0' * 64
        resource['real_module_build']['modules'].update(
            {row['module']: {k: v for k, v in row.items() if k != 'module'} for row in records})
        for name, evidence in (('n71-pci-held-caller.json', held), ('n71-pci-resource-assignment.json', resource)):
            (folder / name).write_text(json.dumps(evidence))
        loader = b'FIXTURE_LOADER'.ljust(64, b'_')
        (folder / 'm1n1-rebuild.json').write_text(json.dumps({'shallow_clone': {
            'matches_original': True, 'bytes': len(loader), 'sha256': hashlib.sha256(loader).hexdigest()}}))
        payload = self.root / 'payload.bin'
        payload.write_bytes(loader + LINK_SESSION.ASPM_BOOTARGS + b'FIXTURE_PAYLOAD')
        payload.chmod(0o600)
        profile = {'payload': payload, 'sha256': hashlib.sha256(payload.read_bytes()).hexdigest(),
                   'initramfs_sha256': 'b' * 64}
        deployment = self.root / 'deployment.json'
        deployment.write_text('{}\n')
        deployment.chmod(0o600)
        metadata = {'kernel_patchset': 'n71-dart-serdev-power-v2', 'kernel_release': LINK_SESSION.BINDING_RELEASE,
                    'payload_sha256': profile['sha256'], 'module_sha256': records[0]['sha256'],
                    'pcie_scan_link_target': True, 'pcie_scan_pme_disable': True, 'pcie_scan_hold': True,
                    'pcie_aspm_off': True, 'pcie_resource_capable': True,
                    'bootargs_sha256': hashlib.sha256(LINK_SESSION.ASPM_BOOTARGS).hexdigest()}
        provenance = self.root / 'provenance.json'
        provenance.write_text(json.dumps(metadata))
        provenance.chmod(0o600)
        argv = ['n71-link-session.py', '--profile', str(deployment), '--host-scan', '--scan-link-target',
                '--scan-pme-disable', '--scan-hold', '--resource-capable', '--check']
        return profile, metadata, argv

    def test_resource_cli_check_rejects_provenance_and_modules_without_ssh(self):
        # Mutations killed: lose CLI capability dispatch or accept nonboolean/mismatched provenance.
        profile, metadata, argv = self.resource_cli()
        provenance = self.root / 'provenance.json'
        with patch.object(LINK_SESSION, 'ROOT', self.root), patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(LINK_SESSION.device_profile, 'verify', return_value=profile), \
                patch.object(LINK_SESSION.subprocess, 'run', side_effect=AssertionError('Unexpected SSH')):
            with patch.object(sys, 'argv', argv):
                try:
                    self.assertEqual(LINK_SESSION.main(), 0)
                except (ValueError, OSError, SystemExit) as error:
                    self.fail('Valid resource CLI check refused: ' + str(error))
            for value in (False, 1, None, 'true'):
                provenance.write_text(json.dumps(dict(metadata, pcie_resource_capable=value)))
                with patch.object(sys, 'argv', argv), self.assertRaises(ValueError):
                    LINK_SESSION.main()
            missing = dict(metadata)
            del missing['pcie_resource_capable']
            provenance.write_text(json.dumps(missing))
            with patch.object(sys, 'argv', argv), self.assertRaises(ValueError):
                LINK_SESSION.main()
            provenance.write_text(json.dumps(metadata))
            without_flag = [arg for arg in argv if arg != '--resource-capable']
            with patch.object(sys, 'argv', without_flag), self.assertRaises(ValueError):
                LINK_SESSION.main()
            module = self.root / HELD.MODULES[0]
            module.write_bytes(module.read_bytes() + b'CHANGED')
            with patch.object(sys, 'argv', argv), self.assertRaisesRegex(ValueError, 'Module size differs'):
                LINK_SESSION.main()

    def test_resource_cli_forwards_capability_to_acquisition_and_resume_check(self):
        # Mutations killed: omit capability from either Session constructor used by the held CLI.
        profile, _, argv = self.resource_cli()
        def coordinator(session, *args, **kwargs):
            self.assertIs(session.resource_capable, True)
            self.assertEqual(session.modules[0][0]['sha256'],
                             hashlib.sha256((self.root / HELD.MODULES[0]).read_bytes()).hexdigest())
            return 0
        def invoke(arguments):
            with patch.object(sys, 'argv', arguments):
                try:
                    return LINK_SESSION.main()
                except (ValueError, OSError, SystemExit) as error:
                    self.fail('Valid resource CLI dispatch refused: ' + str(error))
        with patch.object(LINK_SESSION, 'ROOT', self.root), patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(LINK_SESSION.device_profile, 'verify', return_value=profile), \
                patch.object(LINK_SESSION.device_profile, 'ssh_options', return_value=[]), \
                patch.object(LINK_SESSION.n71_held_session, 'run', side_effect=coordinator), \
                patch.object(LINK_SESSION.n71_held_session, 'load_source', side_effect=coordinator), \
                patch.object(LINK_SESSION.subprocess, 'run', side_effect=AssertionError('Unexpected SSH')):
            acquire = [arg for arg in argv if arg != '--check'] + ['--output-dir', str(self.root / 'runtime/acquire')]
            self.assertEqual(invoke(acquire), 0)
            resume = argv + ['--release-held', str(self.root / 'runtime/source')]
            self.assertEqual(invoke(resume), 0)

    def test_cleanup_keeps_negative_stop_error_even_after_all_owners_are_released(self):
        # Mutation killed: convert a denied PCI stop write into a successful operation.
        _, _, output = self.execute('acquire')
        def refused(phone, session, text):
            refusal = ('N71_PCIE_SCAN_WRITE_REFUSED bus=1 devfn=00 where=004 size=2 value=00000000 error=-1\n')
            phone.history = phone.history.replace('[ 70.000000] N71_PCIE_SCAN_BUS_REMOVED bus-null=1 stop-error=0\n',
                                                  timestamp(refusal, 69) + '[ 70.000000] N71_PCIE_SCAN_BUS_REMOVED bus-null=1 stop-error=-1\n')
            return 0, 'N71_PCIE_HELD held=0\n' + CLEAN + phone.history
        self.phone.overrides['held-cleanup'] = refused
        code, session, _ = self.execute('release', output)
        self.assertEqual(code, 1)
        self.assertTrue(session.result['cleanup_verified'])
        self.assertEqual(session.result['stop_error'], -1)
        self.assertFalse(self.phone.pcie or self.phone.reg or self.phone.active)

    def test_missing_live_checkpoint_does_not_authorize_a_release(self):
        # Mutation killed: resume a crashed acquisition from its attempt flags alone.
        _, _, output = self.execute('acquire')
        path = output / 'held-state-private.json'
        data = json.loads(path.read_text())
        data['checkpoint'] = None
        path.write_text(json.dumps(data))
        code, _, _ = self.execute('release', output)
        self.assertEqual(code, 1)
        self.assertEqual(self.phone.cleanup_calls, 0)
        self.assertTrue(self.phone.pcie and self.phone.reg)

    def test_completed_release_can_be_checked_again_without_repeating_effects(self):
        # Mutation killed: repeat restore/unload after complete cleanup.
        _, _, output = self.execute('acquire')
        _, _, released = self.execute('release', output)
        before = len(self.phone.calls)
        code, session, _ = self.execute('repeat-release', released)
        self.assertEqual(code, 0)
        self.assertTrue(session.result['cleanup_verified'])
        self.assertTrue(all('rmmod' not in command and 'printf "0' not in command
                            and 'printf "cleanup' not in command for _, command in self.phone.calls[before:]))

    def test_snapshot_command_executes_real_shell_and_reads_sysfs_bool_format(self):
        # Mutations killed: omit bind suppression or report immutable parameters without reading them.
        sysfs = self.root / 'sys'
        proc = self.root / 'proc'
        proc.joinpath('sys/kernel/random').mkdir(parents=True)
        proc.joinpath('sys/kernel/random/boot_id').write_text(BOOT + '\n')
        proc.joinpath('cmdline').write_text('rdinit=/init pcie_aspm=off\n')
        sysfs.joinpath('bus/pci/devices/0001:01:00.0').mkdir(parents=True)
        pcie = sysfs / 'module/n71_pcie_diagnostic/parameters'
        reg = sysfs / 'module/n71_wlan_power_diagnostic/parameters'
        pcie.mkdir(parents=True)
        reg.mkdir(parents=True)
        for name in HELD.TRUE_PARAMETERS + HELD.FALSE_PARAMETERS:
            (pcie / name).write_text(('Y' if name in HELD.TRUE_PARAMETERS else 'N') + '\n')
        (pcie / 'held').write_text('held=1\n')
        (pcie / 'status').write_text(ACTIVE.removeprefix('N71_PCIE_STATUS '))
        (reg / 'state').write_text(LINK_SESSION.STATE_ACTIVE + '\n')
        (reg / 'control').write_text('N71_REG_ON_CONTROL_READBACK value=81\n')
        staged = self.root / 'staged'
        staged.mkdir()
        for record, raw in self.modules:
            (staged / record['module']).write_bytes(raw)
        tools = self.root / 'bin'
        tools.mkdir()
        programs = {'uname': '#!/bin/sh\nprintf "%s\\n" ' + shlex.quote(LINK_SESSION.BINDING_RELEASE) + '\n',
                    'dmesg': '#!/bin/sh\nprintf "%s\\n" "PCIe ASPM is disabled"\n',
                    'sha256sum': '#!' + sys.executable + '\nimport hashlib, sys\nfrom pathlib import Path\n'
                                 'for name in sys.argv[1:]:\n print(hashlib.sha256(Path(name).read_bytes()).hexdigest() + "  " + name)\n'}
        for name, text in programs.items():
            path = tools / name
            path.write_text(text)
            path.chmod(0o700)
        session = SimpleNamespace(module_directory='/run/n71-link-' + 'a' * 24, release=LINK_SESSION.BINDING_RELEASE,
                                  result={'boot_id': BOOT}, modules=self.modules)
        command = re.sub(r'/(sys|proc)/', lambda match: str(self.root / match[1]) + '/', HELD.snapshot_command(session))
        command = command.replace(session.module_directory, str(staged))
        environment = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ['PATH'])
        result = subprocess.run(['bash', '-c', command], env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('N71_HELD_PARAM scan_hold=Y\n', result.stdout)
        self.assertIn('N71_HELD_PARAM dart_cycle=N\n', result.stdout)
        self.assertIn('N71_HELD_PCI_EMPTY=0\n', result.stdout)
        bind = sysfs / 'bus/platform/drivers/n71-pcie-diagnostic/bind'
        bind.parent.mkdir(parents=True)
        bind.touch()
        result = subprocess.run(['bash', '-c', command], env=environment, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        bind.unlink()
        sysfs.joinpath('bus/pci/devices').rename(sysfs / 'bus/pci/unavailable')
        result = subprocess.run(['bash', '-c', command], env=environment, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'N71_HELD_PCI_EMPTY=1', result.stdout)

    def test_cli_held_profile_boolean_and_release_scope_are_exact(self):
        # Mutations killed: ignore held provenance or release through a non-held candidate.
        profile_path = self.root / 'deployment.json'
        profile_path.write_text('{}\n')
        profile_path.chmod(0o600)
        records = []
        for name in HELD.MODULES:
            raw = bytearray(128)
            raw[:7] = b'\x7fELF\x02\x01\x01'
            struct.pack_into('<HH', raw, 16, 1, 183)
            raw.extend(('vermagic=' + LINK_SESSION.BINDING_RELEASE + ' SMP preempt mod_unload aarch64\0').encode())
            path = self.root / name
            path.write_bytes(raw)
            path.chmod(0o600)
            records.append({'module': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                            'vermagic': LINK_SESSION.BINDING_RELEASE + ' SMP preempt mod_unload aarch64'})
        legacy = json.loads((ROOT / 'docs/evidence/n71-pcie-pme-aspm-build.json').read_text())
        legacy['selected_modules'] = {row['module']: row for row in records}
        legacy_path = self.root / 'docs/evidence/n71-pcie-pme-aspm-build.json'
        legacy_path.parent.mkdir(parents=True)
        legacy_path.write_text(json.dumps(legacy))
        metadata = {'kernel_patchset': 'n71-dart-serdev-power-v2', 'kernel_release': LINK_SESSION.BINDING_RELEASE,
                    'payload_sha256': 'a' * 64, 'module_sha256': records[0]['sha256'],
                    'pcie_scan_link_target': True, 'pcie_scan_pme_disable': True,
                    'pcie_scan_hold': True, 'pcie_aspm_off': True}
        provenance = self.root / 'provenance.json'
        provenance.write_text(json.dumps(metadata))
        provenance.chmod(0o600)
        profile = {'payload': self.root / 'payload.bin', 'sha256': 'a' * 64, 'initramfs_sha256': 'b' * 64}
        argv = ['n71-link-session.py', '--profile', str(profile_path), '--host-scan', '--scan-link-target',
                '--scan-pme-disable', '--scan-hold', '--check']
        with patch.object(LINK_SESSION, 'ROOT', self.root), patch.dict(os.environ), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(LINK_SESSION.device_profile, 'verify', return_value=profile), \
                patch.object(LINK_SESSION, 'aspm_payload'), \
                patch.object(LINK_SESSION.n71_scan_held_result, 'selected_records', return_value=records), \
                patch.object(LINK_SESSION.subprocess, 'run', side_effect=AssertionError('Unexpected SSH')):
            with patch.object(sys, 'argv', argv):
                self.assertEqual(LINK_SESSION.main(), 0)
            for value in (False, 1, None):
                provenance.write_text(json.dumps(dict(metadata, pcie_scan_hold=value)))
                with patch.object(sys, 'argv', argv), self.assertRaises(ValueError):
                    LINK_SESSION.main()
            with patch.object(sys, 'argv', ['n71-link-session.py', '--profile', str(profile_path),
                                           '--release-held', str(self.root / 'runtime/source'), '--check']), \
                    self.assertRaisesRegex(ValueError, 'Held release requires held mode'):
                LINK_SESSION.main()

    def test_completed_reg_restore_is_not_written_again_after_unload_failure(self):
        # Mutation killed: write REG_ON power again or duplicate its proof before retrying unload.
        _, _, output = self.execute('acquire')
        self.phone.overrides['held-reg-unload'] = lambda phone, session, text: (setattr(phone, 'reg', True) or 1, '')
        code, _, pending = self.execute('pending-reg-unload', output)
        self.assertEqual(code, 1)
        self.assertFalse(self.phone.active or self.phone.pcie)
        self.assertTrue(self.phone.reg)
        del self.phone.overrides['held-reg-unload']
        before = len(self.phone.calls)
        code, session, _ = self.execute('resume-reg-unload', pending)
        self.assertEqual(code, 0)
        self.assertTrue(session.result['cleanup_verified'])
        self.assertTrue(all('printf "0' not in command and 'printf "cleanup' not in command
                            for _, command in self.phone.calls[before:]))

    @unittest.skipIf(os.environ.get('N71_HELD_MUTATION_CHILD') == '1', 'Mutation child runs behavioral tests only')
    def test_mutations_fail_behavioral_assertions(self):
        variants = {
            'held-profile-identity': ("data.get('identity') == selected_identity", 'True'),
            'held-boot': ("boot == session.result['boot_id']", 'True'),
            'held-checkpoint-hash': ("hashlib.sha256(checkpoint.read_bytes()).hexdigest() == record['sha256']", 'True'),
            'held-proof-hash': ("hashlib.sha256(path.read_bytes()).hexdigest() == expected", 'True'),
            'held-history': ('n71_held_history.verify(live, prior, reg_present=presence[1])', 'pass'),
            'held-private-mode': ('device_profile.protected(directory, directory=True)', 'pass'),
            'held-sysfs-parameters': ("value == ('Y' if name in TRUE_PARAMETERS else 'N')", 'True'),
            'held-staged-hash': ("re.findall(r'^([0-9a-f]{64})  ' + re.escape(target) + r'$', raw, re.M) == [record['sha256']]", 'True'),
            'held-live-owner': ('n71_scan_target_result.live_status(live) == n71_scan_target_result.live_status(prior)', 'True'),
            'held-cleanup-parser': ('cleanup = n71_scan_held_result.cleanup(proof)', "cleanup = {'stop_error': 0}"),
            'held-stop-error': ("session.result['stop_error'] = cleanup['stop_error']", "session.result['stop_error'] = 0"),
            'held-stop-exit': ("and session.result.get('stop_error', 0) == 0", ''),
            'held-bind-suppression': ('test ! -e /sys/bus/platform/drivers/n71-pcie-diagnostic/bind; ', ''),
            'held-pci-directory': ("'test -d /sys/bus/pci/devices; '", "''"),
            'held-reg-repeat-write': ("session.activation_attempted and 'restore' not in journal.proofs", 'session.activation_attempted'),
            'held-checkpoint-name': ("re.fullmatch(r'held-checkpoint-[0-9a-f]{12}-private\\.log', record['name'])", 'True'),
        }
        link_variants = {
            'held-caller-parameter': ("parameters += ' scan_hold=1'", "parameters += ''"),
            'held-caller-parser': ('self.scan_parser = n71_scan_held_result', 'self.scan_parser = n71_scan_pme_result'),
            'held-build-selection': ('return n71_scan_held_result.selected_records(ROOT, release=release)',
                                     'return selected_records(config_inventory, host_scan, release=release, scan_link_target=scan_link_target, scan_pme_disable=scan_pme_disable)'),
            'held-provenance': ("metadata.get('pcie_scan_hold', False) is options.scan_hold", 'True'),
            'held-release-scope': ('options.scan_hold and options.previous_clean is None', 'True'),
            'held-journal-before-effect': ('session.before_effect = journal.save', 'session.before_effect = lambda: None'),
            'resource-build-selection': ('return n71_resource_result.selected_records(ROOT, release=release)',
                                         'return n71_scan_held_result.selected_records(ROOT, release=release)'),
            'resource-selection-scope': ("type(resource_capable) is bool and (not resource_capable or scan_hold),\n            'Resource capability", "True,\n            'Resource capability"),
            'resource-session-scope': ("type(resource_capable) is bool and (not resource_capable or scan_hold),\n                'Resource session", "True,\n                'Resource session"),
            'resource-session-selection': ('self.resource_capable = resource_capable', 'self.resource_capable = False'),
            'resource-provenance': ("metadata.get('pcie_resource_capable', False) is options.resource_capable", 'True'),
            'resource-cli-selection': ('resource_capable=options.resource_capable,\n                               resource_module_sha256=',
                                       'resource_capable=False,\n                               resource_module_sha256='),
            'resource-cli-check-session': ('resource_capable=options.resource_capable)\n            n71_held_session.load_source',
                                           'resource_capable=False)\n            n71_held_session.load_source'),
            'resource-cli-live-session': ('resource_capable=options.resource_capable)\n        return n71_held_session.run',
                                          'resource_capable=False)\n        return n71_held_session.run'),
        }
        # The journal hook lives in the coordinator, not the link collector.
        variants['held-journal-before-effect'] = link_variants.pop('held-journal-before-effect')
        with tempfile.TemporaryDirectory(prefix='n71-held-mutations-') as folder:
            for source, variable, changes in ((ROOT / 'scripts/host/n71_held_session.py', 'N71_HELD_SESSION_SCRIPT', variants),
                                              (ROOT / 'scripts/host/n71-link-session.py', 'N71_HELD_LINK_SCRIPT', link_variants)):
                text = source.read_text()
                for name, (before, after) in changes.items():
                    self.assertEqual(text.count(before), 1, name)
                    path = Path(folder) / (name + '.py')
                    path.write_text(text.replace(before, after))
                    compile(path.read_text(), str(path), 'exec')
                    environment = dict(os.environ, N71_HELD_MUTATION_CHILD='1', PYTHONDONTWRITEBYTECODE='1')
                    environment[variable] = str(path)
                    process = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                                              '-p', 'test_n71_held_session.py'], env=environment, capture_output=True, text=True, timeout=30)
                    output = process.stdout + process.stderr
                    self.assertNotEqual(process.returncode, 0, name)
                    self.assertIn('AssertionError', output, name)
                    self.assertNotIn('ERROR:', output, name + '\n' + output)
                    print('N71_HELD_SESSION_MUTATION_KILLED', name, flush=True)


if __name__ == '__main__':
    unittest.main()
