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
    ('reset-trace-wiring', 'result->reset_trace = request->controller->reset_trace;', '(void)0;'),
    ('reset-trace-freshness', 'request->controller->reset_trace = (struct n71_i2c_reset_trace) {0};', '(void)0;'),
    ('reset-trace-marker', 'N71_I2C_RESET_TRACE attempts=', 'N71_I2C_RESET_HIDDEN attempts='),
    ('reset-trace-attempts', 'result.reset_trace.attempts,', '0U,'),
    ('reset-trace-samples', 'result.reset_trace.samples,', '0U,'),
    ('reset-trace-error', 'result.reset_trace.sample_error,', '0,'),
    ('reset-trace-first-ctl', 'result.reset_trace.first_ctl,', '0U,'),
    ('reset-trace-last-rev', 'result.reset_trace.words[N71_I2C_REV],', '0U,'),
    ('reset-trace-last-smsta', 'result.reset_trace.words[N71_I2C_SMSTA],', '0U,'),
    ('reset-trace-last-xfsta', 'result.reset_trace.words[N71_I2C_XFSTA],', '0U,'),
    ('reset-trace-last-imask', 'result.reset_trace.words[N71_I2C_IMASK],', '0U,'),
    ('reset-trace-last-ctl', 'result.reset_trace.words[N71_I2C_CTL]);', '0U);'),
    ('trace-wiring', '.trace = &result->trace', '.trace = NULL'),
    ('trace-freshness', '*result = (struct n71_i2c_configuration_result) {0};',
     '*result = (struct n71_i2c_configuration_result) {.trace = {.stage = 99}};'),
    ('trace-marker', 'N71_I2C_HDQ_TRACE stage=', 'N71_I2C_HDQ_HIDDEN stage='),
    ('trace-read-mode', 'if (read_control) {', 'if (true) {'),
    ('trace-primary-stage', 'result.trace.stage,', '0U,'),
    ('trace-primary-sampled', 'result.trace.sampled,', '0U,'),
    ('trace-primary-status', 'result.trace.status,', '0U,'),
    ('trace-cleanup-stage', 'result.trace.cleanup_stage,', '0U,'),
    ('trace-cleanup-sampled', 'result.trace.cleanup_sampled,', '0U,'),
    ('trace-cleanup-status', 'result.trace.cleanup_status);', '0U);'),
    ('stage-pins', 'result->stage = N71_I2C_STAGE_PINS;', 'result->stage = 0;'),
    ('stage-power', 'result->stage = N71_I2C_STAGE_POWER;', 'result->stage = 0;'),
    ('stage-controller', 'result->stage = N71_I2C_STAGE_CONTROLLER;', 'result->stage = 0;'),
    ('stage-hdq', 'result->stage = N71_I2C_STAGE_HDQ;', 'result->stage = 0;'),
    ('stage-complete', 'result->stage = N71_I2C_STAGE_COMPLETE;', 'result->stage = 0;'),
    ('stage-marker', 'N71_I2C_CONFIGURATION_STAGE stage=', 'N71_I2C_CONFIGURATION_HIDDEN stage='),
    ('early-action', 'if (!diagnostic_ready) {', 'if (false) {'),
    ('pending-new-cycle', 'if (!n71_diagnostic_clean() || diagnostic_retained) {', 'if (false) {'),
    ('pending-unpin', 'diagnostic_retained && n71_diagnostic_clean()', 'diagnostic_retained'),
    ('skip-cycle-release', 'cleanup_error = n71_i2c_power_release(&diagnostic_io, &diagnostic_state);', 'cleanup_error = 0;'),
    ('missing-retained-pin', '__module_get(THIS_MODULE);', 'if (false) __module_get(THIS_MODULE);'),
    ('missing-ephemeral-pin', 'if (!try_module_get(THIS_MODULE))', 'if (false && !try_module_get(THIS_MODULE))'),
    ('lose-primary-error', 'module_put(THIS_MODULE);\n\treturn error;', 'module_put(THIS_MODULE);\n\treturn 0;'),
    ('missing-consumer-release', 'root_device_unregister(diagnostic_backend.consumer);',
     'if (false) root_device_unregister(diagnostic_backend.consumer);'),
    ('missing-node-release', 'of_node_put(diagnostic_node);', '(void)diagnostic_node;'),
    ('ignore-initial-quiescence', 'error = n71_genpd_words(access, false);', 'error = 0;'),
    ('missing-action-lock', 'mutex_lock(&diagnostic_lock);\n\tif (!diagnostic_ready)',
     'if (false) mutex_lock(&diagnostic_lock);\n\tif (!diagnostic_ready)'),
    ('skip-inspect', 'if (inspect) {', 'if (false) {'),
    ('overwrite-inspect-error', 'if (!error)\n\t\t\t\terror = cleanup_error;', 'if (true)\n\t\t\t\terror = cleanup_error;'),
    ('skip-release-after-inspect-failure', 'cleanup_error = n71_i2c_power_release(&diagnostic_io, &diagnostic_state);',
     'cleanup_error = error ? 0 : n71_i2c_power_release(&diagnostic_io, &diagnostic_state);'),
    ('skip-configure', 'error = n71_diagnostic_configure(read_control);', 'error = false ? n71_diagnostic_configure(read_control) : 0;'),
    ('skip-controller-release', 'error = n71_i2c_controller_release(&ownership, request->controller);',
     'error = false ? n71_i2c_controller_release(&ownership, request->controller) : 0;'),
    ('skip-pin-release', 'error = n71_i2c_pin_owner_release(request->pins);',
     'error = false ? n71_i2c_pin_owner_release(request->pins) : 0;'),
    ('ignore-controller-pending', 'if (error || !n71_i2c_controller_clean(request->controller))', 'if (false)'),
    ('ignore-pin-pending', 'if (error || !n71_i2c_pin_owner_clean(request->pins))', 'if (false)'),
    ('skip-hdq-read', 'result->error = n71_i2c_read_hdq_control(&read, request->read, &result->value);',
     'result->error = false ? n71_i2c_read_hdq_control(&read, request->read, &result->value) : 0;'),
    ('fake-validity', 'result->value_valid = !result->error;', 'result->value_valid = true;'),
    ('skip-transfer-cleanup', 'error = n71_i2c_hdq_read_cleanup(&read, request->read);',
     'error = false ? n71_i2c_hdq_read_cleanup(&read, request->read) : 0;'),
    ('ignore-transfer-pending', 'if (error || request->read->cleanup_pending || request->read->controller)', 'if (false)'),
)


class N71I2CControlTests(unittest.TestCase):
    def test_real_caller_failures_retained_refs_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        sources = {name: (ROOT / 'phone/kernel' / name).read_text() for name in (
            'n71-i2c-power-diagnostic.c', 'n71-i2c-configuration.h')}
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
            for name in ('i2c', 'pm_domain', 'pm_runtime', 'module', 'mutex', 'string', 'io', 'ioport', 'of_address'):
                (folder / 'linux' / (name + '.h')).write_text('/* Kernel APIs supplied by harness. */\n')
            for name in ('n71-i2c-genpd.h', 'n71-i2c-power-lifecycle.h', 'n71-pmgr-access.h',
                         'n71-i2c-controller-observe.h', 'n71-i2c-controller.h', 'n71-i2c-pin-owner.h',
                         'n71-i2c-hdq-read.h', 'n71-i2c-hdq-trace.h'):
                (folder / name).write_bytes((ROOT / 'phone/kernel' / name).read_bytes())
            (folder / 'n71_i2c_genpd_fixture.c').write_text(fixture)
            binary = folder / 'caller'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                for filename, source in sources.items():
                    (folder / filename).write_text(source)
                if before:
                    owners = [filename for filename, source in sources.items() if source.count(before) == 1]
                    self.assertEqual(len(owners), 1, name)
                    filename = owners[0]
                    (folder / filename).write_text(sources[filename].replace(before, after, 1))
                compiled = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                           '-I', str(folder), str(ROOT / 'tests/n71_i2c_power_diagnostic.c'),
                                           '-o', str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_I2C_CALLER_OK cases=', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_I2C_CALLER_ASSERTION_KILL ' + name, flush=True)
            print('N71_I2C_CALLER_MUTATION_GATE_OK count=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
