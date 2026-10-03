"""Validate the N71 port preparation order and bounded failure paths."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class N71PciePort(unittest.TestCase):
    def test_native_sequence(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('No native C compiler; no passing native gate.')
        with tempfile.TemporaryDirectory(prefix='n71-pcie-port-') as directory:
            binary = Path(directory) / 'port'
            built = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(ROOT / 'phone/kernel'), str(ROOT / 'tests/n71_pcie_port.c'),
                 '-o', str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertIn('N71_PCIE_PORT_PREPARE_OK', ran.stdout)


if __name__ == '__main__':
    unittest.main()
