"""Native MSI ownership, aligned allocation and per-vector rollback contracts."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('omit-child-pin', '|| binding->child)\n\t\t\terror', '|| false)\n\t\t\terror'),
    ('omit-child-identity', 'binding->child = child;', 'binding->child = NULL;'),
    ('overwrite-child', 'else if (binding->child)', 'else if (false)'),
    ('skip-prepare-reset', 'memset(argument, 0, sizeof(*argument));', '(void)argument;'),
    ('skip-child-teardown', 'binding->child = NULL;', '(void)binding->child;'),
    ('omit-child-device', 'info->desc->dev != binding->child_device ||', 'false ||'),
    ('omit-msix-token', 'info->bus_token != DOMAIN_BUS_PCI_DEVICE_MSI ||', 'false ||'),
    ('omit-msix-flags', 'info->flags & MSI_FLAG_PCI_MSIX ||', 'false ||'),
    ('ignore-library-error', 'if (!msi_lib_init_dev_msi_info(device, domain, real_parent, info))',
     'if (!msi_lib_init_dev_msi_info(device, domain, real_parent, info) && false)'),
    ('omit-cell-count', 'spec->param_count != 3 ||', 'false ||'),
    ('omit-interrupt-number', 'spec->param[1] != 264 ||', 'false ||'),
    ('omit-number-encoding', 'hwirq != 0x10108UL + i ||', 'false ||'),
    ('omit-trigger-translation', 'type != IRQ_TYPE_EDGE_RISING)', 'false)'),
    ('translate-only-first', 'for (i = 0; i < 8; i++)', 'for (i = 0; i < 1; i++)'),
    ('allow-nine-vectors', 'count > 8 ||', 'count > 16 ||'),
    ('reject-eight-vectors', 'count > 8 ||', 'count >= 8 ||'),
    ('omit-power-of-two', '(count & (count - 1)))', 'false)'),
    ('unaligned-region', 'first += count)', 'first++)'),
    ('allow-overlap', 'if (!(binding->slots & mask))', 'if (true)'),
    ('clobber-grants', 'binding->slots |= mask;', 'binding->slots = mask;'),
    ('skip-conflict', 'if (irq_find_mapping(binding->parent, 0x10108UL + first + i))',
     'if (irq_find_mapping(binding->parent, 0x10108UL + first + i) && false)'),
    ('wrong-parent-offset', 'spec.param[1] += first;', 'spec.param[1] += 0;'),
    ('skip-partial-parent-rollback', 'irq_domain_free_irqs_parent(domain, virq + i, 1);', '(void)i;'),
    ('skip-parent-rollback', 'irq_domain_free_irqs_parent(domain, virq, count);', '(void)count;'),
    ('omit-parent-chip', 'strcmp(data->chip->name, "AIC")', '0'),
    ('omit-parent-hwirq', 'data->hwirq != 0x10108UL + first + i ||', 'false ||'),
    ('skip-leaf-rollback', 'irq_domain_reset_irq_data(irq_domain_get_irq_data(domain, virq + --i));', '(void)--i;'),
    ('skip-trigger-state', 'irqd_set_trigger_type(irq_domain_get_irq_data(domain, virq + i), IRQ_TYPE_EDGE_RISING);', '(void)i;'),
    ('skip-common-free', 'irq_domain_free_irqs_common(domain, virq, count);', '(void)count;'),
    ('omit-single-vector-free', 'count != 1 || !data ||', 'false || !data ||'),
    ('omit-free-chip', 'data->chip != &n71_wlan_msi_chip ||', 'false ||'),
    ('omit-free-owner', 'data->chip_data != binding ||', 'false ||'),
    ('omit-free-bounds', 'data->hwirq >= 8))', 'false))'),
    ('omit-free-grant', 'if (WARN_ON_ONCE(!(binding->slots & mask)))', 'if (WARN_ON_ONCE(false))'),
    ('wrong-free-slot', 'mask = 1U << data->hwirq;', 'mask = 1U;'),
    ('erase-other-grants', 'binding->slots &= ~mask;', 'binding->slots = 0;'),
    ('wrong-message-number', 'message->data = reference.message[2];', 'message->data = reference.irq.aic_irq_number;'),
    ('omit-message-grant', '!(binding->slots & (1U << data->hwirq))', 'false'),
    ('omit-message-domain', 'data->domain != binding->domain ||', 'false ||'),
    ('omit-release-slots', 'if (binding->slots || binding->domain->mapcount || binding->child)',
     'if (false || binding->domain->mapcount || binding->child)'),
    ('omit-release-mapcount', 'if (binding->slots || binding->domain->mapcount || binding->child)',
     'if (binding->slots || false || binding->child)'),
    ('omit-release-owner', 'binding->domain->host_data != binding ||', 'false ||'),
    ('skip-domain-remove', 'irq_domain_remove(binding->domain);', '(void)binding->domain;'),
    ('skip-fwnode-free', 'irq_domain_free_fwnode(binding->fwnode);', '(void)binding->fwnode;'),
    ('skip-node-put', 'of_node_put(binding->node);', '(void)binding->node;'),
)


class NativeMsiTests(unittest.TestCase):
    def test_production_callbacks_and_compiled_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-wlan-msi-native.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-msi-native-') as directory:
            folder = Path(directory)
            (folder / 'linux/irqchip').mkdir(parents=True)
            for name in ('irq.h', 'irqdomain.h', 'msi.h', 'of_irq.h', 'irqchip/irq-msi-lib.h'):
                (folder / 'linux' / name).write_text('/* Supplied by the tracked core fixture. */\n')
            for name in ('n71-wlan-msi-message.h', 'n71-wlan-irq-reference.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    if before:
                        self.assertIn(before, source)
                    (folder / 'n71-wlan-msi-native.h').write_text(source if before is None else source.replace(before, after))
                    binary = folder / 'msi'
                    compiled = subprocess.run(
                        [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                         '-I', str(folder), str(ROOT / 'tests/n71_wlan_msi_native.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                    executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                    if before is None:
                        self.assertEqual(executed.returncode, 0, executed.stderr)
                        self.assertIn('N71_WLAN_MSI_NATIVE_OK cases=', executed.stdout)
                        print(executed.stdout.strip())
                    else:
                        self.assertEqual(executed.returncode, -6, name + executed.stderr)
                        self.assertIn('assert', executed.stderr.lower())


if __name__ == '__main__':
    unittest.main()
