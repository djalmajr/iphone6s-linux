"""Real Session load command with modeled qualified interface and phone replies."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_n71_pmd_session_entry as fixture
import test_n71_pmd_runtime_build as pmd_fixture

ROOT = fixture.ROOT
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_profile.py'
LINK_SOURCE = ROOT / 'scripts/host/n71-link-session.py'
spec = importlib.util.spec_from_file_location('observer_options_under_test', Path(os.environ.get('N71_OBSERVER_OPTIONS_SCRIPT', SOURCE)))
SUBJECT = importlib.util.module_from_spec(spec); spec.loader.exec_module(SUBJECT)


class ReachedLoad(Exception):
    pass


class ObserverOptions(unittest.TestCase):
    def setUp(self):
        case = fixture.PmdSessionEntry('test_real_constructor_keeps_two_diagnostics_and_five_owned_drivers')
        case.setUp(); self.addCleanup(case.doCleanups); self.case = case; self.root = case.root
        self.interface = None; self.bad_hash = None; self.calls = []
        self.pmd = pmd_fixture.SUBJECT; original = self.pmd.snapshot
        def snapshot(*args, **kwargs):
            kernel, modules, hashes = original(*args, **kwargs)
            modules = copy.deepcopy(modules)
            if self.interface is not None: modules['n71_pcie_diagnostic']['parameters'] = list(self.interface)
            if self.bad_hash is not None: modules['n71_pcie_diagnostic']['sha256'] = self.bad_hash
            return kernel, modules, hashes
        for hook in (patch.object(self.pmd, 'snapshot', side_effect=snapshot),
                     patch.object(fixture.LINK, 'n71_driver_runtime_profile', SUBJECT)):
            hook.start(); self.addCleanup(hook.stop)
        data = json.loads((ROOT / 'docs/evidence/n71-pmd-observer-build.json').read_text())
        self.observer_interface = data['modules']['n71_pcie_diagnostic']['parameters']

    def accepted(self, function, *args):
        try: return function(*args)
        except (ValueError, KeyError, OSError) as error: self.fail('Qualified observer options refused: ' + str(error))

    def session(self):
        return self.case.session()

    def command(self, session):
        # Existing gates cover preflight; this probe starts at latch activation.
        session.preflight = lambda: None
        def capture(stage, command, raw=None):
            self.calls.append((stage, command))
            if stage == 'observe':
                text = ('N71_REG_ON_OBSERVED control=80 bit0=0 compatible-plan=1\n'
                    'N71_REG_ON_PARENT simple-mfd-i2c shared-regmap; no rebind\n'
                    'bound=1 active=0 restore_pending=0\nN71_REG_ON_CONTROL_READBACK value=80\n')
            elif stage == 'activate':
                text = fixture.LINK.STATE_ACTIVE + '\nN71_REG_ON_CONTROL_READBACK value=81\n'
            else:
                self.assertEqual(stage, 'pcie'); raise ReachedLoad()
            return SimpleNamespace(returncode=0, stdout=text, stderr='')
        session.capture = capture
        with self.assertRaises(ReachedLoad): session.experiment()
        self.assertEqual([name for name, _ in self.calls], ['observe', 'activate', 'pcie'])
        return self.calls[-1][1]

    def test_disabled_and_previous_abi_do_not_query_observer_context(self):
        for session in (SimpleNamespace(driver_runtime=False),
                        SimpleNamespace(driver_runtime=True, release='7.2.0-iphone6s-dart-serdev-power2')):
            with patch.object(SUBJECT, 'selected', side_effect=AssertionError('Do not read observer context')):
                self.assertEqual(SUBJECT.observer_parameters(session, self.root), '')

    def test_previous_pmd_interface_preserves_the_real_load_command(self):
        session = self.accepted(self.session)
        self.assertEqual(self.accepted(SUBJECT.observer_parameters, session, self.root), '')
        command = self.command(session)
        self.assertIn(' driver_runtime=1', command)
        self.assertNotIn('dma_observe=', command); self.assertNotIn('dma_iova=', command)

    def test_complete_interface_adds_both_options_once_to_the_real_command(self):
        self.interface = self.observer_interface
        session = self.accepted(self.session); original = copy.deepcopy(session.modules)
        self.assertEqual(self.accepted(SUBJECT.observer_parameters, session, self.root),
                         ' dma_observe=1 dma_iova=0x3ffff028')
        command = self.command(session)
        self.assertEqual(command.count(' dma_observe=1'), 1)
        self.assertEqual(command.count(' dma_iova=0x3ffff028'), 1)
        self.assertEqual(command.count('insmod '), 1)
        self.assertEqual(session.modules, original)

    def test_partial_or_duplicate_interface_refuses_before_load(self):
        for name in ('dma_observe', 'dma_iova', 'dma_observation'):
            values = [row for row in self.observer_interface if not row.startswith(name + ':')]
            for interface in (values, self.observer_interface + [next(row for row in self.observer_interface if row.startswith(name + ':'))]):
                self.interface = interface
                session = self.accepted(self.session)
                with self.assertRaises(ValueError): SUBJECT.observer_parameters(session, self.root)

    def test_changed_bytes_refuse_before_options_are_returned(self):
        self.interface = self.observer_interface; session = self.accepted(self.session)
        record, raw = session.modules[0]; session.modules[0] = (record, bytes([raw[0] ^ 1]) + raw[1:])
        with self.assertRaises(ValueError): SUBJECT.observer_parameters(session, self.root)

    def test_catalog_identity_change_after_session_validation_is_refused(self):
        self.interface = self.observer_interface; session = self.accepted(self.session)
        original = SUBJECT.selected
        def changed(session, root):
            original(session, root); self.bad_hash = 'f' * 64
        with patch.object(SUBJECT, 'selected', side_effect=changed), self.assertRaises(ValueError):
            SUBJECT.observer_parameters(session, self.root)


@unittest.skipIf(os.environ.get('N71_OBSERVER_OPTIONS_SCRIPT') or os.environ.get('N71_PMD_LINK_ENTRY_SCRIPT'), 'Mutation child')
class ObserverOptionMutations(unittest.TestCase):
    def test_validation_interface_and_load_route_fail_by_assertion(self):
        variants = [
            ('legacy', SOURCE, 'N71_OBSERVER_OPTIONS_SCRIPT', 'or session.release != iommu.PMD_RELEASE', 'or False', 'disabled_and_previous_abi_do_not_query_observer_context'),
            ('session-validation', SOURCE, 'N71_OBSERVER_OPTIONS_SCRIPT', '    selected(session, root)\n    import n71_pmd_runtime_build', '    pass\n    import n71_pmd_runtime_build', 'changed_bytes_refuse_before_options_are_returned'),
            ('module-identity', SOURCE, 'N71_OBSERVER_OPTIONS_SCRIPT', "session.modules[0][0]['sha256'] == pcie['sha256']", 'True', 'catalog_identity_change_after_session_validation_is_refused'),
            ('partial-interface', SOURCE, 'N71_OBSERVER_OPTIONS_SCRIPT', 'counts == (1, 1, 1)', 'True', 'partial_or_duplicate_interface_refuses_before_load'),
            ('previous-interface', SOURCE, 'N71_OBSERVER_OPTIONS_SCRIPT', 'if not any(counts):', 'if False:', 'previous_pmd_interface_preserves_the_real_load_command'),
            ('enable', SOURCE, 'N71_OBSERVER_OPTIONS_SCRIPT', 'return \' dma_observe=1 dma_iova=0x3ffff028\'', 'return \' dma_observe=0 dma_iova=0x3ffff028\'', 'complete_interface_adds_both_options_once_to_the_real_command'),
            ('iova', SOURCE, 'N71_OBSERVER_OPTIONS_SCRIPT', 'return \' dma_observe=1 dma_iova=0x3ffff028\'', 'return \' dma_observe=1 dma_iova=0x3ffff000\'', 'complete_interface_adds_both_options_once_to_the_real_command'),
            ('load-route', LINK_SOURCE, 'N71_PMD_LINK_ENTRY_SCRIPT',
             'parameters += n71_driver_runtime_profile.observer_parameters(self, ROOT)',
             'parameters += ""', 'complete_interface_adds_both_options_once_to_the_real_command'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-observer-options-mutations-') as directory:
            for name, source, variable, before, after, method in variants:
                text = source.read_text(); self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory) / (name + '.py'); path.write_text(body)
                env = dict(os.environ, **{variable: str(path)}, PYTHONPATH=str(ROOT / 'tests'), PYTHONDONTWRITEBYTECODE='1')
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                    'test_n71_observer_options.ObserverOptions.test_' + method], env=env,
                    capture_output=True, text=True, timeout=45)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name + result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('OBSERVER_OPTIONS_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
