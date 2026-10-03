"""Exercise N71 ECAM coordinates, widths and refusal paths without hardware."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class N71PcieEcam(unittest.TestCase):
    def test_bus_function_bounds_and_read_failures(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native compiler unavailable; native gate not passed.')
        with tempfile.TemporaryDirectory(prefix='n71-pcie-ecam-') as directory:
            binary = Path(directory) / 'ecam'
            result = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(ROOT / 'phone/kernel'), str(ROOT / 'tests/n71_pcie_ecam.c'),
                 '-o', str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('N71_PCIE_ECAM_READONLY_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
