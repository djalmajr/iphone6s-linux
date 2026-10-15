"""Real MMIO observer contracts; compiled mutations must fail by assertion."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('missing-active', '!power->active ||', 'false ||'),
    ('missing-attached', '!power->attached ||', 'false ||'),
    ('missing-usage', '!power->usage_held ||', 'false ||'),
    ('missing-obligation', '!power->cleanup_pending)', 'false)'),
    ('wrong-resource-base', 'resource.start != 0x20a111000ULL', 'false'),
    ('wrong-resource-size', 'resource_size(&resource) != 0x1000', 'false'),
    ('wrong-resource-type', 'resource_type(&resource) != IORESOURCE_MEM', 'false'),
    ('ignore-busy-region', 'if (!request_mem_region_exclusive(', 'if (false && !request_mem_region_exclusive('),
    ('ignore-map-failure', 'if (!base) {', 'if (false) {'),
    ('read-fifo', '{0x28, 0x14, 0x0c}', '{0x28, 0x14, 0x04}'),
    ('missing-second-sample', 'sample < 2;', 'sample < 1;'),
    ('missing-unmap', 'iounmap(base);', 'if (false) iounmap(base);'),
    ('missing-region-release', 'release_mem_region(resource.start, resource_size(&resource));',
     'if (false) release_mem_region(resource.start, resource_size(&resource));'),
    ('ignore-all-ones', 'error = -ENODEV;', 'error = 0;'),
    ('ignore-instability', 'result->stable = false;', 'result->stable = true;'),
    ('ignore-transfer', '(1U << 28) |', '0 |'),
    ('ignore-rx-data', '(1U << 19) |', '0 |'),
    ('ignore-empty-tx', '&& (status & (1U << 16))', '&& true'),
)


class N71I2CControllerTests(unittest.TestCase):
    def test_read_bounds_ownership_cleanup_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-i2c-controller-observe.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-i2c-observer-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('io', 'ioport', 'of_address'):
                (folder / 'linux' / (name + '.h')).write_text('/* Kernel APIs supplied by harness. */\n')
            (folder / 'n71-i2c-power-lifecycle.h').write_bytes(
                (ROOT / 'phone/kernel/n71-i2c-power-lifecycle.h').read_bytes())
            header, binary = folder / 'n71-i2c-controller-observe.h', folder / 'observer'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                           '-I', str(folder), str(ROOT / 'tests/n71_i2c_controller_observe.c'),
                                           '-o', str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_I2C_CONTROLLER_OK cases=37', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_I2C_CONTROLLER_ASSERTION_KILL ' + name, flush=True)
            print('N71_I2C_CONTROLLER_MUTATION_GATE_OK count=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
