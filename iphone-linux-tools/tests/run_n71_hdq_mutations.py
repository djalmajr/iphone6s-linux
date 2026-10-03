#!/usr/bin/env python3
"""Require successfully built HDQ mutations to die by a C assertion."""
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'phone/kernel/n71-hdq-codec.h'
MUTATIONS = (
    ('a10-rx-threshold', 'symbols[bit] > 0xf8', 'symbols[bit] >= 0xf0'),
    ('rx-bit-order', 'value |= 1U << bit;', 'value |= 1U << (7 - bit);'),
    ('tx-zero-symbol', '? 0xfe : 0xc0;', '? 0xfe : 0x00;'),
    ('accept-long-frame', 'length != N71_HDQ_BYTE_SYMBOLS', 'length < N71_HDQ_BYTE_SYMBOLS'),
    ('accept-unstable-word', 'high_before != high_after',
     '(high_before != high_after && high_after == 0)'),
    ('word-byte-order', '((u16)high_before << 8) | low', '((u16)low << 8) | high_before'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; unavailable compiler is not a passing gate.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = HEADER.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-hdq-mutations-') as directory:
        folder = Path(directory)
        header = folder / HEADER.name
        binary = folder / 'codec'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) == 0:
                raise ValueError('Mutation anchor absent: ' + name)
            header.write_text(source if before is None else source.replace(before, after, 1))
            built = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_hdq_codec.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if built.returncode:
                raise RuntimeError('Build failure is not a mutation kill: ' + name + built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_HDQ_CODEC_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -signal.SIGABRT or 'assert' not in result.stderr.lower():
                raise RuntimeError('Mutation lacks SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_HDQ_ASSERTION_KILL ' + name, flush=True)
    print('N71_HDQ_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
