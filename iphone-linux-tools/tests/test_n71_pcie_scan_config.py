"""Compile the config-write and restoration contract without device access."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class N71PcieScanConfig(unittest.TestCase):
    def test_scan_write_boundary_and_faulted_restoration(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native compiler unavailable; native gate not passed.')
        with tempfile.TemporaryDirectory(prefix='n71-pcie-scan-') as directory:
            binary = Path(directory) / 'scan'
            compiled = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(ROOT / 'phone/kernel'),
                 str(ROOT / 'tests/n71_pcie_scan_config.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('N71_PCIE_SCAN_CONFIG_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
