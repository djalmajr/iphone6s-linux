"""Compare N71 input encoding with pinned arithmetic; compiled mutants must assert."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('drop-calibration-refusal', 'request->calibration_enabled != 0', 'request->calibration_enabled > 1'),
    ('wrong-floor', 'milliamps = 90U;', 'milliamps = 100U;'),
    ('wrong-ceiling', 'milliamps = 2000U;', 'milliamps = 2010U;'),
    ('wrong-origin', '(milliamps - 90U) / 10U', '(milliamps - 80U) / 10U'),
    ('wrong-step', '(milliamps - 90U) / 10U', '(milliamps - 90U) / 25U'),
    ('round-up', '(milliamps - 90U) / 10U', '(milliamps - 81U) / 10U'),
    ('wrong-nominal', 'setting.register_value * 10U', 'setting.register_value * 25U'),
    ('conflate-zero-code-suspend', 'request->milliamps == 0', 'setting.register_value == 0'),
)


class InputReferenceTests(unittest.TestCase):
    def test_reference_boundaries_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-sn2400-input-reference.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-sn2400-input-') as directory:
            folder = Path(directory)
            header, binary = folder / 'n71-sn2400-input-reference.h', folder / 'input'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror',
                                           '-pedantic', '-I', str(folder),
                                           str(ROOT / 'tests/n71_sn2400_input_reference.c'), '-o', str(binary)],
                                          capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_SN2400_INPUT_REFERENCE_OK', result.stdout)
                else:
                    self.assertEqual(result.returncode, -6, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)


if __name__ == '__main__':
    unittest.main()
