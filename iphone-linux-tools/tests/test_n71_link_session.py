"""Failures must not bypass fresh activation gates or final restoration."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
SPEC = importlib.util.spec_from_file_location('link_session', os.environ.get('N71_LINK_SESSION_SCRIPT', ROOT / 'scripts/host/n71-link-session.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

OBSERVE = ('N71_REG_ON_PARENT simple-mfd-i2c shared-regmap; no rebind\n'
           'N71_REG_ON_OBSERVED control=80 bit0=0 compatible-plan=1\n'
           'bound=1 active=0 restore_pending=0 original=00\n'
           'N71_REG_ON_CONTROL_READBACK value=80\n')
ACTIVE = MODULE.STATE_ACTIVE + '\nN71_REG_ON_CONTROL_READBACK value=81\nN71_REG_ON_LEVEL raw=20 bit2=0\n'
RESTORE = 'bound=1 active=0 restore_pending=0 original=80\nN71_REG_ON_CONTROL_READBACK value=80\n'
CLEANUP = 'N71_PCIE_RESET_RESTORED asserted=1 readback=1\nN71_PCIE_POWER_RELEASED powered=0 attached=0\n'


class LinkSessionTests(unittest.TestCase):
    def run_session(self, overrides=None):
        replies = {'observe': OBSERVE, 'activate': ACTIVE,
                   'pcie': 'N71_PCIE_LINK_RESULT error=-110 port88=0000880c reads=10000\n',
                   'pcie-cleanup': CLEANUP, 'pcie-unload': 'N71_PCIE_UNLOADED\n',
                   'restore': RESTORE,
                   'reg-unload': 'N71_REG_ON_REMOVE error=0 restore_pending=0\nN71_REG_UNLOADED\n'}
        replies.update(overrides or {})
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(MODULE.device_profile, 'ssh_options', return_value=[]):
                session = MODULE.Session(Path(folder), [])

            def capture(stage, command, raw=None):
                calls.append((stage, command))
                value = replies[stage]
                if isinstance(value, Exception):
                    raise value
                return SimpleNamespace(returncode=0, stdout=value)

            session.capture = capture
            session.preflight = lambda: None
            exit_code = session.run()
        return exit_code, session.result, dict(calls)

    def test_timeout_is_negative_link_with_proved_cleanup(self):
        code, result, calls = self.run_session()
        self.assertEqual(code, 0)
        self.assertFalse(result['endpoint_identified'])
        self.assertEqual(result['link']['error'], -110)
        self.assertTrue(result['cleanup_verified'])
        self.assertIn('pcie-unload', calls)
        self.assertIn('reg-unload', calls)
        self.assertIn('test "$(cat ' + MODULE.REG + 'control)"', calls['pcie'])

    def test_unknown_original_does_not_write_or_train(self):
        code, result, calls = self.run_session({'observe': OBSERVE.replace('control=80', 'control=82')})
        self.assertEqual(code, 1)
        self.assertNotIn('activate', calls)
        self.assertNotIn('pcie', calls)
        self.assertIn('restore', calls)
        self.assertNotIn('printf', calls['restore'])
        self.assertTrue(result['cleanup_verified'])

    def test_stale_active_flag_cannot_replace_fresh_control(self):
        code, result, calls = self.run_session({'activate': ACTIVE.replace('value=81', 'value=80')})
        self.assertEqual(code, 1)
        self.assertNotIn('pcie', calls)
        self.assertIn('restore', calls)
        self.assertTrue(result['cleanup_verified'])

    def test_training_ssh_timeout_still_restores(self):
        code, result, calls = self.run_session({'pcie': ValueError('SSH stage timed out')})
        self.assertEqual(code, 1)
        self.assertIn('restore', calls)
        self.assertIn('reg-unload', calls)
        self.assertTrue(result['cleanup_verified'])

    def test_unproved_pcie_cleanup_is_not_success_or_unloaded(self):
        code, result, calls = self.run_session({'pcie-cleanup': ''})
        self.assertEqual(code, 1)
        self.assertFalse(result['cleanup_verified'])
        self.assertNotIn('pcie-unload', calls)
        self.assertIn('restore', calls)

    def test_failed_reg_restore_must_not_unload(self):
        code, result, calls = self.run_session({'restore': RESTORE.replace('restore_pending=0', 'restore_pending=1')})
        self.assertEqual(code, 1)
        self.assertFalse(result['cleanup_verified'])
        self.assertNotIn('reg-unload', calls)

    def test_insmod_exit_zero_without_probe_result_is_not_evidence(self):
        code, result, _ = self.run_session({'pcie': ''})
        self.assertEqual(code, 1)
        self.assertIn('experiment_error', result)
        self.assertFalse(result['endpoint_identified'])

    def test_success_requires_identity_and_bus_master_clear(self):
        success = ('N71_PCIE_LINK_RESULT error=0 port88=0000880d reads=1\n'
                   'N71_PCIE_ENDPOINT_ID=43b114e4; bus-master clear; no radio\n')
        code, result, _ = self.run_session({'pcie': success})
        self.assertEqual(code, 0)
        self.assertTrue(result['endpoint_identified'])
        for altered in (success.splitlines()[0] + '\n', success.replace('bus-master clear', 'bus-master enabled'),
                        success.replace('43b114e4', 'ffffffff'), success.replace('0000880d', '0000880c'),
                        success.replace('reads=1', 'reads=10001')):
            code, result, _ = self.run_session({'pcie': altered})
            self.assertEqual(code, 1)
            self.assertFalse(result['endpoint_identified'])

    def test_failed_preflight_never_issues_insmod(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(MODULE.device_profile, 'ssh_options', return_value=[]):
                session = MODULE.Session(Path(folder), [])
            calls = []
            session.capture = lambda stage, command: (calls.append(command) or SimpleNamespace(returncode=255, stdout=''))
            self.assertEqual(session.run(), 1)
            self.assertEqual(len(calls), 1)
            self.assertNotIn('insmod', calls[0])

    def test_stage_log_prevents_duplicate_command_and_preserves_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(MODULE.device_profile, 'ssh_options', return_value=[]):
                session = MODULE.Session(Path(folder), [])
            with patch.object(MODULE.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ssh', 35)) as call:
                with self.assertRaises(ValueError):
                    session.capture('once', 'true')
                with self.assertRaises(FileExistsError):
                    session.capture('once', 'true')
                self.assertEqual(call.call_count, 1)
            self.assertIn('SSH_TIMEOUT', (Path(folder) / 'once-private.log').read_text())


if __name__ == '__main__':
    unittest.main()
