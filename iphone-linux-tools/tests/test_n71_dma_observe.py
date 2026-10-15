"""Compile bounded live DMA observations; no kernel or device is exercised."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('implicit-request', '!request->requested ||', 'false ||'),
    ('wide-aperture', 'request->aperture_end > 0xffffffffULL', 'false'),
    ('below-aperture', 'request->iova < request->aperture_start', 'false'),
    ('above-aperture', 'request->iova > request->aperture_end', 'false'),
    ('missing-read-guard', '\t\t\terror = n71_dma_error(io->validate(io->context));', '\t\t\terror = 0;'),
    ('wrong-ttbr-offset', '0x40 + (index - 4) * 4', '0x44 + (index - 4) * 4'),
    ('rounded-iova', 'request->iova, &row->physical', 'request->iova & ~0xfffULL, &row->physical'),
    ('truncated-physical', 'row->valid |= N71_DMA_TRANSLATION_VALID;',
     'row->valid |= N71_DMA_TRANSLATION_VALID; row->physical &= 0xffffffffULL;'),
    ('wide-physical', 'row->physical > N71_DMA_PA_MAX', 'false'),
    ('positive-error', 'error > 0 ? -EIO : error', 'error'),
    ('physical-instability', 'result.samples[0].physical != result.samples[1].physical', 'false'),
    ('register-instability', 'result.samples[0].words[index] != result.samples[1].words[index]', 'false'),
    ('busy-command', 'result.samples[0].words[0] & 8U', 'result.samples[0].words[0] & 16U'),
    ('reversed-clock', 'result.samples[1].time_ns < result.samples[0].time_ns', 'false'),
    ('missing-second-sample', 'sample < 2;', 'sample < 1;'),
    ('unavailable-register', 'row->words[index] == 0xffffffffU', 'false'),
    ('discard-partial-data', '*out = result;', '*out = result; if (error) out->samples[0] = (struct n71_dma_sample){0};'),
)


class DmaObservationTests(unittest.TestCase):
    def test_boundaries_partial_observations_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-dma-observe.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-dma-observe-') as directory:
            folder = Path(directory)
            shutil.copyfile(ROOT / 'phone/kernel/n71-pcie-contract.h', folder / 'n71-pcie-contract.h')
            header, binary = folder / 'n71-dma-observe.h', folder / 'observe'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run([compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                    '-I', str(folder), str(ROOT / 'tests/n71_dma_observe.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_DMA_OBSERVE_OK cases=', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_DMA_OBSERVE_ASSERTION_KILL ' + name, flush=True)
            print('N71_DMA_OBSERVE_GATE_OK mutations=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
