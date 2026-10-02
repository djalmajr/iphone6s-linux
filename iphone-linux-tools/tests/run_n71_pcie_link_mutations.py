#!/usr/bin/env python3
"""Require successful compilation and assertion deaths for link regressions."""
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('gen2-instead-of-gen1', 'cap + 0x30, 0xf, 1)', 'cap + 0x30, 0xf, 2)'),
    ('wrong-secondary-bus', '0xffffff, 0x010100)', '0xffffff, 0x020200)'),
    ('wrong-ltssm-register', 'false, 0x80, 1, 1)', 'false, 0x84, 1, 1)'),
    ('accept-bus-master', 'value & 4)', 'value & 8)'),
    ('accept-ffff-vendor', '(endpoint & 0xffff) == 0xffff', '(endpoint & 0xffff) == 0xfffe'),
    ('leave-reset-released', 'cleanup = io->reset(io->context, true);',
     'cleanup = io->reset(io->context, false);'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; gate not passed.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = (ROOT / 'phone/kernel/n71-pcie-link.h').read_text()
    with tempfile.TemporaryDirectory(prefix='n71-link-mutations-') as directory:
        folder = Path(directory)
        for name in ('n71-pcie-contract.h', 'n71-pcie-init.h'):
            shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
        header = folder / 'n71-pcie-link.h'
        binary = folder / 'link'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            header.write_text(source if before is None else source.replace(before, after, 1))
            compiled = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_pcie_link.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if compiled.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_PCIE_LINK_SEQUENCE_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -6 or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_LINK_ASSERTION_KILL ' + name, flush=True)
    print('N71_LINK_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
