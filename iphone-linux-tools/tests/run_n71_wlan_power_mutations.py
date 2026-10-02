#!/usr/bin/env python3
"""Require successfully built REG_ON mutants to die by a C assertion."""
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'phone/kernel/n71-wlan-power-contract.h'
MUTATIONS = (
    ('address-order', 'out[0] = N71_WLAN_REG_ON_REGISTER >> 8;',
     'out[0] = N71_WLAN_REG_ON_REGISTER & 0xff;'),
    ('wrong-register', '#define N71_WLAN_REG_ON_REGISTER 0x8fcU',
     '#define N71_WLAN_REG_ON_REGISTER 0x8f6U'),
    ('cross-register', 'reg != N71_WLAN_REG_ON_REGISTER', 'reg == 0'),
    ('accept-wide-byte', 'old > 0xff', 'old > 0xffff'),
    ('drive-mode', '(old & 0xd8)', '(old & 0xc0)'),
    ('clear-other-bit', '(old & ~1U)', '(old & ~3U)'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; gate not passed.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = HEADER.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-wlan-power-mutations-') as directory:
        folder = Path(directory)
        binary = folder / 'contract'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            (folder / HEADER.name).write_text(
                source if before is None else source.replace(before, after, 1))
            built = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_wlan_power.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if built.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_WLAN_POWER_CONTRACT_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -signal.SIGABRT or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_REG_ON_ASSERTION_KILL ' + name, flush=True)
    print('N71_REG_ON_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
