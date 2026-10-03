"""Verify failed/partial activation, ownership changes and verified restoration."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class N71WlanPowerSequence(unittest.TestCase):
    def test_native_reversible_activation(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required; gate not passed.')
        with tempfile.TemporaryDirectory(prefix='n71-wlan-sequence-') as folder:
            binary = Path(folder) / 'sequence'
            result = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(ROOT / 'phone/kernel'), str(ROOT / 'tests/n71_wlan_power_sequence.c'),
                 '-o', str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('N71_WLAN_POWER_SEQUENCE_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
