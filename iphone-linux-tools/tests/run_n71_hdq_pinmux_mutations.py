#!/usr/bin/env python3
"""Require successfully built HDQ mux mutants to die by a C assertion."""
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'phone/kernel/n71-hdq-pinmux.h'
MUTATIONS = (
    ('wrong-pin', 'request->pin != 2', 'request->pin != 173'),
    ('packet-guard', 'request->flags != 0x102', 'request->flags != 0x202'),
    ('wide-packet', 'request->flags != 0x102', '(request->flags & 0xffff) != 0x102'),
    ('variant-boundary', 'request->glitchless > 1', 'request->glitchless > 2'),
    ('wrong-stride', 'out->offset = 0x08;', 'out->offset = 0x02;'),
    ('linux-only-mask', 'out->mask = 0x270;', 'out->mask = 0x260;'),
    ('clobber-pull', 'out->mask = 0x270;', 'out->mask = 0x3f0;'),
    ('reverse-branch', 'request->glitchless ? 0x210 : 0x220', 'request->glitchless ? 0x220 : 0x210'),
    ('missing-input', 'request->glitchless ? 0x210 : 0x220', 'request->glitchless ? 0x10 : 0x20'),
    ('assume-function-two', 'request->glitchless ? 0x210 : 0x220', 'request->glitchless ? 0x210 : 0x240'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; gate not passed.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = HEADER.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-hdq-pinmux-mutations-') as directory:
        folder = Path(directory)
        binary = folder / 'contract'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            (folder / HEADER.name).write_text(
                source if before is None else source.replace(before, after, 1))
            built = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_hdq_pinmux.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if built.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_HDQ_PINMUX_CONTRACT_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -signal.SIGABRT or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_HDQ_PINMUX_ASSERTION_KILL ' + name, flush=True)
    print('N71_HDQ_PINMUX_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
