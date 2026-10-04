"""Compile the PMGR probe and reject publication after failed I/O."""
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
PATCH = ROOT / 'phone/kernel/patches/0005-apple-pmgr-probe-errors.patch'
METHODS = ('apple_pmgr_ps_set', 'apple_pmgr_ps_is_active', 'apple_pmgr_ps_power_on',
           'apple_pmgr_ps_power_off', 'apple_pmgr_reset_xlate', 'apple_pmgr_ps_probe')


def function(source, name):
    matches = list(re.finditer(r'static (?:int|bool) ' + re.escape(name)
                              + r'\([^;{}]*\)\n\{', source))
    if len(matches) != 1:
        raise ValueError('Function identity differs: ' + name)
    end = matches[0].end()
    depth = 1
    while end < len(source) and depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    if depth:
        raise ValueError('Incomplete function: ' + name)
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
        ('read-error-swallowed', METHODS[1], 'if (ret < 0)\n\t\treturn ret;',
         'if (ret < 0)\n\t\treturn 0;'),
        ('output-before-valid-read', METHODS[1], '\tret = regmap_read(',
         '\t*active = false;\n\tret = regmap_read('),
        ('auto-target-ignored', METHODS[1],
         'FIELD_GET(APPLE_PMGR_PS_TARGET, reg) == APPLE_PMGR_PS_ACTIVE', 'false'),
        ('min-error-swallowed', METHODS[5],
         'FIELD_PREP(APPLE_PMGR_PS_MIN, ps->min_state));\n\t\tif (ret < 0)\n\t\t\treturn ret;',
         'FIELD_PREP(APPLE_PMGR_PS_MIN, ps->min_state));\n\t\tif (ret < 0)\n\t\t\treturn 0;'),
        ('state-error-swallowed-by-probe', METHODS[5],
         'ret = apple_pmgr_ps_is_active(ps, &active);\n\tif (ret < 0)\n\t\treturn ret;',
         'ret = apple_pmgr_ps_is_active(ps, &active);\n\tif (ret < 0)\n\t\treturn 0;'),
        ('always-on-error-ignored', METHODS[5],
         'ret = apple_pmgr_ps_power_on(&ps->genpd);\n\t\t\tif (ret < 0)\n\t\t\t\treturn ret;',
         'ret = apple_pmgr_ps_power_on(&ps->genpd);\n\t\t\t(void)ret;'),
        ('auto-pm-error-swallowed', METHODS[5],
         'APPLE_PMGR_AUTO_ENABLE);\n\t\tif (ret < 0)\n\t\t\treturn ret;',
         'APPLE_PMGR_AUTO_ENABLE);\n\t\tif (ret < 0)\n\t\t\treturn 0;'),
        ('min-clobbers-reset', METHODS[5], 'APPLE_PMGR_FLAGS | APPLE_PMGR_PS_MIN,',
         'APPLE_PMGR_FLAGS | APPLE_PMGR_PS_MIN | APPLE_PMGR_RESET,'),
        ('wrong-domain-offset', METHODS[5], 'ps->genpd.flags |= GENPD_FLAG_IRQ_SAFE;',
         'ps->offset = 4; ps->genpd.flags |= GENPD_FLAG_IRQ_SAFE;'),
        ('irq-safe-flag-dropped', METHODS[5], 'ps->genpd.flags |= GENPD_FLAG_IRQ_SAFE;',
         'ps->genpd.flags |= 0;'),
        ('missing-min-property-refused', METHODS[5],
         'ret = of_property_read_u32(node, "apple,min-state", &ps->min_state);',
         'ret = of_property_read_u32(node, "apple,min-state", &ps->min_state);\n\tif (ret) return ret;'),
        ('domain-before-io', METHODS[5],
         'ret = of_property_read_u32(node, "apple,min-state", &ps->min_state);',
         'pm_genpd_init(&ps->genpd, NULL, true);\n\tret = of_property_read_u32(node, "apple,min-state", &ps->min_state);'),
    )
    for name, method, before, after in changes:
        yield name, mutation(source, method, before, after)


class PmgrProbeTests(unittest.TestCase):
    def test_actual_probe_faults_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = patch_source()
        variants = [('baseline', source), ('original-regression', patch_source(original=True))]
        variants += list(mutations(source))
        with tempfile.TemporaryDirectory(prefix='n71-pmgr-probe-') as directory:
            folder = Path(directory)
            binary = folder / 'probe'
            for name, modified in variants:
                (folder / 'n71-pmgr-probe-functions.h').write_text(modified)
                old_api = 'static bool apple_pmgr_ps_is_active' in modified
                built = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                     '-DN71_NEW_ACTIVE_API=' + str(int(not old_api)), '-I', str(folder),
                     str(ROOT / 'tests/n71_pmgr_probe.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
                self.assertEqual(built.returncode, 0,
                                 name + ': compilation error is not mutation proof: ' + built.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True,
                                        cwd=folder, timeout=10, env=dict(os.environ, LC_ALL='C'))
                if name == 'baseline':
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_PMGR_PROBE_OK cases=3138', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_PMGR_PROBE_ASSERTION_KILL ' + name, flush=True)
        print('N71_PMGR_PROBE_MUTATION_GATE_OK count=12', flush=True)


if __name__ == '__main__':
    unittest.main()
