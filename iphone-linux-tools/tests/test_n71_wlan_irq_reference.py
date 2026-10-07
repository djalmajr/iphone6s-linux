"""Check the N71 AIC request contract; compiled mutations must fail by assertion."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('apple-cells-accepted', 'request->aic_cells != 3', 'request->aic_cells > 3'),
    ('root-count-relaxed', 'request->root_vector_count != 32', 'request->root_vector_count > 32'),
    ('root-offset-relaxed', 'request->root_vector_offset != 256', 'request->root_vector_offset > 256'),
    ('wrong-port-accepted', 'request->port_index != 1', 'request->port_index > 1'),
    ('port-base-relaxed', 'request->port_vector_base != 8', 'request->port_vector_base < 8'),
    ('port-count-relaxed', 'request->port_vector_count != 8', 'request->port_vector_count < 8'),
    ('adjacent-port-accepted', 'request->index >= request->port_vector_count',
     'request->index > request->port_vector_count'),
    ('wrong-range-error', 'return -ERANGE;', 'return -EINVAL;'),
    ('logical-vector-shift', 'request->port_vector_base + request->index;',
     'request->port_vector_base + request->index + 1;'),
    ('missing-parent-offset', 'request->root_vector_offset + reference.logical_vector;',
     'reference.logical_vector;'),
    ('fiq-request', 'reference.fwspec[0] = 0;', 'reference.fwspec[0] = 1;'),
    ('logical-vector-as-aic', 'reference.fwspec[1] = reference.aic_irq_number;',
     'reference.fwspec[1] = reference.logical_vector;'),
    ('level-msi-request', 'reference.fwspec[2] = 1;', 'reference.fwspec[2] = 4;'),
    ('overwrite-output-on-refusal', '\t\treturn -ERANGE;',
     '\t\treturn output->fwspec[0] = 0, -ERANGE;'),
)


class WlanIrqReferenceTests(unittest.TestCase):
    def test_topology_vectors_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-wlan-irq-reference.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-wlan-irq-') as directory:
            folder = Path(directory)
            header = folder / 'n71-wlan-irq-reference.h'
            binary = folder / 'irq-reference'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                     '-I', str(folder), str(ROOT / 'tests/n71_wlan_irq_reference.c'),
                     '-o', str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(),
                                     'N71_WLAN_AIC_REFERENCE_OK cases=61; no IRQ allocation')
                else:
                    self.assertEqual(result.returncode, -6, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)


if __name__ == '__main__':
    unittest.main()
