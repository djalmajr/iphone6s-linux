"""Compile optional-range regressions; count only compiled assertion deaths."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('io-baseline-ignored', 'layout->io_absent && (windows[0] || state->extra[2])', 'false'),
    ('pref-baseline-ignored', 'layout->pref_absent && (windows[1] || windows[2] || state->extra[1])', 'false'),
    ('io-flag-lost', 'state->io_absent = layout->io_absent;', 'state->io_absent = false;'),
    ('pref-flag-lost', 'state->pref_absent = layout->pref_absent;', 'state->pref_absent = false;'),
    ('io-support-invented', 'io_range = state->io_absent &&', 'io_range = true &&'),
    ('pref-support-invented', '!(state->pref_absent && request->where', '!(true && request->where'),
    ('observed-race-ignored', 'if (observed)\n\t\treturn -EAGAIN;',
     'if ((void)observed, false)\n\t\treturn -EAGAIN;'),
    ('io-upper-live-skipped', 'end = io_range ? 2 : 5;', 'end = io_range ? 1 : 5;'),
    ('pref-limit-live-skipped', 'end = io_range ? 2 : 5;', 'end = io_range ? 2 : 4;'),
    ('secondary-status-read-width', 'index == 0 ? 2 : 4, &actual', '4, &actual'),
    ('live-drift-ignored', 'if (actual)\n\t\t\treturn -EAGAIN;', 'if (false)\n\t\t\treturn -EAGAIN;'),
    ('live-error-ignored',
     'offsets[index], index == 0 ? 2 : 4, &actual);\n\t\tif (error)',
     'offsets[index], index == 0 ? 2 : 4, &actual);\n\t\tif (false)'),
    ('io-counter-lost', 'state->io_noops++;', 'state->io_noops += 0;'),
    ('pref-counter-lost', 'state->pref_noops++;', 'state->pref_noops += 0;'),
    ('emulation-not-handled', '*handled = true;', '*handled = false;'),
)


class OptionalRangeTests(unittest.TestCase):
    def test_optional_effects_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-pcie-resource-write.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-optional-ranges-') as directory:
            folder = Path(directory)
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h', 'n71-pcie-scan-config.h',
                         'n71-pcie-io16-upper.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            header, binary = folder / 'n71-pcie-resource-write.h', folder / 'policy'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before is not None:
                    self.assertEqual(source.count(before), 1, 'Mutation anchor: ' + name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                p = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                                    '-I', str(folder), str(ROOT / 'tests/n71_pcie_optional_ranges.c'),
                                    '-o', str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0, 'Compilation failure is not a kill: ' + name + p.stderr)
                p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn('N71_PCIE_OPTIONAL_RANGES_OK cases=', p.stdout)
                    print(p.stdout.strip(), flush=True)
                else:
                    self.assertEqual(p.returncode, -6, 'Missing SIGABRT: ' + name + p.stderr)
                    self.assertIn('assert', p.stderr.lower(), name)
                    print('N71_OPTIONAL_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
