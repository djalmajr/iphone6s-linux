"""Compile the S8000 I/O sequence against a synthetic register backend."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER_DIR = Path(os.environ.get('N71_PCIE_INIT_HEADER_DIR', ROOT / 'phone/kernel'))


class N71PcieInitialization(unittest.TestCase):
    def test_native_order_timeout_and_error_boundaries(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native C compiler unavailable; no passing native gate.')
        with tempfile.TemporaryDirectory(prefix='n71-pcie-init-test-') as directory:
            binary = Path(directory) / 'sequence'
            result = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(HEADER_DIR), str(ROOT / 'tests/n71_pcie_init.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('N71_PCIE_GLOBAL_INIT_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
