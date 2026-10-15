#!/usr/bin/env python3
"""Compile lifecycle regressions and require assertion deaths, never build errors."""
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'phone/kernel/n71-i2c-power-lifecycle.h'
MUTATIONS = (
    ('late-cleanup', 'state->cleanup_pending = true;\n\terror = io->resume_and_get',
     'state->cleanup_pending = false;\n\terror = io->resume_and_get'),
    ('lose-usage', 'state->usage_held = true;', 'state->usage_held = false;'),
    ('duplicate-put-on-retry', 'state->usage_held = false;', 'state->usage_held = true;'),
    ('wrong-zero-usage-retry', 'error = io->suspend_zero_usage(io->context);',
     'error = io->put_and_suspend(io->context);'),
    ('skip-active-proof', 'error = io->verify_active(io->context);', 'error = 0;'),
    ('skip-quiescent-proof', 'error = io->verify_quiescent(io->context);', 'error = 0;'),
    ('ignore-detach-failure', 'error = io->detach_verified(io->context);',
     'io->detach_verified(io->context); error = 0;'),
    ('overwrite-primary-error', 'n71_i2c_power_release(io, state);\n\treturn error;',
     'return n71_i2c_power_release(io, state);'),
    ('skip-failure-cleanup', 'n71_i2c_power_release(io, state);\n\treturn error;',
     'return error;'),
    ('clear-pending-on-error', 'state->cleanup_error = error < 0 ? error : -EIO;',
     'state->cleanup_pending = false; state->cleanup_error = error < 0 ? error : -EIO;'),
    ('ignore-reentry', 'state->active || state->attached || state->cleanup_pending || state->usage_held',
     'false'),
    ('positive-suspend-is-error', 'if (error < 0)\n\t\tgoto pending;',
     'if (error != 0)\n\t\tgoto pending;'),
    ('accept-positive-verification', 'if (error > 0)\n\t\t\terror = -EIO;',
     'if (error > 0)\n\t\t\terror = 0;'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; no passing gate.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = HEADER.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-i2c-lifecycle-') as directory:
        folder = Path(directory)
        binary = folder / 'contract'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            (folder / HEADER.name).write_text(
                source if before is None else source.replace(before, after, 1))
            built = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_i2c_power_lifecycle.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if built.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_I2C_POWER_LIFECYCLE_OK cases=12' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stdout + result.stderr)
                print(result.stdout.strip(), flush=True)
            elif result.returncode != -signal.SIGABRT or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_I2C_POWER_LIFECYCLE_ASSERTION_KILL ' + name, flush=True)
    print('N71_I2C_POWER_LIFECYCLE_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
