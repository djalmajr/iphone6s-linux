#!/usr/bin/env python3
"""Require compiled assertion deaths for PCI inventory safety regressions."""
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('wrong-endpoint', 'result.identity != N71_PCIE_WLAN_ID',
     'result.identity != (N71_PCIE_WLAN_ID ^ (1U << 16))'),
    ('initial-master-allowed', '(result.command_status & 4)', '(result.command_status & 8)'),
    ('late-master-allowed', '(command & 4)', '(command & 8)'),
    ('bridge-header-allowed', '((result.header >> 16) & 0x7f)',
     '((result.header >> 16) & 0x7e)'),
    ('cycle-allowed', 'visited[pointer / 4])', 'visited[0])'),
    ('low-capability-pointer', 'pointer < 0x40', 'pointer < 0x3c'),
    ('changed-identity-allowed', 'identity != result.identity', 'identity == result.identity'),
    ('changed-command-allowed', '(command ^ result.command_status) & 0xffff',
     '(command ^ result.command_status) & 0xff00'),
    ('duplicate-msi-allowed', 'if (result.msi_offset)', 'if (result.msi_offset == 0xfc)'),
    ('premature-output',
     'error = n71_pcie_inventory_read(io, &result, 0, &result.identity);',
     '*out = result;\n\terror = n71_pcie_inventory_read(io, &result, 0, &result.identity);'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; gate not passed.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = (ROOT / 'phone/kernel/n71-pcie-inventory.h').read_text()
    with tempfile.TemporaryDirectory(prefix='n71-inventory-mutations-') as directory:
        folder = Path(directory)
        shutil.copyfile(ROOT / 'phone/kernel/n71-pcie-contract.h',
                        folder / 'n71-pcie-contract.h')
        header = folder / 'n71-pcie-inventory.h'
        binary = folder / 'inventory'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            header.write_text(source if before is None else source.replace(before, after, 1))
            compiled = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_pcie_inventory.c'),
                 '-o', str(binary)], capture_output=True, text=True, timeout=30,
                env=dict(os.environ, LC_ALL='C'))
            if compiled.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_PCIE_INVENTORY_READONLY_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -6 or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_INVENTORY_ASSERTION_KILL ' + name, flush=True)
    print('N71_INVENTORY_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
