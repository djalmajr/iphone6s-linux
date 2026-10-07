"""N71 MSI message values and error preservation, with compiled assertion mutants."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('wrong-address-accepted', 'request->address_lo != 0xbffff000U ||', 'false ||'),
    ('high-address-accepted', 'request->address_hi ||', 'false ||'),
    ('nonzero-vector-base-accepted', '|| request->vector_base)', '|| false)'),
    ('skip-parent-reference', 'error = n71_wlan_irq_reference(&request->irq, &reference.irq);',
     'error = false ? n71_wlan_irq_reference(&request->irq, &reference.irq) : 0;'),
    ('ignore-parent-error', 'if (error)', 'if (false && error)'),
    ('lose-range-error', 'return error;', 'return -EINVAL;'),
    ('aic-as-message-data', 'reference.message[2] = reference.irq.logical_vector;',
     'reference.message[2] = reference.irq.aic_irq_number;'),
    ('message-data-shift', 'reference.message[2] = reference.irq.logical_vector;',
     'reference.message[2] = reference.irq.logical_vector + 1;'),
    ('wrong-message-address', 'reference.message[0] = request->address_lo;',
     'reference.message[0] = 0xfffff000U;'),
    ('wrong-message-high-word', 'reference.message[1] = request->address_hi;',
     'reference.message[1] = 1;'),
    ('swapped-message-address', 'reference.message[0] = request->address_lo;',
     'reference.message[0] = request->address_hi;'),
    ('overwrite-output-on-refusal', 'if (error)\n\t\treturn error;',
     'if (error) { output->message[0] = 0; return error; }'),
    ('skip-output', '*output = reference;', '(void)reference;'),
)


class WlanMsiMessageTests(unittest.TestCase):
    def test_messages_refusals_and_compiled_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-wlan-msi-message.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-msi-message-') as directory:
            folder = Path(directory)
            shutil.copyfile(ROOT / 'phone/kernel/n71-wlan-irq-reference.h',
                            folder / 'n71-wlan-irq-reference.h')
            header, binary = folder / 'n71-wlan-msi-message.h', folder / 'message'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                     '-I', str(folder), str(ROOT / 'tests/n71_wlan_msi_message.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(),
                                     'N71_WLAN_MSI_MESSAGE_OK cases=30; no IRQ allocation or MMIO')
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_WLAN_MSI_MESSAGE_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
