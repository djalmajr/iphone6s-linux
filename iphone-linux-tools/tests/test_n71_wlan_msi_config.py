"""Execute the real MSI config owner, including compiled assertion mutations."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('overwrite-owner', 'if (out->phase != N71_MSI_CONFIG_EMPTY)', 'if (false)'),
    ('missing-grant', 'slots && !(slots & ~0xffU)', '!(slots & ~0xffU)'),
    ('multi-grant', '&& !(slots & (slots - 1))', '&& true'),
    ('out-of-range-grant', '!(slots & ~0xffU)', 'true'),
    ('wrong-vector-base', 'u32 vector = 8;', 'u32 vector = 9;'),
    ('root-write', 'if (config->root)', 'if (false)'),
    ('command-width', 'config->where == 4 && config->size == 2',
     'config->where == 4 && (config->size == 2 || config->size == 4)'),
    ('command-bits', '((config->value ^ state->command[1]) & ~0x400U) == 0', 'true'),
    ('control-qsize', 'allowed = config->value == 0x88;',
     'allowed = config->value == 0x88 || config->value == 0x99;'),
    ('control-width', 'config->where == 0x5a && config->size == 2',
     'config->where == 0x5a && (config->size == 2 || config->size == 4)'),
    ('wrong-address', 'config->value == 0xbffff000U', 'config->value >= 0xbffff000U'),
    ('wrong-hi', 'config->where == 0x60 && config->size == 4 && config->value == 0',
     'config->where == 0x60 && config->size == 4'),
    ('wrong-data', 'config->value == n71_msi_config_vector(request->slots)', 'true'),
    ('message-readback', 'if (actual != expected[index])', 'if (actual != expected[index] && false)'),
    ('lost-first-error', 'if (error && !state->error)', 'if (error)'),
    ('write-after-error', 'if (state->error && state->phase != N71_MSI_CONFIG_STOPPED)', 'if (false)'),
    ('write-readback', 'if (!error && actual != request->value)', 'if (false)'),
    ('stop-unverified', 'if (error)\n\t\treturn n71_msi_config_error(state, error);\n\tstate->phase = N71_MSI_CONFIG_STOPPED;',
     'if (error)\n\t\t(void)error;\n\tstate->phase = N71_MSI_CONFIG_STOPPED;'),
    ('restore-while-active', 'state->phase != N71_MSI_CONFIG_STOPPED || core->enabled', 'core->enabled'),
    ('restore-while-enabled', '|| core->enabled ||', '|| false ||'),
    ('restore-with-grants', '|| core->slots ||', '|| false ||'),
    ('restore-with-mappings', '|| core->mappings)', '|| false)'),
    ('release-on-restore-error', 'if (error)\n\t\treturn n71_msi_config_error(state, error);\n\tstate->phase = N71_MSI_CONFIG_EMPTY;',
     'if (error)\n\t\t(void)error;\n\tstate->phase = N71_MSI_CONFIG_EMPTY;'),
    ('normal-budget', '> N71_MSI_CONFIG_MAX_ATTEMPTS', '> N71_MSI_CONFIG_MAX_ATTEMPTS + 1'),
    ('reject-live-replay', 'if (allowed && (control & 1))', 'if (allowed && (control & 1)) return -EPERM;\n\t\tif (allowed && (control & 1))'),
    ('reject-core-zero-message', 'state->phase == N71_MSI_CONFIG_STOPPED && !(control & 1)', 'false'),
    ('cleanup-budget', 'if (state->phase == N71_MSI_CONFIG_EMPTY)\n\t\treturn 0;\n\tif (++state->cleanup_attempts > N71_MSI_CONFIG_MAX_CLEANUP)',
     'if (state->phase == N71_MSI_CONFIG_EMPTY)\n\t\treturn 0;\n\tif (++state->cleanup_attempts > N71_MSI_CONFIG_MAX_CLEANUP + 1)'),
)


class MsiConfigTests(unittest.TestCase):
    def test_faults_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-wlan-msi-config.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-msi-config-') as directory:
            folder = Path(directory)
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h', 'n71-pcie-scan-config.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    if before:
                        self.assertEqual(source.count(before), 1, name)
                    (folder / 'n71-wlan-msi-config.h').write_text(
                        source if before is None else source.replace(before, after, 1))
                    binary = folder / 'config'
                    built = subprocess.run(
                        [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                         '-I', str(folder), str(ROOT / 'tests/n71_wlan_msi_config.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(built.returncode, 0, name + ': compilation is not proof: ' + built.stderr)
                    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                    if name == 'baseline':
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('N71_WLAN_MSI_CONFIG_OK cases=', result.stdout)
                        print(result.stdout.strip())
                    else:
                        self.assertEqual(result.returncode, -6, name + result.stderr)
                        self.assertIn('assert', result.stderr.lower())
                        print('N71_MSI_CONFIG_ASSERTION_KILLED', name)


if __name__ == '__main__':
    unittest.main()
