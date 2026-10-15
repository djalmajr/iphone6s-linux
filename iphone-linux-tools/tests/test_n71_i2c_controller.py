"""Owned clock/MMIO/reset/restore contracts; never physical charging proof."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('stale-reset-trace', 'state->reset_trace = (struct n71_i2c_reset_trace) {0};', '(void)0;'),
    ('reset-attempts', 'state->reset_trace.attempts = attempt + 1;', 'state->reset_trace.attempts = attempt;'),
    ('reset-sample-error', 'state->reset_trace.sample_error = error;', 'state->reset_trace.sample_error = 0;'),
    ('reset-first-sample', 'if (!state->reset_trace.samples)', 'if (true)'),
    ('reset-first-ctl', 'state->reset_trace.first_ctl = words[N71_I2C_CTL];', 'state->reset_trace.first_ctl = 0;'),
    ('reset-last-words', 'state->reset_trace.words[word] = words[word];', 'state->reset_trace.words[word] = 0;'),
    ('reset-valid-samples', 'state->reset_trace.samples++;', 'state->reset_trace.samples += 0;'),
    ('release-erases-trace', 'state->status_acknowledged = false;',
     'state->status_acknowledged = false; state->reset_trace = (struct n71_i2c_reset_trace) {0};'),
    ('missing-power-usage', 'power->usage_held &&', 'true &&'),
    ('wrong-mmio-scope', 'resource.start != 0x20a111000ULL', 'false'),
    ('multiple-clock-phandles', '"#clock-cells") != 1)', '"#clock-cells") < 1)'),
    ('wrong-clock-node', 'spec.np != expected ||', 'false ||'),
    ('unprotected-clock', 'state->clock_protected = true;', 'state->clock_protected = false;'),
    ('leaked-clock-enable', 'clk_disable_unprepare(state->clock);', 'if (false) clk_disable_unprepare(state->clock);'),
    ('foreign-interrupt-mask', '!words[N71_I2C_XFSTA] && !words[N71_I2C_IMASK]', '!words[N71_I2C_XFSTA]'),
    ('replay-reset-baseline', 'state->saved[N71_I2C_CTL] & ~0x1ffU', 'state->saved[N71_I2C_CTL] & ~0x7ffU'),
    ('reject-observed-ujm', 'state->saved[N71_I2C_CTL] & ~0x1ffU', 'state->saved[N71_I2C_CTL] & ~0xffU'),
    ('strip-ujm-restore', 'iowrite32(state->saved[N71_I2C_CTL],',
     'iowrite32(state->saved[N71_I2C_CTL] & 0xffU,'),
    ('missing-restore-obligation', 'state->restore_pending = true;', 'state->restore_pending = false;'),
    ('wrong-initial-divider', 'iowrite32(0x70f,', 'iowrite32(0x70e,'),
    ('skip-pins-before-write', 'error = n71_i2c_controller_pins(request);\n\tif (error)\n\t\tgoto failed;\n\tstate->restore_pending',
     'error = 0;\n\tif (error)\n\t\tgoto failed;\n\tstate->restore_pending'),
    ('ignore-restore-readback', 'for (word = 0; word < N71_I2C_WORDS; word++) {\n\t\t\tif (words[word] != n71_i2c_controller_expected(state, word)) {',
     'for (word = 0; word < N71_I2C_WORDS; word++) {\n\t\t\tif (false) {'),
    ('leaked-mapping', 'iounmap(state->base);', 'if (false) iounmap(state->base);'),
    ('extra-poll', 'attempt < 100;', 'attempt <= 100;'),
    ('replace-primary-error', 'n71_i2c_controller_release(request, state);\n\treturn error;',
     'error = n71_i2c_controller_release(request, state);\n\treturn error;'),
)


class N71I2CControllerTransactionTests(unittest.TestCase):
    def test_ownership_initialization_restore_retry_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-i2c-controller.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-i2c-controller-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('clk', 'delay', 'device', 'of', 'io', 'ioport', 'of_address'):
                (folder / 'linux' / (name + '.h')).write_text('/* APIs supplied by fixture. */\n')
            for name in ('n71-i2c-power-lifecycle.h', 'n71-i2c-controller-observe.h'):
                (folder / name).write_bytes((ROOT / 'phone/kernel' / name).read_bytes())
            header, binary = folder / 'n71-i2c-controller.h', folder / 'controller'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(folder),
                     str(ROOT / 'tests/n71_i2c_controller.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_I2C_CONTROLLER_TRANSACTION_OK cases=', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_I2C_CONTROLLER_TRANSACTION_ASSERTION_KILL ' + name, flush=True)
            print('N71_I2C_CONTROLLER_TRANSACTION_GATE_OK mutations=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
