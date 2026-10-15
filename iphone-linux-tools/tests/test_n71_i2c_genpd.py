"""Compile actual genpd backend; require assertion-killed ownership and state mutations."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('ignore-binding-lifetime', '!access[index].provider->dev.driver->suppress_bind_attrs', 'false'),
    ('ignore-controller', 'if (controller) {', 'if (controller && false) {'),
    ('ignore-adapter', 'if (adapter) {', 'if (adapter && false) {'),
    ('wrong-resource', 'resource.start != 0x20a111000ULL', 'false'),
    ('ignore-domain', 'domain.np != backend->references[0].node', 'false'),
    ('ignore-active-usage', 'atomic_read(&device->power.usage_count) == (active ? 1 : 0)', 'true'),
    ('ignore-runtime-error', '!device->power.runtime_error', 'true'),
    ('ignore-child-usage', '!atomic_read(&device->power.child_count)', 'true'),
    ('ignore-disabled', 'device->power.disable_depth == 1', 'device->power.disable_depth >= 1'),
    ('ignore-target', '(word & 0xfU) != 0xfU', 'false'),
    ('ignore-actual-auto', '((word & 0xf0U) != 0xf0U && !(word & 0x10000000U))', 'false'),
    ('ignore-reset-disable', 'word & 0x80000400U', 'word & 0U'),
    ('ignore-quiescence', 'word & 0x100000ffU', 'word & 0U'),
    ('ignore-second-sample', 'sample < 2', 'sample < 1'),
    ('missing-own-reference', 'backend->domain = get_device(domain);', 'backend->domain = domain;'),
    ('drop-detach-guard', 'domain->pm_domain || device_is_registered(domain)', 'false'),
    ('ignore-registered-after-detach', 'domain->pm_domain || device_is_registered(domain)', 'domain->pm_domain'),
    ('lose-retained-reference', 'put_device(domain);', '(void)domain;'),
    ('lose-failed-put-usage', 'pm_runtime_put_noidle(backend->domain);', '(void)backend->domain;'),
    ('ignore-external-usage', 'atomic_read(&backend->domain->power.usage_count) != 1', 'false'),
)


class N71GenpdTests(unittest.TestCase):
    def test_real_backend_failures_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-i2c-genpd.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-i2c-genpd-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('i2c', 'pm_domain', 'pm_runtime'):
                (folder / 'linux' / (name + '.h')).write_text('/* Kernel API supplied by harness. */\n')
            for name in ('n71-i2c-power-lifecycle.h', 'n71-pmgr-access.h'):
                (folder / name).write_bytes((ROOT / 'phone/kernel' / name).read_bytes())
            header, binary = folder / 'n71-i2c-genpd.h', folder / 'genpd'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    expected = 2 if name == 'lose-failed-put-usage' else 1
                    self.assertEqual(source.count(before), expected, name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(folder),
                     str(ROOT / 'tests/n71_i2c_genpd.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_I2C_GENPD_OK cases=87', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_GENPD_ASSERTION_KILL ' + name, flush=True)
            print('N71_GENPD_MUTATION_GATE_OK count=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
