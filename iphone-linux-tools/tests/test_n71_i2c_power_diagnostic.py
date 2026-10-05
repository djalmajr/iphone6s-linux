"""Compile the real caller; retain objects/module ownership on failed cleanup."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('early-action', 'if (!diagnostic_ready) {', 'if (false) {'),
    ('pending-new-cycle', 'if (!n71_diagnostic_clean() || diagnostic_retained) {', 'if (false) {'),
    ('pending-unpin', 'diagnostic_retained && n71_diagnostic_clean()', 'diagnostic_retained'),
    ('skip-cycle-release', 'if (!error)\n\t\t\terror = n71_i2c_power_release', 'if (false)\n\t\t\terror = n71_i2c_power_release'),
    ('missing-retained-pin', '__module_get(THIS_MODULE);', 'if (false) __module_get(THIS_MODULE);'),
    ('missing-ephemeral-pin', 'if (!try_module_get(THIS_MODULE))', 'if (false && !try_module_get(THIS_MODULE))'),
    ('lose-primary-error', 'module_put(THIS_MODULE);\n\treturn error;', 'module_put(THIS_MODULE);\n\treturn 0;'),
    ('missing-consumer-release', 'root_device_unregister(diagnostic_backend.consumer);',
     'if (false) root_device_unregister(diagnostic_backend.consumer);'),
    ('missing-node-release', 'of_node_put(diagnostic_node);', '(void)diagnostic_node;'),
    ('ignore-initial-quiescence', 'error = n71_genpd_words(access, false);', 'error = 0;'),
    ('missing-action-lock', 'mutex_lock(&diagnostic_lock);\n\tif (!diagnostic_ready)',
     'if (false) mutex_lock(&diagnostic_lock);\n\tif (!diagnostic_ready)'),
)


class N71I2CControlTests(unittest.TestCase):
    def test_real_caller_failures_retained_refs_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-i2c-power-diagnostic.c').read_text()
        fixture = (ROOT / 'tests/n71_i2c_genpd.c').read_text().replace('int main(void)', 'int genpd_fixture_main(void)')
        original = 'static const struct { unsigned int offset; } n71_domains[] = {{0x801a0}, {0x80158}, {0x80150}};'
        self.assertEqual(fixture.count(original), 1)
        fixture = fixture.replace(original, '''static const struct { unsigned int offset; const char *path; } n71_domains[] = {
{0x801a0, "/soc/power-management@20e000000/power-controller@801a0"},
{0x80158, "/soc/power-management@20e000000/power-controller@80158"},
{0x80150, "/soc/power-management@20e000000/power-controller@80150"}};''')
        attachment = 'assert(!virtual_device.refs); virtual_device.refs=1; virtual_device.registered=true;'
        self.assertEqual(fixture.count(attachment), 1)
        # Each attach allocates a new virtual device; do not reuse a detached RPM state.
        fixture = fixture.replace(attachment, 'memset(&virtual_device.power,0,sizeof(virtual_device.power)); ' + attachment)
        with tempfile.TemporaryDirectory(prefix='n71-i2c-caller-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('i2c', 'pm_domain', 'pm_runtime', 'module', 'mutex', 'string'):
                (folder / 'linux' / (name + '.h')).write_text('/* Kernel APIs supplied by harness. */\n')
            for name in ('n71-i2c-genpd.h', 'n71-i2c-power-lifecycle.h', 'n71-pmgr-access.h'):
                (folder / name).write_bytes((ROOT / 'phone/kernel' / name).read_bytes())
            (folder / 'n71_i2c_genpd_fixture.c').write_text(fixture)
            module, binary = folder / 'n71-i2c-power-diagnostic.c', folder / 'caller'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                module.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                           '-I', str(folder), str(ROOT / 'tests/n71_i2c_power_diagnostic.c'),
                                           '-o', str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_I2C_CALLER_OK cases=39', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_I2C_CALLER_ASSERTION_KILL ' + name, flush=True)
            print('N71_I2C_CALLER_MUTATION_GATE_OK count=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
