"""Stable DART observations must fail closed before any output is published."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('missing-quiet', 'error = io->quiet(io->context);', 'error = 0;'),
    ('wrong-tcr', 'index == 1 ? 0xc', 'index == 1 ? 0x8'),
    ('ignore-unavailable', 'if (value == 0xffffffffU)', 'if (value == 0xfffffffeU)'),
    ('ignore-busy', 'value & 8', 'value & 16'),
    ('ignore-instability', 'else if (value != first[index])', 'else if (value == first[index])'),
    ('wrong-ttbr-valid', '1U << 31', '1U << 30'),
    ('truncate-ttbr', 'result.ttbr[index] = first[index + 3];',
     'result.ttbr[index] = first[index + 3] & 0x80000000U;'),
)


class DartObservationTests(unittest.TestCase):
    def test_fault_boundaries_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-dart-observe.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-dart-observe-') as directory:
            folder = Path(directory)
            shutil.copyfile(ROOT / 'phone/kernel/n71-pcie-contract.h', folder / 'n71-pcie-contract.h')
            header, binary = folder / 'n71-dart-observe.h', folder / 'observe'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertGreaterEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after))
                compiled = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                                           '-I', str(folder), str(ROOT / 'tests/n71_dart_observe.c'), '-o', str(binary)],
                                          capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_DART_OBSERVE_OK', result.stdout)
                else:
                    self.assertEqual(result.returncode, -6, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)


if __name__ == '__main__':
    unittest.main()
