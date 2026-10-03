#!/usr/bin/env python3
"""Compile actual new kernel patch routines; require assertion-killed mutations."""
import os
from pathlib import Path
import resource
import re
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'phone/kernel/patches/0002-serdev-stop-bits.patch'
MUTATIONS = (
    ('drop-controller-registration', '.set_stop_bits = ttyport_set_stop_bits,', '.set_stop_bits = NULL,', 0),
    ('forward-wrong-count', 'return ctrl->ops->set_stop_bits(ctrl, stop_bits);',
     'return ctrl->ops->set_stop_bits(ctrl, 1);', 0),
    ('core-invalid-count', 'stop_bits != 1 && stop_bits != 2', 'stop_bits != 0 && stop_bits != 2', 0),
    ('tty-invalid-count', 'stop_bits != 1 && stop_bits != 2', 'stop_bits != 0 && stop_bits != 2', 1),
    ('clear-other-setting', 'ktermios.c_cflag &= ~CSTOPB;', 'ktermios.c_cflag &= ~(CSTOPB | 0x100U);', 0),
    ('reverse-stop-count', 'if (stop_bits == 2)', 'if (stop_bits == 1)', 0),
    ('drop-second-stop', 'ktermios.c_cflag |= CSTOPB;', 'ktermios.c_cflag |= 0;', 0),
    ('swallow-tty-error', 'if (ret)\n\t\treturn ret;', 'if (ret)\n\t\treturn 0;', 0),
    ('ignore-readback', '(tty->termios.c_cflag & CSTOPB) != (ktermios.c_cflag & CSTOPB)', '0 != 0', 0),
    ('unsupported-is-success', 'return -EOPNOTSUPP;', 'return 0;', 0),
    ('closed-port-is-success', 'return -ENODEV;', 'return 0;', 0),
    ('swallow-controller-error', 'return ctrl->ops->set_stop_bits(ctrl, stop_bits);',
     'ctrl->ops->set_stop_bits(ctrl, stop_bits); return 0;', 0),
)


def added_functions(raw):
    added = '\n'.join(line[1:] for line in raw.splitlines()
                      if line.startswith('+') and not line.startswith('+++'))
    methods = []
    for marker in ('int serdev_device_set_stop_bits(', 'static int ttyport_set_stop_bits('):
        pattern = re.escape(marker) + r'[^;{}]*\)\n\{'
        matches = list(re.finditer(pattern, added))
        if len(matches) != 1:
            raise ValueError('Patch function identity is not unique.')
        start = matches[0].start()
        body = matches[0].end() - 1
        depth = 1
        end = body + 1
        while end < len(added) and depth:
            depth += (added[end] == '{') - (added[end] == '}')
            end += 1
        if depth:
            raise ValueError('Unterminated patch function.')
        methods.append(added[start:end])
    registration = re.findall(r'^\t\.set_stop_bits = [a-z_]+,$', added, re.MULTILINE)
    if len(registration) != 1:
        raise ValueError('Patch controller registration is not unique.')
    methods.append('static const struct serdev_controller_ops n71_test_ctrl_ops = {\n'
                   + registration[0] + '\n};')
    return '\n\n'.join(methods) + '\n'


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = added_functions(PATCH.read_text())
    with tempfile.TemporaryDirectory(prefix='n71-serdev-stop-bits-') as directory:
        folder = Path(directory)
        binary = folder / 'contract'
        for name, before, after, occurrence in (('baseline', None, None, 0),) + MUTATIONS:
            modified = source
            if before is not None:
                expected = 2 if before == 'stop_bits != 1 && stop_bits != 2' else 1
                if source.count(before) != expected:
                    raise ValueError('Mutation anchor differs: ' + name)
                position = source.index(before)
                for _ in range(occurrence):
                    position = source.index(before, position + len(before))
                modified = source[:position] + after + source[position + len(before):]
            (folder / 'n71-serdev-added-functions.h').write_text(modified)
            built = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_serdev_stop_bits.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if built.returncode:
                raise RuntimeError('Compilation error is not a kill: ' + name + built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_SERDEV_STOP_BITS_CONTRACT_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -signal.SIGABRT or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing SIGABRT/assertion proof: ' + name + result.stderr)
            else:
                print('N71_SERDEV_STOP_BITS_ASSERTION_KILL ' + name, flush=True)
    print('N71_SERDEV_STOP_BITS_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
