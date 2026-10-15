"""Scan results and cleanup must reject incomplete or unsafe evidence."""
import importlib.util
import os
from pathlib import Path
import unittest
from test_n71_link_session import SCAN

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('scan_result', os.environ.get(
    'N71_SCAN_RESULT_SCRIPT', ROOT / 'scripts/host/n71_scan_result.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ScanResultTests(unittest.TestCase):
    def test_sized_memory_bar_is_parsed_without_mapping_claim(self):
        text = SCAN.replace('index=0 start=0000000000000000 end=0000000000000000 flags=00000000',
                            'index=0 start=00000007c0000000 end=00000007c0003fff flags=00100200')
        result = MODULE.parse(text)
        self.assertEqual(result['bars'][0]['bytes'], 16384)
        self.assertEqual(result['bars'][1]['bytes'], 0)
        self.assertEqual(result['devices'], 2)
        self.assertEqual(result['device_details'][1]['identity'], '43a314e4')

    def test_partial_duplicate_or_unsafe_scan_is_not_success(self):
        for text in (SCAN + SCAN, '', SCAN.replace('error=0 devices', 'error=-1 devices'),
                     SCAN.replace('refusals=0', 'refusals=1'), SCAN.replace('attempts=24', 'attempts=130'),
                     SCAN.replace('command=0103', 'command=0107'), SCAN.replace('index=5', 'index=4'),
                     SCAN.replace('class=028000', 'class=020000'), SCAN.replace('devices=2', 'devices=1')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                MODULE.parse(text)

    def test_resource_size_and_kind_are_bounded(self):
        anchor = 'index=0 start=0000000000000000 end=0000000000000000 flags=00000000'
        for replacement in ('index=0 start=0000000000000000 end=0000000000000012 flags=00000200',
                            'index=0 start=0000000000000020 end=000000000000001f flags=00000200',
                            'index=0 start=0000000000000000 end=000000000000000f flags=00000100',
                            'index=0 start=0000000000000000 end=00000001ffffffff flags=00000200'):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                MODULE.parse(SCAN.replace(anchor, replacement))

    def test_config_restore_and_bus_removal_are_both_required(self):
        for text in (SCAN.replace('bus-null=1', 'bus-null=0'),
                     SCAN.replace('RESTORED error=0', 'RESTORED error=-5'),
                     SCAN.replace('N71_PCIE_SCAN_BUS_REMOVED bus-null=1\n', ''),
                     SCAN.replace('N71_PCIE_SCAN_CONFIG_RESTORED error=0; decode/readback checked\n', '')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                MODULE.cleanup(text)

    def test_failed_scan_can_prove_cleanup_without_claiming_success(self):
        text = SCAN.replace('error=0 devices', 'error=-1 devices').replace('refusals=0', 'refusals=1')
        MODULE.cleanup(text)
        with self.assertRaises(ValueError):
            MODULE.parse(text)
        before_scan = ('N71_PCIE_SCAN_RESULT error=-19 devices=0 endpoints=0 reads=6 '
                       'attempts=0 writes=0 refusals=0; no DMA or radio\n')
        MODULE.cleanup(before_scan)
        with self.assertRaises(ValueError):
            MODULE.cleanup(before_scan.replace('writes=0', 'writes=1'))

    def test_absent_scan_requires_an_earlier_negative_stage(self):
        MODULE.cleanup('N71_PCIE_LINK_RESULT error=-110 port88=0 reads=10000\n')
        for text in ('', 'N71_PCIE_LINK_RESULT error=0 port88=5 reads=12\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                MODULE.cleanup(text)


if __name__ == '__main__':
    unittest.main()
