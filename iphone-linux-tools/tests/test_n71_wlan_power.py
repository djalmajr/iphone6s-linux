"""Verify selected N71 REG_ON address, mode refusal and bit preservation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class N71WlanPower(unittest.TestCase):
    def test_native_restricted_update_contract(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required; gate not passed.')
        with tempfile.TemporaryDirectory(prefix='n71-wlan-power-') as folder:
            binary = Path(folder) / 'contract'
            result = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(ROOT / 'phone/kernel'), str(ROOT / 'tests/n71_wlan_power.c'),
                 '-o', str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('N71_WLAN_POWER_CONTRACT_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
