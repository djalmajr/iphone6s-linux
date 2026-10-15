"""Real DMA backend under modeled bound-driver lifetime; no hardware proof."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('skip-opt-in', '!requested ||', 'false ||'),
    ('missing-endpoint-lock', 'device_lock(&live.endpoint->dev);', 'if (false) device_lock(&live.endpoint->dev);'),
    ('missing-endpoint-unlock', 'device_unlock(&live.endpoint->dev);', 'if (false) device_unlock(&live.endpoint->dev);'),
    ('driver-managed-dma', 'endpoint->driver->driver_managed_dma ||', 'false ||'),
    ('wrong-driver', 'strcmp(endpoint->dev.driver->name, "brcmfmac")', 'false'),
    ('wrong-endpoint', 'endpoint->device != 0x43a3 ||', 'false ||'),
    ('stopped-provider', '!state->dart->lease.running ||', 'false ||'),
    ('foreign-domain', 'host->iommu_domain != live->domain ||', 'false ||'),
    ('wrong-domain-type', 'live->domain->type != IOMMU_DOMAIN_DMA', 'false'),
    ('wrong-provider', 'host->dart.provider != state->dart->device ||', 'false ||'),
    ('pending-power', 'state->power_put_pending ||', 'false ||'),
    ('dead-refs', '!n71_dart_host_refs_valid(&host->dart) ||', '(false && !n71_dart_host_refs_valid(&host->dart)) ||'),
    ('missing-error-output', 'result.error = error;', 'result.error = 0;'),
    ('wrong-clock', '*value = ktime_get_boottime_ns();', '*value = ktime_get_boottime_ns() + 1;'),
    ('wrong-translation', '*physical = iommu_iova_to_phys(live->domain, iova);',
     '*physical = iommu_iova_to_phys(live->domain, iova) & 0xffffffffULL;'),
)


class DmaLive(unittest.TestCase):
    def test_bound_driver_domain_and_power_lifetime(self):
        compiler = shutil.which('cc'); self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-pcie-dma-live.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-dma-live-') as directory:
            folder = Path(directory); (folder / 'linux').mkdir()
            (folder / 'linux/ktime.h').write_text('/* Fixture supplies API. */\n')
            for name in ('n71-dma-observe.h', 'n71-pcie-contract.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before: self.assertEqual(source.count(before), 1, name)
                (folder / 'n71-pcie-dma-live.h').write_text(source if before is None else source.replace(before, after, 1))
                binary = folder / 'probe'
                result = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                    '-I', str(folder), str(ROOT / 'tests/n71_dma_live.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, name + result.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, cwd=folder, timeout=5)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_DMA_LIVE_OK cases=', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_DMA_LIVE_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
