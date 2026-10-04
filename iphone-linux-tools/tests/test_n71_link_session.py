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
from test_n71_bar_result import TEXT as SIZING, RAW as SIZING_RAW
from test_n71_chip_result import TEXT as CHIP_ID
from test_n71_dart_result import TEXT as DART

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
LINK = ('N71_PCIE_LINK_RESULT error=0 port88=00000005 reads=12\n'
        'N71_PCIE_ENDPOINT_ID=43a314e4; bus-master clear; no radio\n')
INVENTORY = ('N71_PCIE_INVENTORY_RESULT error=0; no config writes\n'
             'N71_PCIE_INVENTORY class-revision=02800001 header=00000000 subsystem=0000106b\n'
             'N71_PCIE_INVENTORY command-status=00100002 interrupt=000001ff reads=19 caps=3\n'
             + ''.join('N71_PCIE_BAR_RAW index=' + str(index) + ' value=00000000; no sizing or MMIO access\n'
                       for index in range(6))
             + 'N71_PCIE_CAP_RAW express=40/00025010 msi=50/00806005 msix=60/00000011\n')
SCAN = ('N71_PCIE_SCAN_DEVICE bus=0 devfn=08 id=1004106b class=060400 command=0103 driver=none\n'
        'N71_PCIE_SCAN_DEVICE bus=1 devfn=00 id=43a314e4 class=028000 command=0103 driver=none\n'
        + ''.join(f'N71_PCIE_SCAN_BAR index={index} start=0000000000000000 end=0000000000000000 flags=00000000; no MMIO\n' for index in range(6))
        + 'N71_PCIE_SCAN_BUS_REMOVED bus-null=1\n'
        'N71_PCIE_SCAN_CONFIG_RESTORED error=0; decode/readback checked\n'
        'N71_PCIE_SCAN_RESULT error=0 devices=2 endpoints=1 reads=100 attempts=24 writes=20 refusals=0; no DMA or radio\n')


class LinkSessionTests(unittest.TestCase):
    def run_session(self, overrides=None, *, config_inventory=False, host_scan=False, bar_sizing=False, chip_id=False, dart_observe=False):
        replies = {'observe': OBSERVE, 'activate': ACTIVE,
                   'pcie': 'N71_PCIE_LINK_RESULT error=-110 port88=0000880c reads=10000\n',
                   'pcie-cleanup': CLEANUP, 'pcie-unload': 'N71_PCIE_UNLOADED\n',
                   'restore': RESTORE,
                   'reg-unload': 'N71_REG_ON_REMOVE error=0 restore_pending=0\nN71_REG_UNLOADED\n'}
        if host_scan:
            replies.update({'pcie-cleanup': CLEANUP + SCAN, 'pci-empty-after': 'N71_PCI_CLEANUP_EMPTY\n'})
        if bar_sizing:
            replies.update({'pcie-cleanup': CLEANUP + SIZING, 'pci-empty-after': 'N71_PCI_CLEANUP_EMPTY\n'})
        if chip_id:
            replies.update({'pcie-cleanup': CLEANUP + SIZING + CHIP_ID, 'pci-empty-after': 'N71_PCI_CLEANUP_EMPTY\n'})
        if dart_observe:
            replies.update({'pcie-cleanup': CLEANUP + DART, 'pci-empty-after': 'N71_PCI_CLEANUP_EMPTY\n'})
        replies.update(overrides or {})
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(MODULE.device_profile, 'ssh_options', return_value=[]):
                session = MODULE.Session(Path(folder), [], config_inventory=config_inventory,
                                         host_scan=host_scan, bar_sizing=bar_sizing, chip_id=chip_id, dart_observe=dart_observe)

            def capture(stage, command, raw=None):
                calls.append((stage, command))
                value = replies[stage]
                if isinstance(value, Exception):
                    raise value
                if isinstance(value, SimpleNamespace):
                    return value
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

    def test_inventory_opt_in_selects_the_new_hash_only(self):
        with patch.object(MODULE, 'ROOT', ROOT):
            original = MODULE.selected_records(False)
            selected = MODULE.selected_records(True)
        self.assertEqual([record['module'] for record in selected], [record['module'] for record in original])
        self.assertNotEqual(selected[0]['sha256'], original[0]['sha256'])
        self.assertEqual(selected[1], original[1])

    def test_inventory_requires_mode_identity_and_full_private_result(self):
        code, result, calls = self.run_session({'pcie': LINK + INVENTORY}, config_inventory=True)
        self.assertEqual(code, 0)
        self.assertIn('enumerate=1 config_inventory=1;', calls['pcie'])
        self.assertEqual(result['inventory']['bars_raw'], [0] * 6)
        self.assertEqual(result['inventory']['reads'], 19)
        self.assertFalse(result['dma_enabled'])
        self.assertFalse(result['wifi_verified'])
        _, result, calls = self.run_session({'pcie': LINK})
        self.assertNotIn('config_inventory=', calls['pcie'])
        self.assertNotIn('inventory', result)
        for altered in (LINK.replace('43a314e4', '43b114e4') + INVENTORY, LINK,
                        LINK.replace('error=0', 'error=-110') + INVENTORY):
            code, result, calls = self.run_session({'pcie': altered}, config_inventory=True)
            self.assertEqual(code, 1)
            self.assertNotIn('inventory', result)
            self.assertTrue(result['cleanup_verified'])
            self.assertIn('reg-unload', calls)

    def test_incomplete_or_unqualified_inventory_still_cleans_up(self):
        altered = [INVENTORY.replace('error=0;', 'error=-5;'), INVENTORY + INVENTORY,
                   INVENTORY.replace('reads=19', 'reads=64'), INVENTORY.replace('caps=3', 'caps=49'),
                   INVENTORY.replace('command-status=00100002', 'command-status=00100006'),
                   INVENTORY.replace('header=00000000', 'header=00010000'),
                   INVENTORY.replace('index=5', 'index=4'), INVENTORY.replace('index=5', 'index=6'),
                   INVENTORY.replace('express=40', 'express=41'),
                   INVENTORY.replace('express=40', 'express=d0'),
                   INVENTORY.replace('00025010', '00025005'),
                   INVENTORY.replace('00025010', '00625010'),
                   INVENTORY.replace('00025010', '00005010'),
                   INVENTORY.replace('msi=50/00806005', 'msi=00/00806005'),
                   INVENTORY.replace('msi=50/00806005', 'msi=40/00806005'),
                   INVENTORY.replace('msix=60/00000011', 'msix=60/00000005')]
        for text in altered:
            with self.subTest(text=text):
                code, result, calls = self.run_session({'pcie': LINK + text}, config_inventory=True)
                self.assertEqual(code, 1)
                self.assertNotIn('inventory', result)
                self.assertTrue(result['cleanup_verified'])
                self.assertIn('pcie-unload', calls)
                self.assertIn('reg-unload', calls)

    def test_inventory_accepts_absent_optional_interrupt_capabilities(self):
        text = INVENTORY.replace('msi=50/00806005 msix=60/00000011', 'msi=00/00000000 msix=00/00000000')
        self.assertEqual(MODULE.inventory_result(text)['capability_headers_raw'][2:], (0, 0, 0, 0))

    def test_host_scan_selects_new_module_and_requires_safe_result(self):
        with patch.object(MODULE, 'ROOT', ROOT):
            selected = MODULE.selected_records(False, True)
            self.assertNotEqual(selected[0]['sha256'], MODULE.selected_records(True)[0]['sha256'])
        code, result, calls = self.run_session({'pcie': LINK + INVENTORY + SCAN}, host_scan=True)
        self.assertEqual(code, 0)
        self.assertIn('config_inventory=1 host_scan=1;', calls['pcie'])
        self.assertEqual(result['host_scan']['devices'], 2)
        self.assertFalse(result['dma_enabled'])
        altered = (SCAN + SCAN, SCAN.replace('command=0103', 'command=0107'),
                   SCAN.replace('error=0 devices', 'error=-1 devices'),
                   SCAN.replace('refusals=0', 'refusals=1'), SCAN.replace('attempts=24', 'attempts=130'),
                   SCAN.replace('index=5', 'index=4'), SCAN.replace('class=028000', 'class=020000'),
                   SCAN.replace('bus-null=1', 'bus-null=0'), SCAN.replace('RESTORED error=0', 'RESTORED error=-5'))
        for text in altered:
            with self.subTest(text=text):
                code, result, calls = self.run_session({'pcie': LINK + INVENTORY + text}, host_scan=True)
                self.assertEqual(code, 1)
                self.assertNotIn('host_scan', result)
                self.assertIn('reg-unload', calls)

    def test_unproved_host_cleanup_or_nonempty_sysfs_prevents_unload(self):
        for overrides in ({'pcie-cleanup': CLEANUP + SCAN.replace('RESTORED error=0', 'RESTORED error=-5')},
                          {'pci-empty-after': SimpleNamespace(returncode=1, stdout='')}):
            code, result, calls = self.run_session(dict(overrides, pcie=LINK + INVENTORY + SCAN), host_scan=True)
            self.assertEqual(code, 1)
            self.assertFalse(result['cleanup_verified'])
            self.assertNotIn('pcie-unload', calls)
            self.assertIn('reg-unload', calls)

    def test_host_scan_failure_with_restoration_still_allows_cleanup(self):
        failed = SCAN.replace('error=0 devices', 'error=-1 devices').replace('refusals=0', 'refusals=1')
        code, result, calls = self.run_session({'pcie': LINK + INVENTORY + failed,
                                              'pcie-cleanup': CLEANUP + failed}, host_scan=True)
        self.assertEqual(code, 1)
        self.assertTrue(result['cleanup_verified'])
        self.assertIn('pcie-unload', calls)

    def test_hot_preflight_requires_history_and_exclusive_module_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            from n71_session_history import History
            history = History.__new__(History)
            history.lines = ['[ 10.123456] dev N71_PCIE_RESET_RESTORED asserted=1 readback=1']
            history.known = frozenset(history.lines)
            history.boot_id = None
            with patch.object(MODULE.device_profile, 'ssh_options', return_value=[]):
                session = MODULE.Session(Path(folder), [({'module': 'n71-pcie-diagnostic.ko', 'sha256': 'a' * 64}, b'module')], history=history)
            calls = []
            live = MODULE.RELEASE + '\nN71_BOOT_ID 12345678-1234-1234-1234-123456789abc\n' + history.lines[0] + '\n'
            def capture(stage, command, raw=None):
                calls.append((stage, command))
                return SimpleNamespace(returncode=0, stdout=live)
            session.capture = capture
            session.preflight()
            self.assertIn('/run/n71-link-', dict(calls)['transfer-n71-pcie-diagnostic.ko'])
            self.assertIn('set -C', dict(calls)['transfer-n71-pcie-diagnostic.ko'])
            self.assertIn('test -z', dict(calls)['pci-empty'])
            history.lines = []
            with self.assertRaises(ValueError):
                session.preflight()

    def test_hot_capture_retains_raw_log_and_filters_only_prior_results(self):
        with tempfile.TemporaryDirectory() as folder:
            from n71_session_history import History
            history = History.__new__(History)
            old = '[ 10.123456] dev N71_PCIE_LINK_RESULT error=0'
            new = '[ 12.123456] dev N71_PCIE_LINK_RESULT error=-5'
            history.known = frozenset([old])
            with patch.object(MODULE.device_profile, 'ssh_options', return_value=[]):
                session = MODULE.Session(Path(folder), [], history=history)
            with patch.object(MODULE.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=(old + '\n' + new + '\n').encode(), stderr=b'')):
                result = session.capture('pcie', 'dmesg')
            self.assertEqual(result.stdout, new + '\n')
            self.assertIn(old, (Path(folder) / 'pcie-private.log').read_text())

    def test_direct_sizing_mode_and_cleanup(self):
        inventory = INVENTORY
        for index, raw in enumerate(SIZING_RAW):
            inventory = inventory.replace(f'index={index} value=00000000', f'index={index} value={raw:08x}')
        with patch.object(MODULE, 'ROOT', ROOT):
            self.assertNotEqual(MODULE.selected_records(False, False, True)[0]['sha256'],
                                MODULE.selected_records(False, True)[0]['sha256'])
            with self.assertRaises(ValueError):
                MODULE.selected_records(False, True, True)
        code, proof, calls = self.run_session({'pcie': LINK + inventory + SIZING}, bar_sizing=True)
        self.assertEqual(code, 0)
        self.assertIn('config_inventory=1 bar_sizing=1;', calls['pcie'])
        self.assertEqual(proof['bar_sizing']['bars'][0]['bytes'], 0x8000)
        for cleanup in (CLEANUP, CLEANUP + SIZING.replace('RESTORED error=0', 'RESTORED error=-5')):
            code, proof, calls = self.run_session({'pcie': LINK + inventory + SIZING,
                                                  'pcie-cleanup': cleanup}, bar_sizing=True)
            self.assertEqual(code, 1)
            self.assertFalse(proof['cleanup_verified'])
            self.assertNotIn('pcie-unload', calls)

    def test_chip_mode_requires_full_identity_and_mapping_cleanup(self):
        inventory = INVENTORY
        for index, raw in enumerate(SIZING_RAW):
            inventory = inventory.replace(f'index={index} value=00000000', f'index={index} value={raw:08x}')
        with patch.object(MODULE, 'ROOT', ROOT):
            self.assertNotEqual(MODULE.selected_records(False, chip_id=True)[0]['sha256'],
                                MODULE.selected_records(False, bar_sizing=True)[0]['sha256'])
        code, proof, calls = self.run_session({'pcie': LINK + inventory + SIZING + CHIP_ID}, chip_id=True)
        self.assertEqual(code, 0)
        self.assertEqual(proof['chip_id']['revision'], 2)
        self.assertIn('config_inventory=1 chip_id=1;', calls['pcie'])
        self.assertNotIn('bar_sizing=1', calls['pcie'])
        code, proof, calls = self.run_session({'pcie': LINK + inventory + SIZING + CHIP_ID,
                                              'pcie-cleanup': CLEANUP + SIZING + CHIP_ID.replace('claimed=0', 'claimed=1')}, chip_id=True)
        self.assertEqual(code, 1)
        self.assertFalse(proof['cleanup_verified'])
        self.assertNotIn('pcie-unload', calls)

    def test_dart_mode_has_separate_module_and_no_sizing(self):
        with patch.object(MODULE, 'ROOT', ROOT):
            selected = MODULE.selected_records(False, dart_observe=True)
            self.assertNotEqual(selected[0]['sha256'], MODULE.selected_records(False, chip_id=True)[0]['sha256'])
            with self.assertRaises(ValueError):
                MODULE.selected_records(False, chip_id=True, dart_observe=True)
        code, proof, calls = self.run_session({'pcie': LINK + INVENTORY + DART}, dart_observe=True)
        self.assertEqual(code, 0)
        self.assertEqual(proof['dart_observation']['valid_ttbr_count'], 2)
        self.assertFalse(proof['dma_enabled'])
        self.assertIn('config_inventory=1 dart_observe=1;', calls['pcie'])
        self.assertNotIn('bar_sizing=1', calls['pcie'])
        self.assertIn('pci-empty-after', calls)

    def test_dart_map_cleanup_or_pci_residue_prevents_unload(self):
        for changed in ({'pcie-cleanup': CLEANUP},
                        {'pcie-cleanup': CLEANUP + DART.replace('claimed=0', 'claimed=1')},
                        {'pci-empty-after': SimpleNamespace(returncode=1, stdout='residue')}):
            code, proof, calls = self.run_session(dict({'pcie': LINK + INVENTORY + DART}, **changed), dart_observe=True)
            self.assertEqual(code, 1)
            self.assertFalse(proof['cleanup_verified'])
            self.assertNotIn('pcie-unload', calls)
            self.assertIn('reg-unload', calls)


if __name__ == '__main__':
    unittest.main()
