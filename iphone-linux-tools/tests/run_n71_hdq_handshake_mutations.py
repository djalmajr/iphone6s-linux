#!/usr/bin/env python3
"""Require successfully built HDQ handshake mutants to die by a C assertion."""
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'phone/kernel/n71-hdq-handshake.h'
MUTATIONS = (
    ('wrong-register', 'REGISTER 0x1dU', 'REGISTER 0x00U'),
    ('wrong-request', 'REGISTER, 0x04)', 'REGISTER, 0x06)'),
    ('wrong-final', 'REGISTER, 0x06)', 'REGISTER, 0x04)'),
    ('wrong-ack-bit', 'value & 0x20', 'value & 0x40'),
    ('extend-poll-budget', 'POLLS 100U', 'POLLS 101U'),
    ('accept-wide-status', 'value > 0xff', 'value > 0xffff'),
    ('skip-initial-write-error', 'if (error)\n\t\treturn error;', 'if (0)\n\t\treturn error;'),
    ('skip-read-error', 'if (error)\n\t\t\treturn error;', 'if (0)\n\t\t\treturn error;'),
    ('wrong-delay', 'io->delay_ms(io->context, 10);', 'io->delay_ms(io->context, 5);'),
    ('late-cleanup-pending', 'state->cleanup_required = true;', 'state->cleanup_required = false;'),
    ('drop-reentry-check', 'if (state->cleanup_required)', 'if (false)'),
    ('ignore-final-error', 'return error;\n\t\t}', 'return 0;\n\t\t}'),
    ('drop-final-write', 'if (!final_write)', 'if (!final_write || final_write)'),
    ('retain-stale-ack', 'state->acknowledged = false;', ';'),
    ('retain-stale-final', 'state->final_write_accepted = false;', ';'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; gate not passed.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = HEADER.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-hdq-handshake-mutations-') as directory:
        folder = Path(directory)
        binary = folder / 'contract'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            (folder / HEADER.name).write_text(
                source if before is None else source.replace(before, after, 1))
            built = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_hdq_handshake.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if built.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_HDQ_HANDSHAKE_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -signal.SIGABRT or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_HDQ_HANDSHAKE_ASSERTION_KILL ' + name, flush=True)
    print('N71_HDQ_HANDSHAKE_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
