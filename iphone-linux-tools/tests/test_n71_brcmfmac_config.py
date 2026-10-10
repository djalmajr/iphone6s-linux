"""Exercise real driver PCI policy with observable ECAM and retained ownership."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('skip-opt-in', 'if (!state->active)\n\t\treturn -EPERM;', 'if (false)\n\t\treturn -EPERM;'),
    ('capture-without-owner', 'result.active = true;', 'result.active = false;'),
    ('accept-bad-power', 'power != 0x4008', 'false'),
    ('ignore-capture-drift', 'window != result.window || link != result.link', 'false'),
    ('deny-driver-master', 'u32 mask = write.root ? 6U : 0x406U;', 'u32 mask = write.root ? 2U : 0x402U;'),
    ('allow-io', 'u32 mask = write.root ? 6U : 0x406U;', 'u32 mask = write.root ? 7U : 0x407U;'),
    ('rewrite-link-status', 'write.size = 2;\n\t\twrite.value &= 0xffffU;', '/* Incorrect DWORD replay. */'),
    ('allow-link-retrain', 'allowed = ((write.value ^ state->link) & ~3U) == 0;', 'allowed = true;'),
    ('drop-doorbell', 'error = io->write(io->context, false, 0x98, 4, 1);', 'error = 0;'),
    ('enable-intx-with-msi', 'allowed = !(control & 1);', 'allowed = true;'),
    ('omit-message-check', 'error = n71_msi_config_message(io, request->slots);', 'error = 0;'),
    ('accept-zero-without-stop', '} else if (!write.value) {', '} if (!write.value) {'),
    ('ignore-readback', 'if (!error && actual != request->value)', 'if (false)'),
    ('replace-first-error', 'if (error && !state->error)', 'if (error)'),
    ('accept-positive-error', 'if (error > 0)', 'if (false)'),
    ('restore-with-registered-driver', 'core->driver_registered || core->driver_bound', 'core->driver_bound'),
    ('restore-with-bound-driver', 'core->driver_registered || core->driver_bound', 'core->driver_registered'),
    ('restore-with-software-msi', 'core->software_enabled ||', 'false ||'),
    ('restore-with-grant', 'core->slots || core->mappings', 'core->mappings'),
    ('restore-with-mapping', 'core->slots || core->mappings', 'core->slots'),
    ('restore-with-child-mapping', 'core->child_mappings)', 'false)'),
    ('ignore-identity', 'identity != (index == 0 ? 0x1004106bU : 0x43a314e4U)', 'false'),
    ('lose-window-restore', 'false, 0x80, state->window, 4', 'false, 0x80, 0, 4'),
)


class BrcmfmacConfigTests(unittest.TestCase):
    def test_runtime_effects_retained_restore_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-brcmfmac-config.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-brcmfmac-config-') as directory:
            folder = Path(directory)
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h',
                         'n71-pcie-scan-config.h', 'n71-wlan-msi-config.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    if before:
                        self.assertEqual(source.count(before), 1, name)
                    (folder / 'n71-brcmfmac-config.h').write_text(
                        source if before is None else source.replace(before, after, 1))
                    binary = folder / 'config'
                    built = subprocess.run(
                        [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                         '-I', str(folder), str(ROOT / 'tests/n71_brcmfmac_config.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(built.returncode, 0, name + ': compilation is not proof: ' + built.stderr)
                    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                    if name == 'baseline':
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('N71_BRCMFMAC_CONFIG_OK cases=', result.stdout)
                        print(result.stdout.strip(), flush=True)
                    else:
                        self.assertEqual(result.returncode, -6, name + result.stderr)
                        self.assertIn('assert', result.stderr.lower())
                        print('N71_BRCMFMAC_CONFIG_ASSERTION_KILLED', name, flush=True)


if __name__ == '__main__':
    unittest.main()
