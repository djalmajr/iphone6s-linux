"""Fixed SN2400-register transport contracts; no physical bus/gauge proof."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('trace-reset', 'trace', '*trace = (struct n71_i2c_hdq_trace){.stage = N71_HDQ_ARGUMENTS};', 'trace->stage = N71_HDQ_ARGUMENTS;'),
    ('trace-primary-stage', 'trace', 'trace->stage = stage;', 'trace->stage = 0;'),
    ('trace-cleanup-stage', 'trace', 'trace->cleanup_stage = stage;', 'trace->cleanup_stage = 0;'),
    ('trace-primary-status', 'trace', 'trace->status = status;', 'trace->status = 0;'),
    ('trace-cleanup-overwrites-primary', 'trace', 'trace->cleanup_status = status;', 'trace->cleanup_status = status; trace->status = status;'),
    ('trace-sampled', 'trace', 'trace->sampled = true;', 'trace->sampled = false;'),
    ('trace-cleanup-sampled', 'trace', 'trace->cleanup_sampled = true;', 'trace->cleanup_sampled = false;'),
    ('trace-stale-cleanup', 'trace', 'trace->cleanup_sampled = false;', 'trace->cleanup_sampled = true;'),
    ('trace-cleanup-erases-primary', 'trace', 'trace->cleanup_stage = N71_HDQ_C_ARGUMENTS;',
     '*trace = (struct n71_i2c_hdq_trace){.cleanup_stage = N71_HDQ_C_ARGUMENTS};'),
    ('trace-early-arguments', 'read', 'n71_hdq_trace_begin(trace, false);', 'if (false) n71_hdq_trace_begin(trace, false);'),
    ('trace-idle-cause', 'read', 'n71_hdq_trace_stage(trace, N71_HDQ_IDLE, false);', 'n71_hdq_trace_stage(trace, 0, false);'),
    ('trace-poll-cause', 'read', 'n71_hdq_trace_stage(trace, N71_HDQ_POLL, false);', 'n71_hdq_trace_stage(trace, 0, false);'),
    ('wrong-target', 'read', 'iowrite32(0x1ea,', 'iowrite32(0x1e8,'),
    ('wrong-register', 'read', 'iowrite32(0x1d,', 'iowrite32(0x1c,'),
    ('missing-stop', 'read', 'iowrite32(0x601,', 'iowrite32(0x401,'),
    ('missing-pending-before-write', 'read', 'controller->transfer_pending = true;', 'controller->transfer_pending = false;'),
    ('unchecked-interrupt-owner', 'read', 'words[N71_I2C_IMASK] ||', 'false ||'),
    ('unchecked-rx', 'read', 'if (value & ~0xffU)', 'if (false)'),
    ('missing-error-recovery-reset', 'read', 'iowrite32(0x70f,', 'if (false) iowrite32(0x70f,'),
    ('early-output-commit', 'read', 'error = n71_i2c_hdq_read_cleanup(request, state);\n\tif (error)\n\t\treturn error;\n\t*output = value;',
     '*output = value;\n\terror = n71_i2c_hdq_read_cleanup(request, state);\n\tif (error)\n\t\treturn error;'),
    ('replace-primary-error', 'read', 'n71_i2c_hdq_read_cleanup(request, state);\n\treturn error;',
     'error = n71_i2c_hdq_read_cleanup(request, state);\n\treturn error;'),
    ('premature-release', 'controller', 'if (state->transfer_pending) {', 'if (false) {'),
    ('invent-event-restore', 'controller', 'word == N71_I2C_SMSTA && state->status_acknowledged ?', 'false && word == N71_I2C_SMSTA && state->status_acknowledged ?'),
    ('reset-busy-bus', 'read', 'if (status & N71_I2C_HDQ_BUSY_FLAGS) {', 'if (false) {'),
)


class N71I2CHdqReadTests(unittest.TestCase):
    def test_fixed_read_recovery_retry_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        sources = {name: (ROOT / 'phone/kernel' / filename).read_text() for name, filename in (
            ('read', 'n71-i2c-hdq-read.h'), ('controller', 'n71-i2c-controller.h'), ('trace', 'n71-i2c-hdq-trace.h'))}
        with tempfile.TemporaryDirectory(prefix='n71-i2c-hdq-read-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('clk', 'delay', 'device', 'of', 'io', 'ioport', 'of_address'):
                (folder / 'linux' / (name + '.h')).write_text('/* APIs supplied by fixture. */\n')
            for name in ('n71-i2c-power-lifecycle.h', 'n71-i2c-controller-observe.h'):
                (folder / name).write_bytes((ROOT / 'phone/kernel' / name).read_bytes())
            paths = {'read': folder / 'n71-i2c-hdq-read.h', 'controller': folder / 'n71-i2c-controller.h',
                     'trace': folder / 'n71-i2c-hdq-trace.h'}
            binary = folder / 'hdq-read'
            for name, target, before, after in (('baseline', None, None, None),) + MUTATIONS:
                for key, path in paths.items():
                    path.write_text(sources[key])
                if before:
                    self.assertEqual(sources[target].count(before), 1, name)
                    paths[target].write_text(sources[target].replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(folder),
                     str(ROOT / 'tests/n71_i2c_hdq_read.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_I2C_HDQ_READ_OK cases=', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_I2C_HDQ_READ_ASSERTION_KILL ' + name, flush=True)
            print('N71_I2C_HDQ_READ_GATE_OK mutations=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
