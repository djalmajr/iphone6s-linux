"""Fault-inject the temporary BAR route and its mandatory restoration."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('wrong-route', '0xc0000004, 4', '0xc0010004, 4'),
    ('enable-dma', 'command & ~3U) | 2', 'command & ~3U) | 6'),
    ('wrong-chip-window', '0x18000000, 4', '0x18001000, 4'),
    ('lost-restore-error', 'if (!error)\n\t\terror = restore;', 'if (!error)\n\t\terror = 0;'),
    ('wrong-chip-revision', '(result.raw >> 16) & 0xf', '(result.raw >> 20) & 0xf'),
    ('publish-on-error', 'if (!error)\n\t\t*out = result;', 'if (out)\n\t\t*out = result;'),
)


class ChipIdentityTests(unittest.TestCase):
    def test_faults_and_mutation_assertions(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-pcie-chip-id.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-chip-id-') as directory:
            folder = Path(directory)
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h', 'n71-pcie-scan-config.h', 'n71-pcie-bar-sizing.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            header, binary = folder / 'n71-pcie-chip-id.h', folder / 'chip'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertGreaterEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after))
                compiled = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                                           '-I', str(folder), str(ROOT / 'tests/n71_pcie_chip_id.c'), '-o', str(binary)],
                                          capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_PCIE_CHIP_ID_OK', result.stdout)
                else:
                    self.assertEqual(result.returncode, -6, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)


if __name__ == '__main__':
    unittest.main()
