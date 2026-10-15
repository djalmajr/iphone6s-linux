"""Compile effective patch code; optional full-source mode checks the real VM source."""
import os
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
    ('missing-flag', 'new |= BIT(1);', 'new |= 0;'),
    ('wrong-flag', 'new |= BIT(1);', 'new |= BIT(2);'),
    ('all-formats', 'data->iop.fmt == APPLE_DART &&', '1 &&'),
    ('no-quirk', 'data->iop.cfg.quirks & IO_PGTABLE_QUIRK_APPLE_DART_S5L', '1'),
    ('other-quirk', 'data->iop.cfg.quirks & IO_PGTABLE_QUIRK_APPLE_DART_S5L',
     'data->iop.cfg.quirks & BIT(9)'),
    ('wrong-hardware', 'dart->hw->type == DART_S5L8960X ?',
     'dart->hw->type == DART_T8020 ?'),
    ('all-hardware', 'dart->hw->type == DART_S5L8960X ?', '1 ?'),
    ('drop-pa', 'paddr_to_iopte(__pa(table), data) | APPLE_DART_PTE_VALID',
     '(paddr_to_iopte(__pa(table), data) & 0xfff000) | APPLE_DART_PTE_VALID'),
    ('no-barrier', 'dma_wmb();', 'if (0) dma_wmb();'),
    ('overwrite-winner', 'old = cmpxchg64_relaxed(ptep, curr, new);',
     'old = cmpxchg64_relaxed(ptep, curr, new); *ptep = new;'),
    ('wrong-expected', 'cmpxchg64_relaxed(ptep, curr, new)',
     'cmpxchg64_relaxed(ptep, 0, new); (void)curr'),
    ('hidden-conflict', 'return old;', 'return 0 * old;'),
)


def sources():
    selected = os.environ.get('N71_DART_PMD_SOURCE')
    names = ('include/linux/io-pgtable.h', 'drivers/iommu/apple-dart.c',
             'drivers/iommu/io-pgtable-dart.c')
    if selected:
        return {name: (Path(selected) / name).read_text() for name in names}
    result, name = {}, None
    for line in (ROOT / 'phone/kernel/patches/0009-s5l8960x-dart-pmd.patch').read_text().splitlines(True):
        if line.startswith('+++ b/'):
            name = line[6:].strip()
            result[name] = ''
        elif name and not line.startswith(('--- ', '+++ ', '@@ ')) and line[:1] in (' ', '+'):
            result[name] += line[1:]
    if set(result) != set(names):
        raise ValueError('Exact three PMD patch paths required')
    return result


def subject():
    files = sources()
    macro = re.search(r'^\s*#define IO_PGTABLE_QUIRK_APPLE_DART_S5L\s+BIT\(10\)$',
                      files['include/linux/io-pgtable.h'], re.MULTILINE)
    if macro is None:
        raise ValueError('Explicit unique quirk bit required')
    installer = re.search(r'static dart_iopte dart_install_table\(.*?\n\}',
                          files['drivers/iommu/io-pgtable-dart.c'], re.DOTALL)
    cfg = re.search(r'pgtbl_cfg = \(struct io_pgtable_cfg\)\{.*?\n\t\};',
                    files['drivers/iommu/apple-dart.c'], re.DOTALL)
    if installer is None or cfg is None:
        raise ValueError('Effective installer and configuration required')
    return macro[0] + '\n' + installer[0] + '''
static struct io_pgtable_cfg selected_config(struct apple_dart *dart)
{
    struct io_pgtable_cfg pgtbl_cfg;
    unsigned int ias = 32;
    ''' + cfg[0] + '''
    return pgtbl_cfg;
}
'''


class DartPMD(unittest.TestCase):
    def test_published_descriptor_scope_order_and_cas_conflicts(self):
        # Kills each listed installer/configuration mutation through compiled assertions.
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = subject()
        with tempfile.TemporaryDirectory(prefix='n71-dart-pmd-') as directory:
            folder = Path(directory)
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                (folder / 'pmd-subject.h').write_text(source if before is None else source.replace(before, after, 1))
                binary = folder / 'pmd'
                compiled = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                           '-I', str(folder), str(ROOT / 'tests/n71_dart_pmd.c'),
                                           '-o', str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_DART_PMD_OK cases=387', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_DART_PMD_ASSERTION_KILL ' + name, flush=True)
        print('N71_DART_PMD_GATE_OK mutations=12', flush=True)


if __name__ == '__main__':
    unittest.main()
