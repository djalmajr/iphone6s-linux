"""Regression: actual DART writer hunk must preserve unselected stream bytes."""
from pathlib import Path
import os
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'phone/kernel/patches/0001-s5l8960x-dart-stream-tcr.patch'


def functions():
    old, new = [], []
    for line in PATCH.read_text().splitlines():
        if line.startswith(('---', '+++', '@@')):
            continue
        if line[:1] in (' ', '-'):
            old.append(line[1:])
        if line[:1] in (' ', '+'):
            new.append(line[1:])
    return '\n'.join(old) + '\n', '\n'.join(new) + '\n'


class DartS5lTcr(unittest.TestCase):
    def test_actual_writer_and_source_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required.')
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        old, new = functions()
        mutants = [
            ('original-source', new, old),
            ('wrong-mask', '~(0xffU <<', '(0xffU <<'),
            ('missing-shift', 'val << (sid * DART_S5L8960X_TCR_BITS_PER_STREAM)', 'val'),
            ('sid-boundary', 'sid >= 4', 'sid > 4'),
            ('wide-value', 'val > 0xff', 'false'),
        ]
        with tempfile.TemporaryDirectory(prefix='dart-s5l-tcr-') as directory:
            folder = Path(directory)
            for name, before, after in [('baseline', None, None)] + mutants:
                if before is not None:
                    self.assertEqual(new.count(before), 1, name)
                source = new if before is None else new.replace(before, after, 1)
                (folder / 'dart-write-under-test.h').write_text(source)
                built = subprocess.run(
                    [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                     '-I', directory, str(ROOT / 'tests/dart_s5l_tcr.c'), '-o', str(folder / 'test')],
                    capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
                self.assertEqual(built.returncode, 0, 'Build error is not a kill: ' + name + built.stderr)
                result = subprocess.run([str(folder / 'test')], capture_output=True, text=True,
                                        timeout=20, cwd=directory, env=dict(os.environ, LC_ALL='C'))
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('DART_S5L_STREAM_PRESERVATION_OK', result.stdout)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)


if __name__ == '__main__':
    unittest.main()
