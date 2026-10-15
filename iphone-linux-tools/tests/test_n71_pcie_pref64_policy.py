"""Qualify the typed disable without weakening any other allocator readback."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'n71-pcie-resource-write.h'
MUTATIONS = (
    ('capture-check-lost', 'layout->pref64_disable && (layout->pref_absent ||', 'false && (layout->pref_absent ||'),
    ('capture-optin-lost', 'state->pref64_disable = layout->pref64_disable;', 'state->pref64_disable = false;'),
    ('optin-invented', 'if (state->pref64_disable) {', 'if (true) {'),
    ('live-error-ignored', 'n71_pref64_disable_expected(io, request, observed, &expected);\n\t\tif (error)',
     'n71_pref64_disable_expected(io, request, observed, &expected);\n\t\tif (false)'),
    ('equality-before-live-proof', 'if (state->pref64_disable) {',
     'if (observed == request->value) return 0;\n\tif (state->pref64_disable) {'),
    ('expected-original-only', 'if (observed == expected)', 'if (observed == request->value)'),
    ('counter-lost', 'state->pref64_writes++;', 'state->pref64_writes += 0;'),
    ('counter-unscoped', 'if (state->pref64_disable && n71_pref64_disable_request(request))',
     'if (state->pref64_disable)'),
    ('readback-compares-original', 'error = actual == expected ? 0 : -EIO;',
     'error = actual == request->value ? 0 : -EIO;'),
    ('readback-accepts-original-or-typed', 'error = actual == expected ? 0 : -EIO;',
     'error = actual == expected || actual == request->value ? 0 : -EIO;'),
    ('expected-failure-lost', 'failure.expected = expected;', 'failure.expected = request->value;'),
)


class Pref64PolicyTests(unittest.TestCase):
    def test_policy_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel' / HEADER).read_text()
        with tempfile.TemporaryDirectory(prefix='n71-pref64-policy-') as directory:
            folder = Path(directory)
            binary = folder / 'policy'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before is not None:
                    self.assertEqual(source.count(before), 1, 'Mutation anchor: ' + name)
                (folder / HEADER).write_text(source if before is None else source.replace(before, after, 1))
                p = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                                    '-I', str(folder), '-I', str(ROOT / 'phone/kernel'),
                                    str(ROOT / 'tests/n71_pcie_pref64_policy.c'), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0, 'Compilation failure is not a kill: ' + name + p.stderr)
                p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn('N71_PCIE_PREF64_POLICY_OK cases=20', p.stdout)
                    print(p.stdout.strip(), flush=True)
                else:
                    self.assertEqual(p.returncode, -6, 'Missing SIGABRT: ' + name + p.stderr)
                    self.assertIn('assert', p.stderr.lower(), name)
                    print('N71_PREF64_POLICY_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
