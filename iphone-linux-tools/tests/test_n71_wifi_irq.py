"""Compile real brcmfmac IRQ error paths, original regression and mutations."""
import importlib.util
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/build'))
SPEC = importlib.util.spec_from_file_location('wifi_irq_builder',
                                            ROOT / 'scripts/build/build-n71-wifi-modules.py')
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
MUTATIONS = (
    ('ignore-msi-error', 'if (ret) {', 'if (ret && false) {'),
    ('swallow-msi-error', '\t\treturn ret;', '\t\treturn 0;'),
    ('replace-msi-error', '\t\treturn ret;', '\t\treturn -EIO;'),
    ('own-on-msi-error', '\tif (ret) {', '\tif (ret) {\n\t\tdevinfo->irq_allocated = true;'),
    ('disable-failed-msi', '\tif (ret) {', '\tif (ret) {\n\t\tpci_disable_msi(pdev);'),
    ('omit-interrupt-mask', '\tbrcmf_pcie_intr_disable(devinfo);', '\t(void)devinfo;'),
    ('omit-msi-rollback', '\t\tpci_disable_msi(pdev);', '\t\t(void)pdev;'),
    ('swallow-irq-error', '\t\treturn -EIO;', '\t\treturn 0;'),
    ('omit-irq-owner', '\tdevinfo->irq_allocated = true;', '\tdevinfo->irq_allocated = false;'),
    ('wrong-irq', 'request_threaded_irq(pdev->irq,', 'request_threaded_irq(0,'),
    ('wrong-thread', 'brcmf_pcie_isr_thread, IRQF_SHARED,', 'brcmf_pcie_quick_check_isr, IRQF_SHARED,'),
    ('wrong-flags', 'brcmf_pcie_isr_thread, IRQF_SHARED,', 'brcmf_pcie_isr_thread, 0,'),
    ('wrong-cookie', '"brcmf_pcie_intr", devinfo)', '"brcmf_pcie_intr", pdev)'),
)


def method(source):
    start = source.index(b'static int brcmf_pcie_request_irq(')
    end = source.index(b'\n}', start) + 3
    return source[start:end].decode()


class WifiIrqTests(unittest.TestCase):
    def test_actual_method_faults_original_regression_and_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        original, changed = BUILDER.irq_patch_method()
        actual = os.environ.get('N71_BRCMFMAC_PCIE_SOURCE')
        if actual:
            raw = Path(actual).read_bytes()
            self.assertEqual(method(raw), original.decode())
            changed = method(BUILDER.irq_patch_source(raw)).encode()
        variants = [('baseline', changed.decode()), ('original-regression', original.decode())]
        for name, before, after in MUTATIONS:
            self.assertEqual(changed.decode().count(before), 1, name)
            variants.append((name, changed.decode().replace(before, after, 1)))
        with tempfile.TemporaryDirectory(prefix='n71-wifi-irq-') as directory:
            folder = Path(directory)
            for name, source in variants:
                with self.subTest(name=name):
                    (folder / 'n71_wifi_irq_method.h').write_text(source)
                    binary = folder / 'irq'
                    built = subprocess.run(
                        [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                         '-I', str(folder), str(ROOT / 'tests/n71_wifi_irq.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
                    self.assertEqual(built.returncode, 0, name + ': compilation is not proof: ' + built.stderr)
                    result = subprocess.run([str(binary)], capture_output=True, text=True,
                                            cwd=folder, timeout=5, env=dict(os.environ, LC_ALL='C'))
                    if name == 'baseline':
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn('N71_BRCMFMAC_IRQ_OK cases=16', result.stdout)
                        print(result.stdout.strip())
                    else:
                        self.assertEqual(result.returncode, -6, name + result.stderr)
                        self.assertIn('assert', result.stderr.lower())
                        print('N71_WIFI_IRQ_ASSERTION_KILLED', name)


if __name__ == '__main__':
    unittest.main()
