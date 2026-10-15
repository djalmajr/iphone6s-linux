"""Exercise actual PMGR observation; require assertion-killed boundary mutations."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('drop-board', '!of_machine_is_compatible("apple,n71")',
     '(!of_machine_is_compatible("apple,n71") && false)'),
    ('drop-resource-base', 'resource.start != 0x20e000000ULL',
     '(resource.start != 0x20e000000ULL && false)'),
    ('drop-resource-size', 'resource_size(&resource) != 0x8c000',
     '(resource_size(&resource) != 0x8c000 && false)'),
    ('allow-parent-clock', 'of_find_property(pmgr, "clocks", NULL)',
     '(of_find_property(pmgr, "clocks", NULL) && false)'),
    ('wrong-domain-offset', 'reg[0] != n71_domains[index].offset',
     '(reg[0] != n71_domains[index].offset && false)'),
    ('wrong-parent', 'parent != pmgr', '(parent != pmgr && false)'),
    ('wrong-chain', 'domain.np != expected', '(domain.np != expected && false)'),
    ('drop-bound-driver', 'strcmp(provider->dev.driver->name, "apple-pmgr-pwrstate")',
     '(strcmp(provider->dev.driver->name, "apple-pmgr-pwrstate") && false)'),
    ('drop-provider-lock', 'device_lock(&provider->dev);', '(void)device_lock;'),
    ('read-other-register', 'n71_domains[index].offset, &words[0]',
     'n71_domains[index].offset + 4, &words[0]'),
    ('swallow-map-error', 'error = PTR_ERR(map);', 'error = 0;'),
    ('swallow-read-error', 'if (!error)\n\t\terror = regmap_read_bypassed',
     'if (error) error = 0;\n\tif (!error)\n\t\terror = regmap_read_bypassed'),
    ('partial-success-output', 'if (error)\n\t\t\tgoto put_pmgr;',
     'if (error) { pr_info("N71_PMGR_OBSERVED\\n"); goto put_pmgr; }'),
    ('leak-domain-ref', 'of_node_put(domain.np);', '(void)domain.np;'),
    ('leak-provider-ref', 'put_device(&provider->dev);', '(void)put_device; (void)provider;'),
    ('lie-stable', 'words[index][0] == words[index][1]', '1U'),
    ('reject-valid-last-index', 'reference->index >= 3', 'reference->index >= 2'),
    ('allow-open-handle-reentry', 'access->provider || access->map', 'false'),
    ('keep-unlocked-map', 'access->map = NULL;', '(void)access->map;'),
    ('keep-unlocked-provider', 'access->provider = NULL;', '(void)access->provider;'),
    ('ignore-domain-path', 'node != expected', '(node != expected && false)'),
    ('ignore-root-path', 'pmgr != expected', '(pmgr != expected && false)'),
)


class PmgrPowerObserveTests(unittest.TestCase):
    def test_real_module_faults_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        module_source = (ROOT / 'phone/kernel/n71-pmgr-power-observe.c').read_text()
        include = '#include "n71-pmgr-access.h"\n'
        self.assertEqual(module_source.count(include), 1)
        source = ((ROOT / 'phone/kernel/n71-pmgr-access.h').read_text() + '\n'
                  + module_source.replace(include, '', 1))
        with tempfile.TemporaryDirectory(prefix='n71-pmgr-observe-') as directory:
            folder = Path(directory)
            (folder / 'linux/mfd').mkdir(parents=True)
            for name in ('mfd/syscon', 'module', 'of_address', 'of_platform',
                         'platform_device', 'regmap', 'string'):
                (folder / 'linux' / (name + '.h')).write_text('/* Kernel API supplied by harness. */\n')
            module, binary = folder / 'n71-pmgr-power-observe.c', folder / 'observe'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                module.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(folder),
                     str(ROOT / 'tests/n71_pmgr_power_observe.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_PMGR_POWER_OBSERVE_OK cases=97', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_PMGR_ASSERTION_KILL ' + name, flush=True)
            print('N71_PMGR_MUTATION_GATE_OK count=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
