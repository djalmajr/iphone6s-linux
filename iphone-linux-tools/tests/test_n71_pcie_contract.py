"""Compile and exercise S8000 primitives without accessing real hardware."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER_DIR = Path(os.environ.get('N71_PCIE_HEADER_DIR', ROOT / 'phone/kernel'))


class N71PcieContract(unittest.TestCase):
    def test_native_reference_and_preservation_cases(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native C compiler unavailable; this is not a passing native gate.')
        with tempfile.TemporaryDirectory(prefix='n71-pcie-test-') as directory:
            binary = Path(directory) / 'contract'
            compile_result = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(HEADER_DIR), str(ROOT / 'tests/n71_pcie_contract.c'),
                 '-o', str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('N71_PCIE_PRIMITIVES_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
