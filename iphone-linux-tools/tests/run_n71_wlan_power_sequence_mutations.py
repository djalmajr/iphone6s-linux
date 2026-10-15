#!/usr/bin/env python3
"""Require successfully built reversible REG_ON mutants to die by a C assertion."""
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'phone/kernel/n71-wlan-power.h'
MUTATIONS = (
    ('drop-cleanup', 'cleanup = n71_wlan_power_release(io, state);', 'cleanup = 0;'),
    ('late-pending', 'state->restore_pending = true;\n\terror = io->write',
     'state->restore_pending = false;\n\terror = io->write'),
    ('wrong-restore', 'state->original & 1, &restored', 'true, &restored'),
    ('ignore-owner', '(readback & 0xfe) != (state->original & 0xfe)', 'false'),
    ('ignore-activation-verification', 'observed != requested', 'false'),
    ('ignore-restore-verification', 'readback != state->original', 'false'),
    ('ignore-pending-guard', 'state->active || state->restore_pending', 'state->active'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; gate not passed.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = HEADER.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-wlan-power-mutations-') as directory:
        folder = Path(directory)
        (folder / 'n71-wlan-power-contract.h').write_text(
            (ROOT / 'phone/kernel/n71-wlan-power-contract.h').read_text())
        binary = folder / 'contract'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            (folder / HEADER.name).write_text(
                source if before is None else source.replace(before, after, 1))
            built = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_wlan_power_sequence.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if built.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_WLAN_POWER_SEQUENCE_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -signal.SIGABRT or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_REG_ON_SEQUENCE_ASSERTION_KILL ' + name, flush=True)
    print('N71_REG_ON_SEQUENCE_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
