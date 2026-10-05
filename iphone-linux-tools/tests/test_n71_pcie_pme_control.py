"""Compile endpoint PME ownership and falsify it without contacting hardware."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('root-scope', 'n71_control_capture(io, false, &reference)',
     'n71_control_capture(io, true, &reference)'),
    ('pm-offset', 'reference.offsets[index] != 0x48', 'reference.offsets[index] != 0x50'),
    ('pm-version', 'version > 3', 'version > 2'),
    ('missing-capability', 'headers != 1 || words != 1', 'headers > 1 || words > 1'),
    ('fresh-master', 'error || command & 4', 'error || command & 8'),
    ('fresh-word', 'actual != pmcsr', '(actual & ~0x8000U) != (pmcsr & ~0x8000U)'),
    ('baseline-state', 'observed != 0x4108', '(observed & 3)'),
    ('lost-ownership', 'state->pending = true;', 'state->pending = false;'),
    ('prepare-readback', 'error || actual != 0x4008', 'error || false'),
    ('w1c-restore', 'value = (observed & ~0x8100U)', 'value = (observed & ~0x100U)'),
    ('stale-controls', 'value = (observed & ~0x8100U)',
     'value = (state->original & ~0x8100U)'),
    ('early-release', 'value = (observed & ~0x8100U)',
     'state->pending = false;\n\tvalue = (observed & ~0x8100U)'),
    ('restore-enable', '(state->original & 0x100U);', '(state->original & 0x200U);'),
    ('lost-event', '((observed & 0x8000U) && !(actual & 0x8000U))', 'false'),
    ('unowned-core', '!state->pending || !state->prepared ||', 'false ||'),
    ('core-original', 'state->original != 0x4108 || request->value != 0xc008',
     'false || request->value != 0xc008'),
    ('core-request', 'state->original != 0x4108 || request->value != 0xc008',
     'state->original != 0x4108 || false'),
    ('core-active-event', 'error || observed != 0x4008', 'error || false'),
    ('core-width', 'request->where != 0x4c || request->size != 2',
     'request->where != 0x4c || false'),
)


class PMEControl(unittest.TestCase):
    def test_owned_disable_restore_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native compiler unavailable; gate not passed.')
        source = (ROOT / 'phone/kernel/n71-pcie-pme-control.h').read_text()
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        try:
            with tempfile.TemporaryDirectory(prefix='n71-pme-control-') as directory:
                folder = Path(directory)
                header, binary = folder / 'n71-pcie-pme-control.h', folder / 'test'
                for name, before, after in (('baseline', None, None),) + MUTATIONS:
                    with self.subTest(mutation=name):
                        if before is not None:
                            self.assertEqual(source.count(before), 1)
                        header.write_text(source if before is None else source.replace(before, after, 1))
                        result = subprocess.run(
                            [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                             '-I', str(folder), '-I', str(ROOT / 'phone/kernel'),
                             str(ROOT / 'tests/n71_pcie_pme_control.c'), '-o', str(binary)],
                            capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        result = subprocess.run([str(binary)], capture_output=True, text=True,
                                                timeout=5, cwd=folder)
                        if before is None:
                            self.assertEqual(result.returncode, 0, result.stderr)
                            self.assertIn('N71_PME_CONTROL_OK', result.stdout)
                            print('N71_PME_CONTROL_BASELINE_OK', flush=True)
                        else:
                            self.assertEqual(result.returncode, -6, result.stderr)
                            self.assertIn('assert', result.stderr.lower())
                            print('N71_PME_CONTROL_MUTATION_KILLED', name, flush=True)
        finally:
            resource.setrlimit(resource.RLIMIT_CORE, limits)


if __name__ == '__main__':
    unittest.main()
