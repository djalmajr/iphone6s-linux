"""Apply the real cleanup patch and reject leaked/unowned domain cleanup."""
import hashlib
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest
from test_n71_pmgr_probe import function, mutation

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'drivers/pmdomain/apple/pmgr-pwrstate.c'
BASE_SHA = '7ad9c93264edbf3e42400ff7d654e0c143db68f4500b196a8ae6ee260e43b5a4'
METHODS = ('apple_pmgr_ps_set', 'apple_pmgr_ps_is_active', 'apple_pmgr_ps_power_on',
           'apple_pmgr_ps_power_off', 'apple_pmgr_reset_xlate', 'apple_pmgr_ps_probe')
BACKENDS = '''#undef of_genpd_add_provider_simple
#undef pm_genpd_remove
#undef of_genpd_del_provider
#define of_genpd_add_provider_simple test_provider_add
#define pm_genpd_remove test_domain_remove
#define of_genpd_del_provider test_provider_del
'''


def predecessor():
    patch = ROOT / 'phone/kernel/patches/0005-apple-pmgr-probe-errors.patch'
    lines = patch.read_text().splitlines()
    if lines[:2] != ['--- a/' + TARGET, '+++ b/' + TARGET]:
        raise ValueError('Unexpected predecessor target.')
    source = '\n'.join(line[1:] for line in lines[2:] if line.startswith((' ', '+'))) + '\n'
    if hashlib.sha256(source.encode()).hexdigest() != BASE_SHA:
        raise ValueError('Complete predecessor source differs.')
    return source


def functions(source):
    defines = '\n'.join(line for line in source.splitlines() if line.startswith('#define APPLE_PMGR_'))
    if len(defines.splitlines()) != 16:
        raise ValueError('Incomplete provider constants.')
    return BACKENDS + defines + '\n\n' + '\n\n'.join(function(source, n) for n in METHODS) + '\n'


def mutations(source):
    method = 'apple_pmgr_ps_probe'
    changes = (
        ('skip-domain-cleanup', 'goto err_remove_domain;',
         'if (false) { goto err_remove_domain; }\n\t\treturn ret;'),
        ('delete-unowned-provider', 'goto err_remove_domain;',
         'if (false) { goto err_remove_domain; }\n\t\tgoto err_remove;'),
        ('drop-remove', 'pm_genpd_remove(&ps->genpd);', '(void)pm_genpd_remove;'),
        ('duplicate-remove', 'pm_genpd_remove(&ps->genpd);',
         'pm_genpd_remove(&ps->genpd); pm_genpd_remove(&ps->genpd);'),
        ('wrong-domain-scope', 'pm_genpd_remove(&ps->genpd);', 'pm_genpd_remove(&ps->genpd + 1);'),
        ('first-error-swallowed', 'pm_genpd_remove(&ps->genpd);\n\treturn ret;',
         'pm_genpd_remove(&ps->genpd);\n\treturn 0;'),
    )
    for name, before, after in changes:
        yield name, mutation(source, method, before, after)


class PmgrProviderFailureTests(unittest.TestCase):
    def test_real_patch_faults_and_compiled_mutations(self):
        compiler, git = shutil.which('cc'), shutil.which('git')
        self.assertIsNotNone(compiler, 'Native compiler required')
        self.assertIsNotNone(git, 'Git required for actual patch application')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        before = predecessor()
        with tempfile.TemporaryDirectory(prefix='n71-pmgr-provider-') as directory:
            folder = Path(directory)
            target = folder / TARGET
            target.parent.mkdir(parents=True)
            target.write_text(before)
            patch = ROOT / 'phone/kernel/patches/0006-apple-pmgr-provider-cleanup.patch'
            for args in (['--check'], []):
                subprocess.run([git, 'apply', *args, str(patch)], cwd=folder,
                               check=True, capture_output=True, timeout=15)
            source = target.read_text()
            variants = [('baseline', source), ('predecessor-regression', before)] + list(mutations(source))
            binary = folder / 'provider'
            for name, modified in variants:
                (folder / 'n71-pmgr-probe-functions.h').write_text(functions(modified))
                built = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                     '-DN71_NEW_ACTIVE_API=1', '-I', str(folder), '-I', str(ROOT / 'tests'),
                     str(ROOT / 'tests/n71_pmgr_provider_failure.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
                self.assertEqual(built.returncode, 0,
                                 name + ': compilation error is not mutation proof: ' + built.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True,
                                        cwd=folder, timeout=10, env=dict(os.environ, LC_ALL='C'))
                if name == 'baseline':
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_PMGR_PROVIDER_FAILURE_OK cases=3258', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_PMGR_PROVIDER_ASSERTION_KILL ' + name, flush=True)
        print('N71_PMGR_PROVIDER_MUTATION_GATE_OK count=6', flush=True)


if __name__ == '__main__':
    unittest.main()
