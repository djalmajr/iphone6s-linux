"""Qualify the adapter's core flags, empty resources and absent-range report."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('io-absence-lost', 'layout->io_absent = !root->io_window;', 'layout->io_absent = false;'),
    ('pref-absence-lost', 'layout->pref_absent = !root->pref_window;', 'layout->pref_absent = false;'),
    ('io-absence-invented', 'layout->io_absent = !root->io_window;', 'layout->io_absent = true;'),
    ('pref-absence-invented', 'layout->pref_absent = !root->pref_window;', 'layout->pref_absent = true;'),
    ('io-resource-flags', '!root->io_window && (resource->flags || resource->start || resource->end)',
     '!root->io_window && (resource->start || resource->end)'),
    ('io-resource-start', '!root->io_window && (resource->flags || resource->start || resource->end)',
     '!root->io_window && (resource->flags || resource->end)'),
    ('io-resource-end', '!root->io_window && (resource->flags || resource->start || resource->end)',
     '!root->io_window && (resource->flags || resource->start)'),
    ('pref-resource-flags', '!root->pref_window && (resource->flags || resource->start || resource->end)',
     '!root->pref_window && (resource->start || resource->end)'),
    ('pref-resource-start', '!root->pref_window && (resource->flags || resource->start || resource->end)',
     '!root->pref_window && (resource->flags || resource->end)'),
    ('pref-resource-end', '!root->pref_window && (resource->flags || resource->start || resource->end)',
     '!root->pref_window && (resource->flags || resource->start)'),
    ('optional-report-missing', 'n71_resource_report_optional(host);', '(void)n71_resource_report_optional;'),
    ('optional-report-duplicate', 'n71_resource_report_optional(host);',
     'n71_resource_report_optional(host); n71_resource_report_optional(host);'),
    ('optional-report-flag', 'host->resources.pending, host->resources.io_absent,',
     'host->resources.pending, false,'),
    ('optional-report-counter', 'host->resources.io_noops, host->resources.pref_noops);',
     '0U, host->resources.pref_noops);'),
)


class OptionalHostTests(unittest.TestCase):
    def test_adapter_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-pcie-resource-assign.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-optional-host-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('pci.h', 'spinlock.h', 'ioport.h', 'iommu.h'):
                (folder / 'linux' / name).write_text('/* PCI API supplied by the harness. */\n')
            header, binary = folder / 'n71-pcie-resource-assign.h', folder / 'host'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before is not None:
                    self.assertEqual(source.count(before), 1, 'Mutation anchor: ' + name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                p = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                    '-I', str(folder), '-I', str(ROOT / 'phone/kernel'),
                                    str(ROOT / 'tests/n71_pcie_optional_host.c'), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0, 'Compilation failure is not a kill: ' + name + p.stderr)
                p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn('N71_PCIE_OPTIONAL_HOST_OK cases=18', p.stdout)
                    print(p.stdout.strip(), flush=True)
                else:
                    self.assertEqual(p.returncode, -6, 'Missing SIGABRT: ' + name + p.stderr)
                    self.assertIn('assert', p.stderr.lower(), name)
                    print('N71_OPTIONAL_HOST_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
