"""Require compiled assertion failures for the measured PREF64 disable guards."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER = 'n71-pcie-pref64-disable.h'
MUTATIONS = (
    ('capture-types', 'lower != 0x00010001U ||', '((void)lower, false) ||'),
    ('capture-base-upper', '|| base_upper ||', '|| ((void)base_upper, false) ||'),
    ('capture-limit-upper', '|| limit_upper ?', '|| ((void)limit_upper, false) ?'),
    ('request-function', 'request->root &&', 'true &&'),
    ('request-register', 'request->where == 0x24 &&', 'true &&'),
    ('request-width', 'request->size == 4 &&', 'true &&'),
    ('request-value', 'request->value == 0x0000fff0;', 'true;'),
    ('observed-types-or-address', 'observed != 0x00010001U && observed != 0x0001fff1U', 'false'),
    ('disable-already-applied', 'observed != 0x00010001U && observed != 0x0001fff1U',
     'observed != 0x00010001U'),
    ('live-lower', 'if (actual != (index == 0 ? observed : 0U))',
     'if (index != 0 && actual != (index == 0 ? observed : 0U))'),
    ('live-base-upper', 'if (actual != (index == 0 ? observed : 0U))',
     'if (index != 1 && actual != (index == 0 ? observed : 0U))'),
    ('live-limit-upper', 'if (actual != (index == 0 ? observed : 0U))',
     'if (index != 2 && actual != (index == 0 ? observed : 0U))'),
    ('callback-error', 'if (error)\n\t\t\treturn error;', 'if (false)\n\t\t\treturn error;'),
    ('expected-types', '*expected = 0x0001fff1U;', '*expected = 0x0000fff0U;'),
    ('expected-address', '*expected = 0x0001fff1U;', '*expected = 0x0001ffe1U;'),
)


class Pref64DisableTests(unittest.TestCase):
    def test_helper_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel' / HEADER).read_text()
        with tempfile.TemporaryDirectory(prefix='n71-pref64-helper-') as directory:
            folder = Path(directory)
            binary = folder / 'helper'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before is not None:
                    self.assertEqual(source.count(before), 1, 'Mutation anchor: ' + name)
                (folder / HEADER).write_text(source if before is None else source.replace(before, after, 1))
                p = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                                    '-I', str(folder), '-I', str(ROOT / 'phone/kernel'),
                                    str(ROOT / 'tests/n71_pcie_pref64_disable.c'), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0, 'Compilation failure is not a kill: ' + name + p.stderr)
                p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn('N71_PCIE_PREF64_HELPER_OK cases=35', p.stdout)
                    print(p.stdout.strip(), flush=True)
                else:
                    self.assertEqual(p.returncode, -6, 'Missing SIGABRT: ' + name + p.stderr)
                    self.assertIn('assert', p.stderr.lower(), name)
                    print('N71_PREF64_HELPER_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
