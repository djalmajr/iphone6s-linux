"""Qualify adapter-derived IO16 eligibility, reporting and same-boot cleanup."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('unsupported-window', '!root->io_window || root->io_window_1k', 'false || root->io_window_1k'),
    ('one-k-window', '!root->io_window || root->io_window_1k', '!root->io_window || false'),
    ('type-base-lost', 'lower & 0x0f0fU', 'lower & 0x0f00U'),
    ('type-limit-lost', 'lower & 0x0f0fU', 'lower & 0x000fU'),
    ('type-read-error-ignored', 'pci_read_config_word(root, PCI_IO_BASE, &lower);\n\tif (error)',
     'pci_read_config_word(root, PCI_IO_BASE, &lower);\n\tif (false)'),
    ('flags-ignored', 'resource->flags && resource->flags != IORESOURCE_IO', 'false'),
    ('present-start-ignored', 'resource->flags && (resource->start || resource->end != 0xfffU)',
     'resource->flags && (false || resource->end != 0xfffU)'),
    ('present-end-ignored', 'resource->flags && (resource->start || resource->end != 0xfffU)',
     'resource->flags && (resource->start || false)'),
    ('empty-start-ignored', '!resource->flags && (resource->start || resource->end)',
     '!resource->flags && (false || resource->end)'),
    ('empty-end-ignored', '!resource->flags && (resource->start || resource->end)',
     '!resource->flags && (resource->start || false)'),
    ('derived-optin-lost', 'layout->io16_upper_unused = true;', 'layout->io16_upper_unused = false;'),
    ('preflight-error-ignored', 'error = n71_resource_io16_layout(root, layout);\n\tif (error)',
     'error = n71_resource_io16_layout(root, layout);\n\tif (false)'),
    ('report-missing', 'n71_resource_report_io16(host);', '(void)n71_resource_report_io16;'),
    ('report-duplicate', 'n71_resource_report_io16(host);',
     'n71_resource_report_io16(host); n71_resource_report_io16(host);'),
    ('report-before-optional', 'n71_resource_report_optional(host);\n\tn71_resource_report_io16(host);',
     'n71_resource_report_io16(host);\n\tn71_resource_report_optional(host);'),
    ('report-enabled-lost', 'host->resources.pending, host->resources.io16_upper_unused,',
     'host->resources.pending, false,'),
    ('report-counter-lost', 'host->resources.io16_noops);', '0U);'),
)


class IO16HostTests(unittest.TestCase):
    def test_adapter_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-pcie-resource-assign.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-io16-host-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('pci.h', 'spinlock.h', 'ioport.h'):
                (folder / 'linux' / name).write_text('/* PCI API supplied by the harness. */\n')
            header, binary = folder / 'n71-pcie-resource-assign.h', folder / 'host'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before is not None:
                    self.assertEqual(source.count(before), 1, 'Mutation anchor: ' + name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                p = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                    '-I', str(folder), '-I', str(ROOT / 'phone/kernel'),
                                    str(ROOT / 'tests/n71_pcie_io16_host.c'), '-o', str(binary)],
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(p.returncode, 0, 'Compilation failure is not a kill: ' + name + p.stderr)
                p = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn('N71_PCIE_IO16_HOST_OK cases=20', p.stdout)
                    print(p.stdout.strip(), flush=True)
                else:
                    self.assertEqual(p.returncode, -6, 'Missing SIGABRT: ' + name + p.stderr)
                    self.assertIn('assert', p.stderr.lower(), name)
                    print('N71_IO16_HOST_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
