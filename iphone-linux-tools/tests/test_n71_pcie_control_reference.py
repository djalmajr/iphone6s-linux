"""Compile the read-only capability contract and kill weakened guards by assertion."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('identity', '0x1004106b : 0x43a314e4', '0x1004106b : 0x43a314e5'),
    ('bus-master', 'command & 4)', 'command & 8)'),
    ('alignment', 'next % 4 ||', 'next % 2 ||'),
    ('pm-width', 'id == 1 ? 4 : 2, 2, id', 'id == 1 ? 4 : 2, 4, id'),
    ('scope', 'id == 1 || id == 5', 'id == 1 || id == 9 || id == 5'),
    ('capacity', 'result.capabilities == 16', 'result.capabilities == 15'),
    ('partial-output', 'if (!io || !io->read || !out)',
     'if (out) *out = result;\n\tif (!io || !io->read || !out)'),
)


class ControlReference(unittest.TestCase):
    def test_faults_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native compiler unavailable; gate not passed.')
        source = (ROOT / 'phone/kernel/n71-pcie-control-reference.h').read_text()
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        try:
            with tempfile.TemporaryDirectory(prefix='n71-controls-') as directory:
                folder = Path(directory)
                header, binary = folder / 'n71-pcie-control-reference.h', folder / 'test'
                for name, before, after in (('baseline', None, None),) + MUTATIONS:
                    with self.subTest(mutation=name):
                        if before is not None:
                            self.assertEqual(source.count(before), 1)
                        header.write_text(source if before is None else source.replace(before, after, 1))
                        result = subprocess.run(
                            [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                             '-I', str(folder), '-I', str(ROOT / 'phone/kernel'),
                             str(ROOT / 'tests/n71_pcie_control_reference.c'), '-o', str(binary)],
                            capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        result = subprocess.run([str(binary)], capture_output=True, text=True,
                                                timeout=5, cwd=folder)
                        if before is None:
                            self.assertEqual(result.returncode, 0, result.stderr)
                            self.assertIn('N71_CONTROL_REFERENCE_OK', result.stdout)
                        else:
                            self.assertEqual(result.returncode, -6, result.stderr)
                            self.assertIn('assert', result.stderr.lower())
        finally:
            resource.setrlimit(resource.RLIMIT_CORE, limits)


if __name__ == '__main__':
    unittest.main()
