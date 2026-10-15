"""Data capture bounds and completion; no USB or boot executables in tests."""
import importlib.util
from pathlib import Path
import plistlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pongo_reference', ROOT / 'scripts/research/pongo-n71-reference.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class PongoN71Reference(unittest.TestCase):
    def test_single_usb_identity_required(self):
        one = {'IORegistryEntryName': 'PongoOS USB Device'}
        reader.usb_ready(plistlib.dumps([one]))
        for data in ([], [one, one], [{'IORegistryEntryName': 'iPhone 6s Linux probe'}]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                reader.usb_ready(plistlib.dumps(data))

    def test_exact_read_only_command_and_complete_output(self):
        code = ('import sys; data=sys.stdin.buffer.read(); '
                'assert data == b"dt\\n"; '
                'sys.stdout.write("name device-tree\\n    apcie-phy-tunables 01 00\\npongoOS> ")')
        output = reader.capture([sys.executable, '-c', code], timeout=5)
        report = reader.summary(output)
        self.assertEqual(report['property_names_present_anywhere'], ['apcie-phy-tunables'])
        self.assertFalse(report['board_and_tunable_semantics_verified'])
        self.assertFalse(report['mmio_commands_sent'])
        self.assertFalse(report['payload_sent'])

    def test_missing_completion_is_not_a_capture(self):
        for output in (b'', b'name device-tree\n', b'pongoOS> ',
                       b'name device-tree\npongoOS> partial'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                reader.summary(output)

    def test_output_bound_and_timeout(self):
        with self.assertRaisesRegex(ValueError, 'output bound'):
            reader.capture([sys.executable, '-c', 'print("x" * 200)'], timeout=5, maximum=100)
        with self.assertRaises(TimeoutError):
            reader.capture([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=0.1)

    def test_client_error_is_not_a_capture(self):
        with self.assertRaisesRegex(ValueError, 'unsuccessfully'):
            reader.capture([sys.executable, '-c', 'raise SystemExit(3)'], timeout=5)


if __name__ == '__main__':
    unittest.main()
