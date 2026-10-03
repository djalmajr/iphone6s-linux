#!/usr/bin/env python3
"""Require assertion-only rejection of N71 topology boundary mutations."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/build/prepare-n71-topology.py'
MUTATIONS = (
    ('reference', 'if reference != REFERENCE:', 'if False:'),
    ('board', "if b'apple,n71' not in before.get('/', {}).get('compatible', b'').split(b'\\0'):", 'if False:'),
    ('new-node-scope', 'if set(after) - set(before) != {UART, DART, PCIE} or set(before) - set(after):', 'if False:'),
    ('preserve-baseline', 'if after[path] != allowed:', 'if False:'),
    ('disabled', "values['status'] = b'disabled\\0'", "values['status'] = after[path].get('status')"),
    ('uart-clock', "values['clocks'] = phandle(CLOCK_REF) * 2", "values['clocks'] = after[path]['clocks']"),
    ('symlink', 'for parent in (path,) + tuple(path.parents):\n        if parent.is_symlink():',
     'for parent in (path,) + tuple(path.parents):\n        if False:'),
)


def suite(environment, case=None):
    arguments = [case, '-v'] if case else ['discover', '-s', str(ROOT / 'tests'), '-p', 'test_n71_topology.py', '-v']
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest'] + arguments, env=environment,
                            cwd=ROOT / 'tests',
                            capture_output=True, text=True, timeout=120)
    return result.returncode, result.stdout + result.stderr


def main():
    code, output = suite(os.environ)
    if code:
        raise RuntimeError('N71 topology baseline failed: ' + output)
    print(output, end='', flush=True)
    mutations = [(name, before, after, None) for name, before, after in MUTATIONS]
    if os.environ.get('IPHONE_N71_VM_SOURCE') and sys.platform == 'linux':
        mutations.append(('phandle-pins', "return ''.join(result)", "return ''",
                          'test_n71_topology.NativeCompilation.test_phandle_pins_preserve_existing_references'))
    else:
        print('N71_NATIVE_PHANDLE_MUTATION_SKIPPED; dedicated Linux source/compiler required')
    for name, before, after, case in mutations:
        with tempfile.TemporaryDirectory(prefix='n71-topology-mutant-') as directory:
            root = Path(directory)
            (root / 'scripts/build').mkdir(parents=True)
            (root / 'phone/kernel').mkdir(parents=True)
            shutil.copyfile(ROOT / 'phone/kernel/n71-peripherals.dtsi', root / 'phone/kernel/n71-peripherals.dtsi')
            source = SOURCE.read_text()
            if source.count(before) != 1:
                raise ValueError('N71 mutation anchor refused: ' + name)
            script = root / 'scripts/build/prepare-n71-topology.py'
            script.write_text(source.replace(before, after, 1))
            code, output = suite(dict(os.environ, N71_TOPOLOGY_SCRIPT=str(script)), case)
            if not code or '\nFAIL:' not in output or '\nERROR:' in output:
                raise RuntimeError('N71 mutation lacks assertion-only proof: ' + name + output)
            print('N71_TOPOLOGY_MUTATION_KILLED ' + name, flush=True)
    print('N71_TOPOLOGY_GATE_OK ' + str(len(mutations)))


if __name__ == '__main__':
    main()
