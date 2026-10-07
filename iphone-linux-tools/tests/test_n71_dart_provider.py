"""Run real provider acquisition/recovery callbacks with tracked kernel resources."""
from pathlib import Path
import resource
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('free-after-failure', 'if (error)\n\t\treturn error;\n\tif (provider->mmio.regs)',
     'if (false)\n\t\treturn error;\n\tif (provider->mmio.regs)'),
    ('lose-owner', 'state->dart = provider;', 'state->dart = NULL;'),
    ('forget-bound', 'provider->bound = false;', '(void)0;'),
    ('dispose-existing', 'if (provider->new_mapping)', 'if (provider->irq)'),
    ('skip-stopped', '!provider->lease.stopped ||', 'false ||'),
    ('skip-guard', '!provider->restore_guard ||', 'false ||'),
    ('skip-index', 'index != provider->lease.restore_index ||', 'false ||'),
    ('skip-value', 'value != provider->lease.saved.ttbr[index]', 'false'),
    ('reuse-grant', 'provider->restore_guard = false;\n\tprovider->writes++;',
     'provider->restore_guard = true;\n\tprovider->writes++;'),
    ('skip-unmap', 'iounmap(provider->mmio.regs);', '(void)provider->mmio.regs;'),
    ('skip-free', 'kfree(provider);', '(void)provider;'),
    ('skip-node-put', 'of_node_put(provider->node);', '(void)provider->node;'),
    ('skip-claim-release', 'if (provider->claimed)\n\t\trelease_mem_region',
     'if (false)\n\t\trelease_mem_region'),
    ('lose-primary-error', 'state->primary_error = provider->lease.operation_error;', '(void)0;'),
)


class DartProviderTests(unittest.TestCase):
    def test_production_cleanup_preserves_bus_power_and_module_until_dart_recovers(self):
        source = (ROOT / 'phone/kernel/n71-pcie-diagnostic.c').read_text()
        functions = []
        for name in ('n71_session_cleanup', 'n71_finish_cleanup'):
            match = re.search(r'static int ' + name + r'\([^)]*\)\n\{', source)
            self.assertIsNotNone(match, name)
            position, depth = match.end(), 1
            while depth:
                self.assertLess(position, len(source))
                depth += (source[position] == '{') - (source[position] == '}')
                position += 1
            functions.append(source[match.start():position])
        extracted = '\n'.join(functions)
        mutations = (
            ('ignore-dart-pending', 'if (error || state->dart)', 'if (false)'),
            ('ignore-scan-pending', 'if (error || state->scan_bridge)', 'if (false)'),
            ('drop-module-on-error', 'if (!state->cleanup_error && !state->dart && !state->scan_bridge && !state->reset_pending &&\n'
             '\t    !state->powered && !state->attached && !state->power_put_pending && state->module_retained)',
             'if (state->module_retained)'),
        )
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        with tempfile.TemporaryDirectory(prefix='n71-dart-cleanup-') as directory:
            folder = Path(directory)
            header, binary = folder / 'n71-dart-cleanup-under-test.h', folder / 'cleanup'
            for name, before, after in (('baseline', None, None),) + mutations:
                with self.subTest(name=name):
                    if before:
                        self.assertIn(before, extracted)
                    header.write_text(extracted if before is None else extracted.replace(before, after))
                    compiled = subprocess.run(
                        [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                         '-I', str(folder), str(ROOT / 'tests/n71_dart_cleanup.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                    executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                    if before is None:
                        self.assertEqual(executed.returncode, 0, executed.stderr)
                        self.assertIn('N71_DART_CLEANUP_OK cases=4', executed.stdout)
                        print(executed.stdout.strip())
                    else:
                        self.assertEqual(executed.returncode, -6, executed.stderr)
                        self.assertIn('assert', executed.stderr.lower())

    def test_production_callbacks_and_compiled_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-dart-provider.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-dart-provider-') as directory:
            folder = Path(directory)
            (folder / 'linux').mkdir()
            for name in ('irqdomain.h', 'of_irq.h'):
                (folder / 'linux' / name).write_text('/* APIs supplied by the resource fixture. */\n')
            for name in ('n71-dart-lease.h', 'n71-dart-cycle.h', 'n71-dart-observe.h', 'n71-pcie-contract.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            header, binary = folder / 'n71-dart-provider.h', folder / 'provider'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                with self.subTest(name=name):
                    if before:
                        self.assertIn(before, source)
                    header.write_text(source if before is None else source.replace(before, after))
                    compiled = subprocess.run(
                        [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                         '-I', str(folder), str(ROOT / 'tests/n71_dart_provider.c'), '-o', str(binary)],
                        capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                    executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
                    if before is None:
                        self.assertEqual(executed.returncode, 0, executed.stderr)
                        self.assertIn('N71_DART_PROVIDER_OK cases=', executed.stdout)
                        print(executed.stdout.strip())
                    else:
                        self.assertEqual(executed.returncode, -6, name + executed.stderr)
                        self.assertIn('assert', executed.stderr.lower())


if __name__ == '__main__':
    unittest.main()
