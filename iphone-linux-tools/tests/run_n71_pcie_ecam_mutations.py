#!/usr/bin/env python3
"""Require assertion deaths for N71 config mapping and extraction regressions."""
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('wrong-root-slot', 'bus == 0 && devfn != 8', 'bus == 0 && devfn != 0'),
    ('wrong-endpoint-function', 'bus == 1 && devfn != 0', 'bus == 1 && devfn != 1'),
    ('root-offset-alias', 'bus == 0 ? 0x8000 : 0x100000', 'bus == 0 ? 0 : 0x100000'),
    ('wrong-endpoint-bus-offset', 'bus == 0 ? 0x8000 : 0x100000',
     'bus == 0 ? 0x8000 : 0x200000'),
    ('unaligned-dword-read', '(u32)where & ~3U', '(u32)where & ~1U'),
    ('wrong-byte-shift', '((u32)where & 3) * 8', '((u32)where & 3) * 4'),
    ('truncated-word', '(1U << (size * 8)) - 1', '(1U << (size * 4)) - 1'),
    ('cross-function-read', 'where > (int)(0x1000 - size)', 'where > 0x1000'),
    ('positive-callback-success', 'return error < 0 ? error : -EIO;',
     'return error < 0 ? error : 0;'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; gate not passed.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = (ROOT / 'phone/kernel/n71-pcie-ecam.h').read_text()
    with tempfile.TemporaryDirectory(prefix='n71-ecam-mutations-') as directory:
        folder = Path(directory)
        shutil.copyfile(ROOT / 'phone/kernel/n71-pcie-contract.h',
                        folder / 'n71-pcie-contract.h')
        header = folder / 'n71-pcie-ecam.h'
        binary = folder / 'ecam'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            header.write_text(source if before is None else source.replace(before, after, 1))
            compiled = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_pcie_ecam.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if compiled.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_PCIE_ECAM_READONLY_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -6 or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_ECAM_ASSERTION_KILL ' + name, flush=True)
    print('N71_ECAM_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
