"""Compile the N71 enumeration sequence with synthetic register and GPIO I/O."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class N71PcieLink(unittest.TestCase):
    def test_native_enumeration_and_reset_on_failure(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native C compiler unavailable; native gate not passed.')
        with tempfile.TemporaryDirectory(prefix='n71-pcie-link-') as directory:
            binary = Path(directory) / 'link'
            result = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(ROOT / 'phone/kernel'), str(ROOT / 'tests/n71_pcie_link.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('N71_PCIE_LINK_SEQUENCE_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
