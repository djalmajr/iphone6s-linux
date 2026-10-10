"""Exclusive DART IRQ allocation must reject conflicts under the root lock."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('ignore-conflict', 'if (irq_find_mapping(binding->parent, binding->hwirq))', 'if (false)'),
    ('omit-count', 'count != 1 ||', 'false ||'),
    ('omit-owner', 'argument != binding ||', '(argument != binding && false) ||'),
    ('omit-cells', 'spec->param_count != 3 ||', 'false ||'),
    ('omit-type-cell', 'spec->param[0] ||', 'false ||'),
    ('omit-number-contract', 'spec->param[1] != 248 ||', 'false ||'),
    ('omit-trigger-contract', 'spec->param[2] != IRQ_TYPE_LEVEL_HIGH ||', 'false ||'),
    ('omit-encoded-hwirq', 'hwirq != 0x100f8UL', 'false'),
    ('omit-chip-validation', 'strcmp(parent_data->chip->name, "AIC")', '0'),
    ('skip-parent-rollback', 'irq_domain_free_irqs_parent(domain, virq, count);', '(void)count;'),
    ('skip-type', 'return irq_set_irq_type(binding->irq, IRQ_TYPE_LEVEL_HIGH);', 'return 0;'),
    ('ignore-action', 'irq_has_action(binding->irq) ||', 'false ||'),
    ('ignore-started', 'irqd_is_started(data) ||', 'false ||'),
    ('ignore-enabled', '!irqd_irq_disabled(data) ||', 'false ||'),
    ('ignore-unmasked', '!irqd_irq_masked(data)', 'false'),
    ('skip-irq-free', 'irq_domain_free_irqs(binding->irq, 1);', '(void)binding->irq;'),
    ('skip-parent-free', 'irq_domain_free_irqs_common(domain, virq, count);', '(void)domain; (void)virq; (void)count;'),
    ('ignore-domain-mappings', 'if (binding->domain->mapcount)', 'if (false)'),
    ('skip-domain-remove', 'irq_domain_remove(binding->domain);', '(void)binding->domain;'),
    ('skip-fwnode-free', 'irq_domain_free_fwnode(binding->fwnode);', '(void)binding->fwnode;'),
    ('skip-node-put', 'of_node_put(binding->node);', '(void)binding->node;'),
)


class DartIrqTests(unittest.TestCase):
    def test_native_irq_callbacks_conflicts_and_compiled_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-dart-irq.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-dart-irq-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('irq.h', 'irqdomain.h', 'of_irq.h'):
                (folder / 'linux' / name).write_text('/* APIs supplied by the IRQ core fixture. */\n')
            header, binary = folder / 'n71-dart-irq.h', folder / 'irq'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    if before:
                        self.assertIn(before, source)
                    mutated = source if before is None else source.replace(before, after)
                    # Both spec and translated value enforce these two contracts.
                    if name == 'omit-number-contract':
                        mutated = mutated.replace('hwirq != 0x100f8UL', 'false')
                    if name == 'omit-trigger-contract':
                        mutated = mutated.replace('type != IRQ_TYPE_LEVEL_HIGH', 'false')
                    header.write_text(mutated)
                    compiled = subprocess.run(
                        [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                         '-I', str(folder), str(ROOT / 'tests/n71_dart_irq.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                    executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                    if before is None:
                        self.assertEqual(executed.returncode, 0, executed.stderr)
                        self.assertIn('N71_DART_IRQ_OK cases=', executed.stdout)
                        print(executed.stdout.strip())
                    else:
                        self.assertEqual(executed.returncode, -6, name + executed.stderr)
                        self.assertIn('assert', executed.stderr.lower())


if __name__ == '__main__':
    unittest.main()
