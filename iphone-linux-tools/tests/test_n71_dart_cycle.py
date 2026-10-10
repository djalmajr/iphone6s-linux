"""Provider failures must still remove the device and restore the full table."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('ignore-tcr', '!state->tcr &&', 'true &&'),
    ('ignore-busy', '!(state->command & 8)', '!(state->command & 16)'),
    ('skip-stop', 'n71_dart_error(io->stop(io->context))', '0'),
    ('restore-short', 'index < 16', 'index < 15'),
    ('ignore-restore-word', 'observed.ttbr[index] != saved.ttbr[index]', 'false'),
    ('ignore-failed-write', 'result.restored = !result.restore_error;', 'result.restored = true;'),
)


class DartCycleTests(unittest.TestCase):
    def test_faulted_provider_lifecycle_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-dart-cycle.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-dart-cycle-') as directory:
            folder = Path(directory)
            for name in ('n71-dart-observe.h', 'n71-pcie-contract.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            header, binary = folder / 'n71-dart-cycle.h', folder / 'cycle'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertIn(before, source, name)
                header.write_text(source if before is None else source.replace(before, after))
                result = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                                         '-I', str(folder), str(ROOT / 'tests/n71_dart_cycle.c'), '-o', str(binary)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, name + result.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_DART_CYCLE_OK', result.stdout)
                else:
                    self.assertEqual(result.returncode, -6, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)


if __name__ == '__main__':
    unittest.main()
