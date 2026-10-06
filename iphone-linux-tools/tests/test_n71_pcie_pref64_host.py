"""Require adapter proof of PREF64 eligibility, final readback and rollback."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('core-pref-window-ignored', '!root->pref_window || !root->pref_64_window', 'false || !root->pref_64_window'),
    ('core-pref64-probe-ignored', '!root->pref_window || !root->pref_64_window', '!root->pref_window || false'),
    ('flags-ignored', 'resource->flags != (IORESOURCE_MEM | IORESOURCE_PREFETCH |\n'
     '\t    IORESOURCE_MEM_64 | PCI_PREF_RANGE_TYPE_64)', 'false'),
    ('resource-start-ignored', 'resource->start || resource->end != 0xfffffU', 'false || resource->end != 0xfffffU'),
    ('resource-end-ignored', 'resource->start || resource->end != 0xfffffU', 'resource->start || false'),
    ('derived-optin-lost', 'layout->pref64_disable = true;', 'layout->pref64_disable = false;'),
    ('preflight-error-ignored', 'n71_resource_pref64_layout(root, layout);\n\tif (error)',
     'n71_resource_pref64_layout(root, layout);\n\tif (false)'),
    ('final-readback-lost', 'if (!error && host->resources.pref64_disable) {', 'if (false) {'),
    ('typed-expectation-unreported', 'failure->valid && failure->expected != failure->request.value', 'false'),
    ('report-missing', 'n71_resource_report_pref64(host);', '(void)n71_resource_report_pref64;'),
    ('report-duplicate', 'n71_resource_report_pref64(host);',
     'n71_resource_report_pref64(host); n71_resource_report_pref64(host);'),
    ('report-before-io16', 'n71_resource_report_io16(host);\n\tn71_resource_report_pref64(host);',
     'n71_resource_report_pref64(host);\n\tn71_resource_report_io16(host);'),
    ('report-enabled-lost', 'host->resources.pending, host->resources.pref64_disable,',
     'host->resources.pending, false,'),
    ('report-counter-lost', 'host->resources.pref64_writes);', '0U);'),
)


class Pref64HostTests(unittest.TestCase):
    def test_adapter_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-pcie-resource-assign.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-pref64-host-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('pci.h', 'spinlock.h', 'ioport.h'):
                (folder / 'linux' / name).write_text('/* PCI API supplied by the harness. */\n')
            binary = folder / 'host'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before is not None:
                    self.assertEqual(source.count(before), 1, 'Mutation anchor: ' + name)
                (folder / 'n71-pcie-resource-assign.h').write_text(
                    source if before is None else source.replace(before, after, 1))
                p = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                    '-I', str(folder), '-I', str(ROOT / 'phone/kernel'),
                                    str(ROOT / 'tests/n71_pcie_pref64_host.c'), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0, 'Compilation failure is not a kill: ' + name + p.stderr)
                p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn('N71_PCIE_PREF64_HOST_OK cases=20', p.stdout)
                    print(p.stdout.strip(), flush=True)
                else:
                    self.assertEqual(p.returncode, -6, 'Missing SIGABRT: ' + name + p.stderr)
                    self.assertIn('assert', p.stderr.lower(), name)
                    print('N71_PREF64_HOST_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
