"""Exercise N71 HDQ codec against reference boundaries without hardware I/O."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER_DIR = Path(os.environ.get('N71_HDQ_HEADER_DIR', ROOT / 'phone/kernel'))


class N71HdqCodec(unittest.TestCase):
    def test_native_codec_and_refusal_cases(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native C compiler unavailable; this is not a passing native gate.')
        with tempfile.TemporaryDirectory(prefix='n71-hdq-test-') as directory:
            binary = Path(directory) / 'codec'
            result = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(HEADER_DIR), str(ROOT / 'tests/n71_hdq_codec.c'),
                 '-o', str(binary)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('N71_HDQ_CODEC_OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
