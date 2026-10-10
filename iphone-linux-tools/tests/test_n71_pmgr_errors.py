"""Compile patched PMGR callbacks and reject swallowed I/O failures."""
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'phone/kernel/patches/0004-apple-pmgr-errors.patch'
METHODS = ('apple_pmgr_ps_set', 'apple_pmgr_reset_assert',
           'apple_pmgr_reset_deassert', 'apple_pmgr_reset_reset', 'apple_pmgr_reset_status')


def function(source, name):
    matches = list(re.finditer(r'static int ' + re.escape(name) + r'\([^;{}]*\)\n\{', source))
    if len(matches) != 1:
        raise ValueError('Function identity differs: ' + name)
    end = matches[0].end()
    depth = 1
    while end < len(source) and depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    if depth:
        raise ValueError('Incomplete patch function: ' + name)
    return source[matches[0].start():end]


def patch_source(*, original=False):
    lines = PATCH.read_text().splitlines()
    target = 'drivers/pmdomain/apple/pmgr-pwrstate.c'
    if lines[:2] != ['--- a/' + target, '+++ b/' + target]:
        raise ValueError('Unexpected patch target.')
    prefix = (' ', '-') if original else (' ', '+')
    source = '\n'.join(line[1:] for line in lines[2:] if line.startswith(prefix))
    defines = '\n'.join(line for line in source.splitlines() if line.startswith('#define APPLE_PMGR_'))
    if len(defines.splitlines()) != 16:
        raise ValueError('Incomplete provider constants.')
    return defines + '\n\n' + '\n\n'.join(function(source, name) for name in METHODS) + '\n'


def mutation(source, method, before, after):
    original = function(source, method)
    if original.count(before) != 1:
        raise ValueError('Mutation anchor differs: ' + method)
    return source.replace(original, original.replace(before, after, 1), 1)


def mutations(source):
    changes = (
        ('first-write-swallowed', METHODS[0],
         'ret = regmap_write(ps->regmap, ps->offset, reg);\n\tif (ret < 0)\n\t\treturn ret;',
         'ret = regmap_write(ps->regmap, ps->offset, reg);\n\tif (ret < 0)\n\t\treturn 0;'),
        ('poll-error-continues', METHODS[0],
         '\t\t\tgenpd->name, pstate, reg);\n\t\treturn ret;',
         '\t\t\tgenpd->name, pstate, reg);'),
        ('auto-write-swallowed', METHODS[0], '\t\tret = regmap_write(', '\t\tregmap_write('),
        ('power-wrong-offset', METHODS[0],
         '\n\tret = regmap_write(ps->regmap, ps->offset, reg);',
         '\n\tret = regmap_write(ps->regmap, ps->offset + 4, reg);'),
        ('power-clobbers-reset', METHODS[0],
         'reg &= ~(APPLE_PMGR_AUTO_ENABLE | APPLE_PMGR_FLAGS | APPLE_PMGR_PS_TARGET);',
         'reg &= ~(APPLE_PMGR_AUTO_ENABLE | APPLE_PMGR_FLAGS | APPLE_PMGR_PS_TARGET | APPLE_PMGR_RESET);'),
        ('assert-continues-after-failure', METHODS[1], 'if (!ret)', 'if (true)'),
        ('assert-error-swallowed', METHODS[1], 'return ret;', 'return 0;'),
        ('deassert-continues-after-failure', METHODS[2], 'if (!ret)', 'if (true)'),
        ('deassert-error-swallowed', METHODS[2], 'return ret;', 'return 0;'),
        ('assert-unlocked', METHODS[1],
         'spin_lock_irqsave(&ps->genpd.slock, flags);', 'flags = 17;'),
        ('deassert-leaks-lock', METHODS[2],
         'spin_unlock_irqrestore(&ps->genpd.slock, flags);', '(void)flags;'),
        ('reset-error-swallowed', METHODS[3], 'if (ret)\n\t\treturn ret;',
         'if (ret)\n\t\treturn 0;'),
        ('reset-delay-before-assert', METHODS[3],
         'ret = apple_pmgr_reset_assert(rcdev, id);',
         'usleep_range(APPLE_PMGR_RESET_TIME, 2 * APPLE_PMGR_RESET_TIME);\n\tret = apple_pmgr_reset_assert(rcdev, id);'),
        ('status-error-swallowed', METHODS[4], 'if (ret < 0)\n\t\treturn ret;',
         'if (ret < 0)\n\t\treturn 0;'),
    )
    for name, method, before, after in changes:
        yield name, mutation(source, method, before, after)


class PmgrErrorTests(unittest.TestCase):
    def test_actual_callbacks_faults_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = patch_source()
        variants = [('baseline', source), ('original-regression', patch_source(original=True))]
        variants += list(mutations(source))
        with tempfile.TemporaryDirectory(prefix='n71-pmgr-errors-') as directory:
            folder = Path(directory)
            binary = folder / 'contract'
            for name, modified in variants:
                (folder / 'n71-pmgr-provider-functions.h').write_text(modified)
                built = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                     '-I', str(folder), str(ROOT / 'tests/n71_pmgr_errors.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
                self.assertEqual(built.returncode, 0,
                                 name + ': compilation error is not mutation proof: ' + built.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True,
                                        cwd=folder, timeout=10, env=dict(os.environ, LC_ALL='C'))
                if name == 'baseline':
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_PMGR_ERRORS_OK cases=492', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_PMGR_ERRORS_ASSERTION_KILL ' + name, flush=True)
        print('N71_PMGR_ERRORS_MUTATION_GATE_OK count=14', flush=True)


if __name__ == '__main__':
    unittest.main()
