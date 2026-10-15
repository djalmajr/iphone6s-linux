#!/usr/bin/env python3
"""Reject S8000 mutations only after a successful build and C assertion."""
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'phone/kernel/n71-pcie-contract.h'
MUTATIONS = (
    ('resource-index', 'out->port = 2 * port + 1;', 'out->port = 2 * port + 2;'),
    ('a10-selector', 'value = 0x24;', 'value = 0x28;'),
    ('wrong-port-stride', 'port * 0x80', 'port * 0x100'),
    ('clear-unrelated', '(old & ~mask)', '(old & mask)'),
    ('inverted-polarity', 'enabled != inverted', 'enabled == inverted'),
    ('accept-out-of-range', 'port >= N71_PCIE_PORT_COUNT', 'port > N71_PCIE_PORT_COUNT'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; missing compiler is not a passing gate.')
    # Assertion deaths must not leave core dumps on the Mac or CI runner.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = HEADER.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-pcie-mutations-') as directory:
        folder = Path(directory)
        header = folder / HEADER.name
        binary = folder / 'contract'
        cases = (('baseline', None, None),) + MUTATIONS
        for name, before, after in cases:
            if before is not None and source.count(before) == 0:
                raise ValueError('Mutation anchor absent: ' + name)
            header.write_text(source if before is None else source.replace(before, after, 1))
            compiled = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_pcie_contract.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if compiled.returncode:
                raise RuntimeError('Compilation failed, not a mutation kill: ' + name + compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_PCIE_PRIMITIVES_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -6 or 'assert' not in result.stderr.lower():
                raise RuntimeError('Mutation lacks SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_PCIE_ASSERTION_KILL ' + name, flush=True)
    print('N71_PCIE_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
