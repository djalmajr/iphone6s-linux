"""Host MSI association must precede scan and survive incomplete native cleanup."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('omit-duplicate-owner', 'if (owner->bridge || owner->associated)', 'if (false)'),
    ('omit-live-bus-acquire', 'if (bridge->bus || dev_get_msi_domain(&bridge->dev))',
     'if (false || dev_get_msi_domain(&bridge->dev))'),
    ('omit-foreign-acquire', 'if (bridge->bus || dev_get_msi_domain(&bridge->dev))',
     'if (bridge->bus || false)'),
    ('lose-bridge-owner', 'owner->bridge = bridge;', 'owner->bridge = NULL;'),
    ('lose-previous-flag', 'owner->saved_msi_domain = bridge->msi_domain;', 'owner->saved_msi_domain = false;'),
    ('skip-native-acquire', 'error = n71_wlan_msi_acquire(&owner->native, request->spec, request->message);', 'error = 0;'),
    ('ignore-native-errors', 'if (error)\n\t\treturn error;', 'if (false && error)\n\t\treturn error;'),
    ('skip-association', 'dev_set_msi_domain(&bridge->dev, owner->native.domain);', '(void)bridge;'),
    ('skip-msi-flag', 'bridge->msi_domain = true;', '(void)bridge;'),
    ('skip-associated-owner', 'owner->associated = true;', 'owner->associated = false;'),
    ('release-live-bus', 'if (bridge->bus)', 'if (false && bridge->bus)'),
    ('ignore-foreign-release', 'dev_get_msi_domain(&bridge->dev) != owner->native.domain ||', 'false ||'),
    ('ignore-flag-mismatch', '!bridge->msi_domain)', 'false)'),
    ('skip-detach', 'dev_set_msi_domain(&bridge->dev, NULL);', '(void)bridge;'),
    ('skip-flag-restore', 'bridge->msi_domain = owner->saved_msi_domain;', '(void)bridge;'),
    ('forget-detached-state', 'owner->associated = false;', '(void)owner;'),
    ('release-unassociated-foreign', '} else if (dev_get_msi_domain(&bridge->dev)) {', '} else if (false) {'),
    ('skip-native-release', 'error = n71_wlan_msi_release(&owner->native);', 'error = 0;'),
    ('forget-owner-on-error', 'if (error)\n\t\treturn error;', 'if (error) { owner->bridge = NULL; return error; }'),
    ('skip-owner-reset', '*owner = (struct n71_wlan_msi_host){0};', '(void)owner;'),
    ('omit-message-guard', '!request->message ||', 'false ||'),
    ('omit-spec-guard', '!request->spec)', 'false)'),
)


class HostMsiTests(unittest.TestCase):
    def test_real_host_helper_and_compiled_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-wlan-msi-host.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-msi-host-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            (folder / 'linux/pci.h').write_text('/* Supplied by the tracked PCI fixture. */\n')
            (folder / 'n71-wlan-msi-native.h').write_text('/* Native lease has its own production callback gate. */\n')
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    if before:
                        self.assertIn(before, source)
                    (folder / 'n71-wlan-msi-host.h').write_text(source if before is None else source.replace(before, after))
                    binary = folder / 'host'
                    compiled = subprocess.run(
                        [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                         '-I', str(folder), str(ROOT / 'tests/n71_wlan_msi_host.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                    executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                    if before is None:
                        self.assertEqual(executed.returncode, 0, executed.stderr)
                        self.assertIn('N71_WLAN_MSI_HOST_OK cases=', executed.stdout)
                        print(executed.stdout.strip())
                    else:
                        self.assertEqual(executed.returncode, -6, name + executed.stderr)
                        self.assertIn('assert', executed.stderr.lower())


if __name__ == '__main__':
    unittest.main()
