"""Run the IO16 sequence and require compiled assertion failures for its guards."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY = 'n71-pcie-resource-write.h'
HELPER = 'n71-pcie-io16-upper.h'
MUTATIONS = (
    (HELPER, 'capture-lower-ignored', 'return lower || upper ?', 'return ((void)lower, false) || upper ?'),
    (HELPER, 'capture-upper-ignored', 'return lower || upper ?', 'return lower || ((void)upper, false) ?'),
    (POLICY, 'contradictory-absence', 'layout->io16_upper_unused && (layout->io_absent ||',
     'layout->io16_upper_unused && (false ||'),
    (POLICY, 'captured-optin-lost', 'state->io16_upper_unused = layout->io16_upper_unused;',
     'state->io16_upper_unused = false;'),
    (POLICY, 'optin-invented', 'if (state->io16_upper_unused) {', 'if (true) {'),
    (POLICY, 'counter-lost', 'state->io16_noops++;', 'state->io16_noops += 0;'),
    (POLICY, 'equal-observed-bypasses-guard', 'if (state->io16_upper_unused) {',
     'if (observed == request->value) return 0;\n\tif (state->io16_upper_unused) {'),
    (HELPER, 'observed-drift-ignored', 'if (observed)\n\t\treturn -EAGAIN;',
     'if ((void)observed, false)\n\t\treturn -EAGAIN;'),
    (HELPER, 'live-lower-ignored', 'if (lower != 0 && lower != 0x00f0)', 'if (false)'),
    (HELPER, 'disabled-lower-rejected', 'if (lower != 0 && lower != 0x00f0)', 'if (lower != 0)'),
    (HELPER, 'live-upper-ignored', 'if (upper)\n\t\treturn -EAGAIN;', 'if (false)\n\t\treturn -EAGAIN;'),
    (HELPER, 'lower-error-ignored', '0x1c, 2, &lower);\n\tif (error)',
     '0x1c, 2, &lower);\n\tif (false)'),
    (HELPER, 'upper-error-ignored', '0x30, 4, &upper);\n\tif (error)',
     '0x30, 4, &upper);\n\tif (false)'),
    (HELPER, 'secondary-status-width', '0x1c, 2, &lower', '0x1c, 4, &lower'),
    (HELPER, 'wrong-function', '!request->root ||', 'false ||'),
    (HELPER, 'wrong-register', 'request->where != 0x30 ||', 'false ||'),
    (HELPER, 'wrong-width', 'request->size != 4 ||', 'false ||'),
    (HELPER, 'wrong-value', 'request->value != 0x0000ffff)', 'false)'),
    (HELPER, 'unhandled-flag-invented', '*handled = false;', '*handled = true;'),
    (HELPER, 'handled-flag-lost', '*handled = true;', '*handled = false;'),
)


class IO16UpperTests(unittest.TestCase):
    def test_sequence_rollback_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        sources = {name: (ROOT / 'phone/kernel' / name).read_text() for name in (POLICY, HELPER)}
        with tempfile.TemporaryDirectory(prefix='n71-io16-upper-') as directory:
            folder = Path(directory)
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h', 'n71-pcie-scan-config.h',
                         'n71-pcie-pref64-disable.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            binary = folder / 'policy'
            for target, name, before, after in ((None, 'baseline', None, None),) + MUTATIONS:
                if target:
                    self.assertEqual(sources[target].count(before), 1, 'Mutation anchor: ' + name)
                for header, source in sources.items():
                    (folder / header).write_text(source.replace(before, after, 1) if header == target else source)
                p = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                                    '-I', str(folder), str(ROOT / 'tests/n71_pcie_io16_upper.c'),
                                    '-o', str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0, 'Compilation failure is not a kill: ' + name + p.stderr)
                p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if target is None:
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn('N71_PCIE_IO16_UPPER_OK cases=49', p.stdout)
                    print(p.stdout.strip(), flush=True)
                else:
                    self.assertEqual(p.returncode, -6, 'Missing SIGABRT: ' + name + p.stderr)
                    self.assertIn('assert', p.stderr.lower(), name)
                    print('N71_IO16_UPPER_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
