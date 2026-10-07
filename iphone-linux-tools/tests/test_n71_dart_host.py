"""Run real OF/DART host lease with tracked device/tree dependencies and faults."""
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('board-scope', 'prepare', '!of_machine_is_compatible("apple,n71")', '(false && !of_machine_is_compatible("apple,n71"))'),
    ('master-scope', 'prepare', 'strcmp(of_node_full_name(master_node), "/soc/pcie@610000000")', '(false && strcmp(of_node_full_name(master_node), "/soc/pcie@610000000"))'),
    ('provider-scope', 'prepare', 'strcmp(of_node_full_name(provider_node), "/soc/iommu@602008000")', '(false && strcmp(of_node_full_name(provider_node), "/soc/iommu@602008000"))'),
    ('provider-driver', 'prepare', 'strcmp(provider->dev.driver->name, "apple-dart")', '(false && strcmp(provider->dev.driver->name, "apple-dart"))'),
    ('provider-data', 'prepare', '!platform_get_drvdata(provider)', '(false && !platform_get_drvdata(provider))'),
    ('iommu-cells', 'prepare', 'cells != 1', 'false'),
    ('phandle-lookup', 'prepare', 'lookup == provider_node ? 0', 'true ? 0'),
    ('provider-lookup', 'prepare', 'found == provider ? 0', 'true ? 0'),
    ('foreign-map', 'prepare', 'of_find_property(master_node, "iommu-map", NULL) ||', '(false && of_find_property(master_node, "iommu-map", NULL)) ||'),
    ('foreign-mask', 'prepare', 'of_find_property(master_node, "iommu-map-mask", NULL)', '(false && of_find_property(master_node, "iommu-map-mask", NULL))'),
    ('initial-flag', 'prepare', 'of_node_check_flag(provider_node, OF_POPULATED)', '(false && of_node_check_flag(provider_node, OF_POPULATED))'),
    ('bridge-ref', 'prepare', 'get_device(&request->bridge->dev);', 'if (false) get_device(&request->bridge->dev);'),
    ('master-ref', 'prepare', 'get_device(master);', 'if (false) get_device(master);'),
    ('provider-ref', 'prepare', 'get_device(&provider->dev);', 'if (false) get_device(&provider->dev);'),
    ('provider-node-ref', 'prepare', 'owner->provider_node = of_node_get(provider_node);', 'owner->provider_node = provider_node;'),
    ('master-node-ref', 'prepare', 'owner->master_node = of_node_get(master_node);', 'owner->master_node = master_node;'),
    ('flag-claim', 'prepare', 'if (of_node_test_and_set_flag(provider_node, OF_POPULATED))', 'if (false && of_node_test_and_set_flag(provider_node, OF_POPULATED))'),
    ('flag-owner', 'prepare', 'owner->populated = true;', 'owner->populated = false;'),
    ('status-apply', 'prepare', 'error = of_changeset_apply(&owner->status_changes);', 'error = false ? of_changeset_apply(&owner->status_changes) : 0;'),
    ('status-error', 'prepare', 'if (error)\n\t\treturn error;\n\tif (!owner->available', 'if (false && error)\n\t\treturn error;\n\tif (!owner->available'),
    ('map-error', 'prepare', 'if (error)\n\t\treturn error;\n\treturn owner->mapped', 'if (false && error)\n\t\treturn error;\n\treturn owner->mapped'),
    ('root-rid', 'prepare', 'map[0] = 0x0008;', 'map[0] = 0x0009;'),
    ('stream-id', 'prepare', 'map[2] = 0;', 'map[2] = 1;'),
    ('map-cells-count', 'prepare', '"iommu-map", map, 8)', '"iommu-map", map, 7)'),
    ('live-bus-unmap', 'unmap', 'if (owner->bridge->bus)', 'if (false && owner->bridge->bus)'),
    ('foreign-map-unmap', 'unmap', 'if (property && property != owner->map_property)', 'if (false && property && property != owner->map_property)'),
    ('map-revert', 'unmap', 'error = of_changeset_revert(&owner->map_changes);', 'error = false ? of_changeset_revert(&owner->map_changes) : 0;'),
    ('map-revert-error', 'unmap', 'if (error)', 'if (false && error)'),
    ('live-provider-release', 'release', 'if (found)', 'if (false && found)'),
    ('foreign-status-release', 'release', 'if (status != owner->status_before && status != owner->status_property)', 'if (false && status != owner->status_before && status != owner->status_property)'),
    ('status-revert', 'release', 'error = of_changeset_revert(&owner->status_changes);', 'error = false ? of_changeset_revert(&owner->status_changes) : 0;'),
    ('status-revert-error', 'release', 'if (error)\n\t\t\treturn error;', 'if (false && error)\n\t\t\treturn error;'),
    ('early-flag-clear', 'release', 'found = of_find_device_by_node(owner->provider_node);', 'of_node_clear_flag(owner->provider_node, OF_POPULATED);\n\tfound = of_find_device_by_node(owner->provider_node);'),
    ('flag-restore', 'release', 'of_node_clear_flag(owner->provider_node, OF_POPULATED);', 'if (false) of_node_clear_flag(owner->provider_node, OF_POPULATED);'),
    ('owner-clear', 'release', '*owner = (struct n71_dart_host){0};', '(void)owner;'),
    ('owner-clear-after-last-put', 'release', '*owner = (struct n71_dart_host){0};\n\tof_node_put(released.provider_node);\n\tof_node_put(released.master_node);\n\tput_device(&released.provider->dev);\n\tput_device(released.master);\n\tput_device(&released.bridge->dev);', 'of_node_put(released.provider_node);\n\tof_node_put(released.master_node);\n\tput_device(&released.provider->dev);\n\tput_device(released.master);\n\tput_device(&released.bridge->dev);\n\t*owner = (struct n71_dart_host){0};'),
    ('status-entry-destroy', 'release', 'of_changeset_destroy(&owner->status_changes);', 'if (false) of_changeset_destroy(&owner->status_changes);'),
    ('map-entry-destroy', 'release', 'of_changeset_destroy(&owner->map_changes);', 'if (false) of_changeset_destroy(&owner->map_changes);'),
)


def function_span(source, suffix):
    match = re.search(r'static int n71_dart_host_' + suffix + r'\([^)]*\)\n\{', source)
    if match is None:
        raise ValueError('Host lease function missing: ' + suffix)
    end, depth = match.end(), 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return match.start(), end


class DartHostTests(unittest.TestCase):
    def test_production_host_lease_and_compiled_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-dart-host.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-dart-host-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('of.h', 'of_platform.h', 'pci.h', 'platform_device.h'):
                (folder / 'linux' / name).write_text('/* OF/device APIs supplied by the tracked fixture. */\n')
            for name, suffix, before, after in (('baseline', None, None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    changed = source
                    if before:
                        start, end = function_span(source, suffix)
                        scoped = source[start:end]
                        self.assertEqual(scoped.count(before), 1, name)
                        changed = source[:start] + scoped.replace(before, after, 1) + source[end:]
                    (folder / 'n71-dart-host.h').write_text(changed)
                    binary = folder / 'host'
                    p = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                        '-I', str(folder), str(ROOT / 'tests/n71_dart_host.c'), '-o', str(binary)],
                                       capture_output=True, text=True, timeout=30)
                    self.assertEqual(p.returncode, 0, name + p.stderr)
                    p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                    if before is None:
                        self.assertEqual(p.returncode, 0, p.stderr)
                        self.assertIn('N71_DART_HOST_OK cases=49', p.stdout)
                        print(p.stdout.strip(), flush=True)
                    else:
                        self.assertEqual(p.returncode, -signal.SIGABRT, name + p.stderr)
                        self.assertIn('assert', p.stderr.lower(), name)
                        print('N71_DART_HOST_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
