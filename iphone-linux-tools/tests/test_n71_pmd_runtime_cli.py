"""PMD CLI uses real selectors/ELF/Session; identity, gzip and handlers are modeled."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_n71_pmd_runtime_profile as fixture

ROOT = fixture.ROOT
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_cli.py'
SPEC = importlib.util.spec_from_file_location('pmd_cli_under_test', Path(os.environ.get('N71_PMD_RUNTIME_CLI_SCRIPT', SOURCE)))
CLI = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(CLI)
CLI.__file__ = str(SOURCE)  # Mutation copies retain the real sibling-module location.
RELEASE = fixture.RELEASE


class PmdRuntimeCli(unittest.TestCase):
    def setUp(self):
        case = fixture.PmdRuntimeProfile('test_real_compiled_selection_binds_caller_reg_on_wcc_and_kernel')
        case.setUp(); self.addCleanup(case.doCleanups); self.root = case.root; self.selected = case.selected
        runtime = self.root / 'runtime'; runtime.mkdir(mode=0o700)
        self.folder = runtime / 'pmd-profile'; self.folder.mkdir(mode=0o700)
        for record, raw in case.modules + case.drivers: self.write(record['module'], raw)
        link = CLI.link_module(self.root); self.prefix = b'NONBOOTABLE_LOADER'.ljust(64, b'_') + link.ASPM_BOOTARGS
        self.write('initramfs.gz', b'NONBOOTABLE_INITRAMFS')
        self.write('payload.bin', self.prefix + b'NONBOOTABLE_DTB_KERNEL' + b'NONBOOTABLE_INITRAMFS')
        self.write('client_ed25519', b'synthetic identity adapter input')
        self.write('known_hosts', b'synthetic identity adapter input')
        digest = lambda name: hashlib.sha256((self.folder / name).read_bytes()).hexdigest()
        self.profile = self.folder / 'deployment.json'
        self.write('deployment.json', json.dumps({'format': 1, 'payload': 'payload.bin', 'initramfs': 'initramfs.gz',
            'client_key': 'client_ed25519', 'known_hosts': 'known_hosts', 'host_key_alias': 'synthetic-pmd',
            'sha256': digest('payload.bin'), 'initramfs_sha256': digest('initramfs.gz')}).encode())
        self.metadata = {'format': 1, **dict.fromkeys(CLI.TRUE_FLAGS, True), **dict.fromkeys(CLI.FALSE_FLAGS, False),
            'kernel_patchset': 'n71-dart-serdev-pmd-v1', 'kernel_release': RELEASE,
            'payload_sha256': digest('payload.bin'), 'bootargs_sha256': hashlib.sha256(link.ASPM_BOOTARGS).hexdigest(),
            'module_sha256': case.selected['diagnostics'][0]['sha256'],
            'reg_on_module_sha256': case.selected['diagnostics'][1]['sha256'], 'driver_modules': case.selected['drivers']}
        self.write('provenance.json', json.dumps(self.metadata).encode())
        (self.root / 'docs/evidence/m1n1-rebuild.json').write_text(json.dumps({'shallow_clone': {
            'matches_original': True, 'bytes': 64, 'sha256': hashlib.sha256(self.prefix[:64]).hexdigest()}}))
        self.source = runtime / 'saved-source'; self.source.mkdir(mode=0o700)
        self.serial = 0; self.identity_reads = 0
        for hook in (patch.object(CLI.device_profile, 'verify', self.identity),
                     patch.object(CLI.device_profile, 'ssh_options', return_value=[]),
                     patch.object(CLI.iommu, 'payload_image', self.kernel_adapter),
                     patch.object(CLI.held, 'run', self.held_handler),
                     patch.object(CLI.coordinator, 'run', self.runtime_handler),
                     patch.object(subprocess, 'run', side_effect=AssertionError('Unexpected process/network effect'))):
            hook.start(); self.addCleanup(hook.stop)

    def write(self, name, data):
        path = self.folder / name; path.write_bytes(data); path.chmod(0o600)

    def identity(self):
        self.identity_reads += 1
        profile = json.loads(self.profile.read_text())
        return {**profile, **{name: self.folder / profile[name] for name in ('payload', 'initramfs', 'client_key', 'known_hosts')}}

    def kernel_adapter(self, root, profile, metadata, *, prefix_bytes, release):
        self.assertEqual(root, self.root); self.assertEqual(release, RELEASE)
        self.assertEqual(prefix_bytes, len(self.prefix))
        self.assertEqual(metadata['payload_sha256'], profile['sha256'])

    def contract(self, session, action, kind):
        self.assertEqual(session.release, RELEASE)
        self.assertEqual(session.modules, [(r, (self.folder / r['module']).read_bytes()) for r in self.selected['diagnostics']])
        self.assertEqual(session.driver_modules, self.selected['drivers'])
        path = session.output / 'handler-contract-private.json'
        path.write_text(json.dumps({'action': action, 'kind': kind, 'release': session.release,
                                   'drivers': session.driver_modules}))
        return 0

    def held_handler(self, session, identity, *, root, source=None, assign=False):
        self.assertEqual(root, self.root)
        return self.contract(session, 'assign' if assign else 'acquire', 'held')

    def runtime_handler(self, session, request):
        self.contract(session, request['action'], 'runtime')
        return {'action': request['action'], 'phase': 'retained', 'primary_error': 0, 'successful': True}

    def request(self, action='acquire', check=True):
        self.serial += 1
        return {'action': action, 'check': check, 'profile': self.profile,
                'source': None if action == 'acquire' else self.source,
                'output': None if check else self.root / 'runtime' / ('output-' + str(self.serial))}

    def accepted(self, function, *args):
        try:
            with contextlib.redirect_stdout(io.StringIO()): return function(*args)
        except (ValueError, KeyError, OSError) as error: self.fail('Qualified PMD CLI refused: ' + str(error))

    def test_selection_and_local_check_keep_all_private_inputs_and_environment(self):
        # Mutations killed: remove PMD mapping or use the default ABI in either file reader.
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        metadata, selected = self.accepted(CLI.selection, self.root, self.profile)
        self.assertEqual(metadata, self.metadata); self.assertEqual(len(selected['drivers']), 5)
        self.assertEqual(CLI.RELEASE, fixture.wlan.RELEASE)
        previous = os.environ.get('IPHONE_LINUX_PROFILE'); mask = os.umask(0o022)
        try:
            self.assertEqual(self.accepted(CLI.run, self.root, self.request()), 0)
            self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'), previous)
            current = os.umask(0o022); self.assertEqual(current, 0o022)
        finally: os.umask(mask)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertFalse(any(self.root.rglob('handler-contract-private.json')))

    def test_known_bundle_and_exact_release_are_coupled_before_identity(self):
        # Mutation killed: ignore the metadata release while selecting by the bundle.
        for changes in ({'kernel_release': CLI.RELEASE}, {'kernel_patchset': 'unknown'},
                        {'pcie_driver_runtime': False}, {'pcie_iommu_parent': 1}, {'module_automatic_load': True}):
            self.write('provenance.json', json.dumps(dict(self.metadata, **changes)).encode())
            with self.subTest(changes=changes), self.assertRaises(ValueError): CLI.selection(self.root, self.profile)
            with self.assertRaises(ValueError): CLI.run(self.root, self.request())
        self.assertEqual(self.identity_reads, 0)
        self.assertFalse(any(self.root.rglob('handler-contract-private.json')))

    def test_each_pmd_action_routes_a_real_session_to_its_model_handler_only(self):
        # Existing routing contracts must also preserve the explicit PMD ABI and WCC set.
        for action in ('acquire', 'assign', 'start', 'observe', 'stop'):
            request = self.request(action, check=False)
            self.assertEqual(self.accepted(CLI.run, self.root, request), 0)
            value = json.loads((request['output'] / 'handler-contract-private.json').read_text())
            self.assertEqual(value['action'], action); self.assertEqual(value['release'], RELEASE)
            self.assertEqual(value['kind'], 'held' if action in ('acquire', 'assign') else 'runtime')
            self.assertEqual(value['drivers'], self.selected['drivers'])
            self.assertEqual([p.name for p in request['output'].iterdir()], ['handler-contract-private.json'])

    def test_crossed_diagnostic_bytes_refuse_before_identity_or_output(self):
        # The unchanged real ELF/size/hash reader must protect PMD before identity access.
        path = self.folder / 'n71-pcie-diagnostic.ko'; path.write_bytes(path.read_bytes() + b'X')
        with self.assertRaises(ValueError): CLI.run(self.root, self.request())
        self.assertEqual(self.identity_reads, 0)
        self.assertFalse(any(self.root.rglob('handler-contract-private.json')))


@unittest.skipIf(os.environ.get('N71_PMD_RUNTIME_CLI_SCRIPT'), 'Mutation child selects subject')
class PmdCliMutations(unittest.TestCase):
    def test_weakened_bundle_or_reader_release_fail_by_assertion(self):
        variants = [
            ('mapping', "'n71-dart-serdev-pmd-v1': iommu.PMD_RELEASE", "'unrecorded-pmd': iommu.PMD_RELEASE", 'selection_and_local_check_keep_all_private_inputs_and_environment'),
            ('metadata-release', "metadata.get('kernel_release') == release", 'True', 'known_bundle_and_exact_release_are_coupled_before_identity'),
            ('selection-release', "'directory': profile.parent, 'release': release", "'directory': profile.parent, 'release': RELEASE", 'selection_and_local_check_keep_all_private_inputs_and_environment'),
            ('reader-release', "link.module_bytes(request['profile'].parent, record, release=release)", "link.module_bytes(request['profile'].parent, record, release=RELEASE)", 'selection_and_local_check_keep_all_private_inputs_and_environment'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-pmd-cli-mutations-') as directory:
            for name, before, after, method in variants:
                text = SOURCE.read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory)/(name+'.py'); path.write_text(body)
                environment = dict(os.environ, N71_PMD_RUNTIME_CLI_SCRIPT=str(path), PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT/'tests'))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_n71_pmd_runtime_cli.PmdRuntimeCli.test_'+method],
                                        env=environment, capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name+result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name+result.stderr)
                print('PMD_CLI_ASSERTION_KILL '+name, flush=True)


if __name__ == '__main__':
    unittest.main()
