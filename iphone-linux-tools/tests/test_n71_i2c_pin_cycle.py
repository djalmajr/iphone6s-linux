"""Execute the real GPIO cycle with faults; compiled mutations must assert."""
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
     '(false && !of_machine_is_compatible("apple,n71"))'),
    ('drop-disabled-status', 'strcmp(status, "disabled")', 'false'),
    ('drop-children', 'of_get_child_count(node)', '(false && of_get_child_count(node))'),
    ('wrong-i2c-base', '0x20a111000ULL', '0x20a110000ULL'),
    ('wrong-gpio-base', '0x20f100000ULL', '0x20f110000ULL'),
    ('wrong-pin-count', 'npins != 208', 'npins != 209'),
    ('drop-provider-node', 'provider->dev.of_node != gpio', 'false'),
    ('drop-provider-lock', 'device_lock(&provider->dev);', '(void)device_lock;'),
    ('drop-label-identity', 'label_device != gdev', 'false'),
    ('wrong-pins', '{115, 114}', '{114, 115}'),
    ('drop-descriptor-identity', 'descriptors[index] != expected', 'false'),
    ('drop-hardware-offset', 'gpiod_hwgpio(descriptors[index]) != pins[index]',
     '(false && gpiod_hwgpio(descriptors[index]) != pins[index])'),
    ('drop-cache-consistency', 'values[0] != values[1]', 'false'),
    ('drop-stability', 'values[1] != values[2]', 'false'),
    ('drop-after-cache-consistency', 'values[2] != values[3]', 'false'),
    ('wrong-peripheral-mask', '(values[1] & 0x260) != 0x220', 'false'),
    ('ignore-pad-drift', 'words[0] != expected[0] || words[1] != expected[1]',
     'false && (words[0] != expected[0] || words[1] != expected[1])'),
    ('skip-release', 'gpiod_put(descriptors[index - 1]);', '(void)gpiod_put;'),
    ('skip-lookup-remove', 'gpiod_remove_lookup_table(lookup);', '(void)gpiod_remove_lookup_table;'),
    ('skip-root-unregister', 'root_device_unregister(consumer);', '(void)root_device_unregister;'),
    ('skip-second-cycle', 'cycle < 2;', 'cycle < 1;'),
    ('ignore-cleanup-error', 'return error ? error : cleanup_error;', 'return error;'),
)


class N71I2cPinCycleTests(unittest.TestCase):
    def test_real_module_scopes_readback_cleanup_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/i2c-pins/n71-i2c-pin-cycle.c').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-i2c-pins-') as directory:
            folder = Path(directory)
            for name in ('gpio/consumer', 'gpio/driver', 'gpio/machine', 'i2c', 'module',
                         'of_address', 'of_platform', 'platform_device', 'regmap', 'slab', 'string'):
                header = folder / 'linux' / (name + '.h')
                header.parent.mkdir(parents=True, exist_ok=True)
                header.write_text('/* Kernel API contracts supplied by harness. */\n')
            module, binary = folder / 'n71-i2c-pin-cycle.c', folder / 'pin-cycle'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                module.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(folder),
                     str(ROOT / 'tests/n71_i2c_pin_cycle.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_I2C_PIN_CYCLE_OK cases=', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_I2C_PIN_CYCLE_ASSERTION_KILL ' + name, flush=True)
            print('N71_I2C_PIN_CYCLE_MUTATION_GATE_OK count=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
