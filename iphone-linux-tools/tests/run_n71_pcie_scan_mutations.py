#!/usr/bin/env python3
"""Reject config-scan safety regressions by compiled assertion failure."""
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('wrong-endpoint', '0x1004106b : 0x43a314e4', '0x1004106b : 0x43a414e4'),
    ('master-at-capture', 'saved->command & 4)', 'saved->command & 8)'),
    ('class-scope', '0x060400 : 0x028000', '0x060400 : 0x020000'),
    ('bus-scope', '(buses & 0xffffff) != 0x010100', '(buses & 0xffffff) != 0x000100'),
    ('rom-enabled', 'saved->rom & 1)', 'saved->rom & 2)'),
    ('master-write', 'request->value & 4)', 'request->value & 8)'),
    ('write-limit', '> N71_SCAN_MAX_WRITES', '>= N71_SCAN_MAX_WRITES'),
    ('lost-latch', 'if (config->error)\n\t\treturn config->error;',
     'if (config->error == -E2BIG)\n\t\treturn config->error;'),
    ('decode-on-sizing', '(command & 7)', '(command & 4)'),
    ('secondary-status-clear', '!(current & mask)', '!(current & (mask & ~0x800U))'),
    ('arbitrary-change', 'if (!allowed)', 'if (!allowed && request->where == 0x1000)'),
    ('reenable-failed-bar', 'if (!function_error)\n\t\t\tfunction_error =',
     'if (function_error)\n\t\t\tfunction_error ='),
    ('lost-readback', 'actual == value ? 0 : -EIO', '(actual & ~1U) == (value & ~1U) ? 0 : -EIO'),
    ('premature-snapshot', 'if (!io || !io->read || !io->write || !out)',
     'if (out) *out = result;\n\tif (!io || !io->read || !io->write || !out)'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; gate not passed.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = (ROOT / 'phone/kernel/n71-pcie-scan-config.h').read_text()
    with tempfile.TemporaryDirectory(prefix='n71-scan-mutations-') as directory:
        folder = Path(directory)
        for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h'):
            shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
        header, binary = folder / 'n71-pcie-scan-config.h', folder / 'scan'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            header.write_text(source if before is None else source.replace(before, after, 1))
            compiled = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_pcie_scan_config.c'),
                 '-o', str(binary)], capture_output=True, text=True, timeout=30)
            if compiled.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + compiled.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True,
                                    timeout=5, cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_PCIE_SCAN_CONFIG_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -6 or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_SCAN_ASSERTION_KILL ' + name, flush=True)
    print('N71_SCAN_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
