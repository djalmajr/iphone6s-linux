"""Compile and fault-test endpoint-only sizing; mutants must fail assertions."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('power-of-two', '(size & (size - 1))', '(size & 0)'),
    ('upper-word', 'bar++; /* The upper word', 'bar += 0; /* The upper word'),
    ('attributes', '(sizes->masks[bar] & 0xf) != type', '(sizes->masks[bar] & 0xf) != (type & 0)'),
    ('lost-restore-error', 'if (!error)\n\t\terror = restore;', 'if (!error)\n\t\terror = 0;'),
    ('publish-on-error', 'if (!error)\n\t\t*out = result;', 'if (out)\n\t\t*out = result;'),
    ('lost-probe-error', 'return error ? error : n71_bar_decode', 'return error ? 0 : n71_bar_decode'),
)


class BarSizingTests(unittest.TestCase):
    def test_faults_and_mutation_assertions(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required; gate not passed')
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        source = (ROOT / 'phone/kernel/n71-pcie-bar-sizing.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-bar-sizing-') as directory:
            folder = Path(directory)
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h', 'n71-pcie-scan-config.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            header, binary = folder / 'n71-pcie-bar-sizing.h', folder / 'sizing'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                                           '-pedantic', '-I', str(folder),
                                           str(ROOT / 'tests/n71_pcie_bar_sizing.c'), '-o', str(binary)],
                                          capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_PCIE_BAR_SIZING_OK', result.stdout)
                else:
                    self.assertEqual(result.returncode, -6, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)


if __name__ == '__main__':
    unittest.main()
