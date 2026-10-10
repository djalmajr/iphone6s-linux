"""Fault-inject the real passive I2C1 module; compiled mutations must assert."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('drop-board', '!of_machine_is_compatible("apple,n71")',
     '(!of_machine_is_compatible("apple,n71") && false)'),
    ('drop-disabled-status', 'strcmp(status, "disabled")', 'false'),
    ('drop-child-refusal', 'of_get_child_count(node)', '(of_get_child_count(node) && false)'),
    ('drop-resource-base', 'resource.start != base', '(resource.start != base && false)'),
    ('wrong-irq-scope', 'irq.args[1] != 207', 'irq.args[1] != 197'),
    ('drop-pin-parent', 'parent != gpio', '(parent != gpio && false)'),
    ('confuse-unit-name-with-path', 'expected && node == expected',
     'expected && !strcmp(node->full_name, path)'),
    ('accept-existing-platform', 'error = -EBUSY;\n\t\tgoto put_node;\n\t}\n\tadapter',
     'error = 0;\n\t\tgoto put_node;\n\t}\n\tadapter'),
    ('drop-provider-lock', 'device_lock(&provider->dev);', '(void)device_lock;'),
    ('wrong-pin-offset', '(114 + pin) * 4', '(113 + pin) * 4'),
    ('cache-instead-of-hardware', 'regmap_read_bypassed(map, offset, &words[pin][1])',
     'regmap_read(map, offset, &words[pin][1])'),
    ('swallow-first-read-error', 'if (!error)\n\t\t\terror = regmap_read_bypassed(map, offset, &words[pin][1]);',
     'if (error) error = 0;\n\t\tif (!error)\n\t\t\terror = regmap_read_bypassed(map, offset, &words[pin][1]);'),
    ('leak-domain-ref', 'of_node_put(domain.np);', '(void)domain.np;'),
    ('leak-provider-ref', 'put_device(&provider->dev);', '(void)provider;'),
    ('early-success', 'if (error)\n\t\t\tgoto unlock;',
     'if (error) { pr_info("N71_I2C1_OBSERVED\\n"); goto unlock; }'),
)


class I2cTopologyObserveTests(unittest.TestCase):
    def test_real_module_faults_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-i2c-topology-observe.c').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-i2c-observe-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('i2c', 'module', 'of_address', 'of_irq', 'of_platform',
                         'platform_device', 'regmap', 'string'):
                (folder / 'linux' / (name + '.h')).write_text('/* Kernel API supplied by harness. */\n')
            module, binary = folder / 'n71-i2c-topology-observe.c', folder / 'observe'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                module.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(folder),
                     str(ROOT / 'tests/n71_i2c_topology_observe.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_I2C_TOPOLOGY_OBSERVE_OK cases=86', result.stdout)
                    print(result.stdout.strip())
                else:
                    self.assertEqual(result.returncode, -6, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
            print('N71_I2C_TOPOLOGY_MUTATIONS_OK count=' + str(len(MUTATIONS)))


if __name__ == '__main__':
    unittest.main()
