"""Real PMD Session construction and POSIX action files; no hardware effects."""
import copy
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_n71_pmd_runtime_profile as fixture

ROOT = fixture.ROOT
LINK_SOURCE = ROOT / 'scripts/host/n71-link-session.py'
RESOURCE_SOURCE = ROOT / 'scripts/host/n71_resource_stage.py'
NATIVE_SOURCE = ROOT / 'scripts/host/n71_driver_runtime_stage.py'


def load(name, source, variable):
    spec = importlib.util.spec_from_file_location(name, Path(os.environ.get(variable, source)))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


LINK = load('pmd_link_entry', LINK_SOURCE, 'N71_PMD_LINK_ENTRY_SCRIPT')
RESOURCE = load('pmd_resource_entry', RESOURCE_SOURCE, 'N71_PMD_RESOURCE_ENTRY_SCRIPT')
NATIVE = load('pmd_native_entry', NATIVE_SOURCE, 'N71_PMD_NATIVE_ENTRY_SCRIPT')
RELEASE = fixture.RELEASE
BOOT = '12345678-1234-1234-1234-123456789abc'


class PmdSessionEntry(unittest.TestCase):
    def setUp(self):
        case = fixture.PmdRuntimeProfile('test_real_compiled_selection_binds_caller_reg_on_wcc_and_kernel')
        case.setUp(); self.addCleanup(case.doCleanups)
        self.root = case.root; self.modules = case.modules; self.drivers = case.drivers
        legacy = 'docs/evidence/kernel-n71-bundle-build.json'
        (self.root / legacy).write_bytes((ROOT / legacy).read_bytes())
        self.output = self.root / 'new-output'
        for hook in (patch.object(LINK, 'ROOT', self.root),
                     patch.object(LINK.device_profile, 'ssh_options', return_value=[])):
            hook.start(); self.addCleanup(hook.stop)

    def accepted(self, function, *args, **kwargs):
        try: return function(*args, **kwargs)
        except (ValueError, KeyError, OSError) as error: self.fail('Qualified PMD entry refused: ' + str(error))

    def session(self, **changes):
        settings = dict(host_scan=True, scan_link_target=True, scan_pme_disable=True, scan_hold=True,
                        resource_capable=True, iommu_parent=True, release=RELEASE, runtime=self.drivers)
        settings.update(changes)
        session = LINK.Session(self.output, self.modules, **settings)
        session.result['boot_id'] = BOOT
        return session

    def test_real_constructor_keeps_two_diagnostics_and_five_owned_drivers(self):
        # Mutation killed: reject the complete explicit PMD constructor scope.
        original = copy.deepcopy(self.modules + self.drivers)
        session = self.accepted(self.session)
        self.assertEqual(session.release, RELEASE)
        self.assertEqual(session.result['kernel_release'], RELEASE)
        self.assertIs(session.driver_runtime, True)
        self.assertEqual(len(session.modules), 2); self.assertEqual(len(session.driver_module_data), 5)
        self.assertEqual(session.modules + session.driver_module_data, original)
        self.assertFalse(self.output.exists())

    def test_partial_modes_and_mutable_or_changed_bytes_refuse_without_output(self):
        # Mutation killed: remove the complete PMD scope guard (including exact booleans).
        for changes in ({'runtime': None}, {'host_scan': 1}, {'scan_hold': False}, {'iommu_parent': False},
                        {'resource_capable': 1}, {'scan_pme_disable': False}, {'release': 'unknown'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.session(**changes)
            self.assertFalse(self.output.exists())
        for data in (bytearray(self.drivers[0][1]), self.drivers[0][1][:-1]):
            pairs = list(self.drivers); pairs[0] = (pairs[0][0], data)
            with self.assertRaises(ValueError): self.session(runtime=pairs)
        self.assertFalse(self.output.exists())

    def test_provenance_and_real_elf_reader_select_pmd_without_legacy_crossing(self):
        # Mutation killed: remove the PMD profile mapping while retaining legacy defaults.
        metadata = {'kernel_patchset': 'n71-dart-serdev-pmd-v1', 'kernel_release': RELEASE, 'payload_sha256': 'a' * 64}
        self.assertEqual(self.accepted(LINK.selected_release, metadata, 'a' * 64), RELEASE)
        self.assertEqual(LINK.RELEASE, '7.2.0-iphone6s-dart-serdev1')
        for changed in (dict(metadata, kernel_release=LINK.BINDING_RELEASE), dict(metadata, payload_sha256='f' * 64)):
            with self.assertRaises(ValueError): LINK.selected_release(changed, 'a' * 64)
        folder = self.root / 'module-inputs'; folder.mkdir(mode=0o700)
        for record, raw in self.modules + self.drivers:
            path = folder / record['module']; path.write_bytes(raw); path.chmod(0o600)
            self.assertEqual(self.accepted(LINK.module_bytes, folder, record, release=RELEASE), raw)
            with self.assertRaises(ValueError): LINK.module_bytes(folder, record, release=LINK.BINDING_RELEASE)

    def test_old_diagnostic_selector_cannot_silently_select_pmd(self):
        # Mutation killed: permit PMD to fall through to the old diagnostic default records.
        with self.assertRaises(ValueError): LINK.selected_records(False, release=RELEASE)

    def test_action_generators_require_known_abi_boot_and_complete_pmd_mode(self):
        # Mutations killed: remove either command's PMD ownership/mode requirement.
        for name in ('scan_hold', 'iommu_parent'):
            session = self.accepted(self.session); setattr(session, name, False)
            with self.subTest(name=name), self.assertRaises(ValueError): RESOURCE.command(session)
            with self.assertRaises(ValueError): NATIVE.command(session, 'prepare')
        session = self.accepted(self.session); session.driver_runtime = False
        with self.assertRaises(ValueError): RESOURCE.command(session)
        with self.assertRaises(ValueError): NATIVE.command(session, 'prepare')
        for release, boot in [('unknown', BOOT), (RELEASE, 'not-a-boot')]:
            session = self.accepted(self.session); session.release = release; session.result['boot_id'] = boot
            with self.assertRaises(ValueError): RESOURCE.command(session)
            with self.assertRaises(ValueError): NATIVE.command(session, 'prepare')

    def execute(self, command, *, release=RELEASE, boot=BOOT):
        # Only regular files below this test root stand in for kernel parameters.
        for name in set(re.findall(r'/sys/[A-Za-z0-9_/@.:-]+', command)):
            path = self.root / name.lstrip('/'); path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists(): path.write_text('0\n')
        control = self.root / NATIVE.result.PCIE.lstrip('/')
        control.mkdir(parents=True, exist_ok=True)
        for name, value in {'held': 'held=1', 'driver_runtime': 'Y',
                            'resources': ' '.join(n+'='+str(RESOURCE.INITIAL[n]) for n in RESOURCE.n71_resource_result.FIELDS)}.items():
            (control / name).write_text(value + '\n')
        reg = self.root / RESOURCE.REG.lstrip('/'); reg.mkdir(parents=True, exist_ok=True)
        (reg / 'state').write_text('bound=1 active=1 restore_pending=1 original=80\n')
        (reg / 'control').write_text('N71_REG_ON_CONTROL_READBACK value=81\n')
        proc = self.root / 'proc/sys/kernel/random/boot_id'; proc.parent.mkdir(parents=True, exist_ok=True)
        proc.write_text(boot + '\n')
        action = control / 'action'; action.write_bytes(b'untouched\n')
        script = re.sub(r'/(sys|proc)/', lambda match: str(self.root / match[1])+'/', command)
        script = script.replace('uname -r', 'printf %s ' + shlex.quote(release)).replace('dmesg', 'true')
        process = subprocess.run(['sh', '-c', script], capture_output=True, text=True, timeout=8)
        return process, action.read_bytes()

    def test_posix_assignment_and_driver_actions_write_only_after_live_abi_and_boot(self):
        # Mutations killed: omit live uname checks before either action-file write.
        session = self.accepted(self.session)
        commands = [('assign', self.accepted(RESOURCE.command, session))]
        commands += [('driver-' + action, self.accepted(NATIVE.command, session, action)) for action in NATIVE.ACTIONS]
        for value, command in commands:
            process, data = self.execute(command)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(data, (value + '\n').encode())
            for release, boot in [(LINK.BINDING_RELEASE, BOOT), (RELEASE, '87654321-1234-1234-1234-123456789abc')]:
                process, data = self.execute(command, release=release, boot=boot)
                self.assertNotEqual(process.returncode, 0)
                self.assertEqual(data, b'untouched\n')


@unittest.skipIf(any(os.environ.get(name) for name in ('N71_PMD_LINK_ENTRY_SCRIPT',
                'N71_PMD_RESOURCE_ENTRY_SCRIPT', 'N71_PMD_NATIVE_ENTRY_SCRIPT')), 'Mutation child selects subject')
class PmdEntryMutations(unittest.TestCase):
    def test_weakened_entry_scope_or_remote_abi_checks_fail_by_assertion(self):
        variants = [
            ('profile', LINK_SOURCE, 'N71_PMD_LINK_ENTRY_SCRIPT', "'n71-dart-serdev-pmd-v1': n71_iommu_build.PMD_RELEASE", "'unrecorded-pmd': n71_iommu_build.PMD_RELEASE", 'provenance_and_real_elf_reader_select_pmd_without_legacy_crossing'),
            ('constructor', LINK_SOURCE, 'N71_PMD_LINK_ENTRY_SCRIPT', 'runtime is not None and all(value is True for value in\n                (host_scan, scan_link_target, scan_pme_disable, scan_hold, resource_capable, iommu_parent))', 'True', 'partial_modes_and_mutable_or_changed_bytes_refuse_without_output'),
            ('diagnostic', LINK_SOURCE, 'N71_PMD_LINK_ENTRY_SCRIPT', "require(release != n71_iommu_build.PMD_RELEASE, 'PMD requires explicit qualified driver runtime selection')", 'pass', 'old_diagnostic_selector_cannot_silently_select_pmd'),
            ('native-scope', NATIVE_SOURCE, 'N71_PMD_NATIVE_ENTRY_SCRIPT', "all(getattr(session, name, None) is True\n            for name in ('scan_hold', 'resource_capable', 'iommu_parent'))", 'True', 'action_generators_require_known_abi_boot_and_complete_pmd_mode'),
            ('resource-scope', RESOURCE_SOURCE, 'N71_PMD_RESOURCE_ENTRY_SCRIPT', "n71_driver_runtime_result.capable(session)\n            and all(getattr(session, name, None) is True for name in ('scan_hold', 'iommu_parent'))", 'True', 'action_generators_require_known_abi_boot_and_complete_pmd_mode'),
            ('native-remote', NATIVE_SOURCE, 'N71_PMD_NATIVE_ENTRY_SCRIPT', '''test "$(uname -r)" = "' + session.release + '"; ''', 'true; ', 'posix_assignment_and_driver_actions_write_only_after_live_abi_and_boot'),
            ('resource-remote', RESOURCE_SOURCE, 'N71_PMD_RESOURCE_ENTRY_SCRIPT', '''test "$(uname -r)" = "' + session.release + '"; ''', 'true; ', 'posix_assignment_and_driver_actions_write_only_after_live_abi_and_boot'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-pmd-entry-mutations-') as directory:
            for name, source, variable, before, after, method in variants:
                text = source.read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory)/(name+'.py'); path.write_text(body)
                environment = dict(os.environ, **{variable: str(path)}, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT/'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_n71_pmd_session_entry.PmdSessionEntry.test_'+method],
                                        env=environment, capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name+result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name+result.stderr)
                print('PMD_ENTRY_ASSERTION_KILL '+name, flush=True)


if __name__ == '__main__':
    unittest.main()
