"""Retained recovery must survive partial probe, stop and each table-write fault."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('forget-start', 'lease->attempted = true;', 'lease->attempted = false;'),
    ('duplicate-start', 'lease->captured || lease->attempted', 'false'),
    ('forget-pending', 'lease->attempted && !lease->restored', 'false'),
    ('skip-stop', 'n71_dart_error(io->stop(io->context))', '0'),
    ('repeat-stop', 'if (!lease->stopped)', 'if (true)'),
    ('advance-failed-word', 'if (error)\n\t\t\tgoto failed;\n\t\tlease->restore_index++;',
     'if (error) { lease->restore_index++; goto failed; }\n\t\tlease->restore_index++;'),
    ('restart-prefix', 'lease->restore_error = 0;', 'lease->restore_error = 0; lease->restore_index = 0;'),
    ('stale-running', 'lease->running = false;', '(void)0;'),
    ('ignore-drift', 'index < lease->restore_index', 'index < lease->restore_index && false'),
    ('short-restore', 'while (lease->restore_index < 16)', 'while (lease->restore_index < 15)'),
    ('ignore-readback', 'observed.ttbr[index] != lease->saved.ttbr[index]', 'false'),
    ('overwrite-baseline', 'lease->saved = observed;', 'lease->saved = (struct n71_dart_observation){0};'),
    ('skip-guard', 'n71_dart_error(io->quiet(io->context))', '0'),
    ('ignore-control', 'if (lease->control_changed && !lease->operation_error)', 'if (false)'),
    ('ignore-start-table', 'if (observed.ttbr[index])', 'if (false)'),
)


class DartLeaseTests(unittest.TestCase):
    def test_recovery_outcomes_and_compiled_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-dart-lease.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-dart-lease-') as directory:
            folder = Path(directory)
            for name in ('n71-dart-cycle.h', 'n71-dart-observe.h', 'n71-pcie-contract.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            header, binary = folder / 'n71-dart-lease.h', folder / 'lease'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    if before:
                        self.assertIn(before, source)
                    header.write_text(source if before is None else source.replace(before, after))
                    compiled = subprocess.run(
                        [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                         '-I', str(folder), str(ROOT / 'tests/n71_dart_lease.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                    executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                    if before is None:
                        self.assertEqual(executed.returncode, 0, executed.stderr)
                        self.assertIn('N71_DART_LEASE_OK cases=', executed.stdout)
                        print(executed.stdout.strip())
                    else:
                        self.assertEqual(executed.returncode, -6, name + executed.stderr)
                        self.assertIn('assert', executed.stderr.lower())


if __name__ == '__main__':
    unittest.main()
