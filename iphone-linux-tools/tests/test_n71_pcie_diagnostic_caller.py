"""Compile the real caller and MMIO backend with fault-injected kernel dependencies."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('missing-retained-pin', '__module_get(THIS_MODULE);', 'if (false) __module_get(THIS_MODULE);'),
    ('missing-action-pin', 'if (!try_module_get(THIS_MODULE))', 'if (false && !try_module_get(THIS_MODULE))'),
    ('ignore-pending-scan', 'if (error || state->scan_bridge)', 'if (false && (error || state->scan_bridge))'),
    ('skip-scan-cleanup', 'int error = n71_pcie_scan_cleanup(state);', 'int error = false ? n71_pcie_scan_cleanup(state) : 0;'),
    ('skip-reset-cleanup', 'if (state->reset_pending) {', 'if (false) {'),
    ('ignore-reset-error', 'if (error)\n\t\t\treturn error;\n\t\tstate->reset_pending', 'if (false)\n\t\t\treturn error;\n\t\tstate->reset_pending'),
    ('skip-power-release', 'error = n71_release_power(state);', 'error = false ? n71_release_power(state) : 0;'),
    ('ignore-power-status', '!pm_runtime_status_suspended(domain)', '(false && !pm_runtime_status_suspended(domain))'),
    ('duplicate-power-put', 'error = pm_runtime_suspend(domain);',
     'error = false ? pm_runtime_suspend(domain) : pm_runtime_put_sync_suspend(domain);'),
    ('ignore-power-error', 'if (error < 0 ||', 'if ((false && error < 0) ||'),
    ('early-unpin', 'if (!state->cleanup_error && !state->scan_bridge && !state->reset_pending &&\n\t    !state->powered && !state->attached && !state->power_put_pending && state->module_retained)',
     'if (state->module_retained)'),
    ('drop-binding-on-pending', 'if (state->module_retained) {', 'if (false) {'),
    ('allow-second-device', 'error = session ? -EBUSY : n71_probe_locked(pdev);', 'error = n71_probe_locked(pdev);'),
    ('lose-primary-error', 'state->primary_error = error;', 'state->primary_error = 0;'),
    ('expose-unbind', '.suppress_bind_attrs = true', '.suppress_bind_attrs = false'),
    ('missing-action-lock', 'mutex_lock(&session_lock);\n\terror = session ? n71_finish_cleanup',
     'if (false) mutex_lock(&session_lock);\n\terror = session ? n71_finish_cleanup'),
    ('ignore-pme-opt-in', 'scan_pme_disable ? n71_pcie_scan_with_pme(dev, state, true)',
     '(false && scan_pme_disable) ? n71_pcie_scan_with_pme(dev, state, true)'),
    ('enable-pme-by-default', 'scan_pme_disable ? n71_pcie_scan_with_pme(dev, state, true)',
     '(true || scan_pme_disable) ? n71_pcie_scan_with_pme(dev, state, true)'),
    ('allow-pme-without-scan', '(scan_pme_disable && !host_scan)',
     '(false && scan_pme_disable && !host_scan)'),
    ('hold-by-default', 'if (scan_hold)\n\t\t\t\terror = n71_pcie_scan_hold',
     'if (true || scan_hold)\n\t\t\t\terror = n71_pcie_scan_hold'),
    ('ignore-hold-opt-in', 'if (scan_hold)\n\t\t\t\terror = n71_pcie_scan_hold',
     'if (false && scan_hold)\n\t\t\t\terror = n71_pcie_scan_hold'),
    ('allow-hold-without-pme', '(scan_hold && (!host_scan || !scan_pme_disable))',
     '(false && scan_hold && (!host_scan || !scan_pme_disable))'),
    ('held-success-without-proof', 'if (n71_session_has_held_bus(state)) {',
     'if (state) {'),
    ('held-open-on-negative', 'if (scan_hold && !error) {', 'if (scan_hold) {'),
    ('cleanup-before-held-return', 'state->primary_error, state->cleanup_error);\n\t\t\treturn 0;',
     'state->primary_error, state->cleanup_error);\n\t\t\tn71_finish_cleanup(state);\n\t\t\treturn 0;'),
    ('held-getter-without-lock', 'mutex_lock(&session_lock);\n\tlength = scnprintf(buffer, PAGE_SIZE, "held=',
     'if (false) mutex_lock(&session_lock);\n\tlength = scnprintf(buffer, PAGE_SIZE, "held='),
    ('held-when-bus-gone', '!state->scan_bridge->bus', 'false'),
    ('held-from-pending-owner', 'return host->bus_held;', 'return host->bus_held || true;'),
)
MMIO_MUTATIONS = (
    ('ignore-gpio-readback', 'return value < 0 ? value : value == asserted ? 0 : -EIO;',
     'return value < 0 ? value : 0;'),
    ('skip-gpio-read', 'value = gpiod_get_value_cansleep(state->perst);',
     'value = false ? gpiod_get_value_cansleep(state->perst) : asserted;'),
)


class N71PcieCaller(unittest.TestCase):
    def test_real_caller_retention_cleanup_and_compiled_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-pcie-diagnostic.c').read_text()
        mmio_source = (ROOT / 'phone/kernel/n71-pcie-mmio.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-pcie-caller-') as directory:
            folder = Path(directory)
            (folder / 'linux/gpio').mkdir(parents=True)
            for name in ('delay', 'gpio/consumer', 'io', 'module', 'mutex', 'string', 'of_address',
                         'platform_device', 'pm_domain', 'pm_runtime'):
                (folder / 'linux' / (name + '.h')).write_text('/* Kernel fixture APIs. */\n')
            for name in ('n71-pcie-contract.h', 'n71-pcie-mmio.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            for name in ('port', 'link', 'inventory', 'scan', 'chip-mmio'):
                (folder / f'n71-pcie-{name}.h').write_text('/* Dependency supplied by fixture. */\n')
            for name in ('mmio', 'provider'):
                (folder / f'n71-dart-{name}.h').write_text('/* Dependency supplied by fixture. */\n')
            caller, binary = folder / 'n71-pcie-diagnostic.c', folder / 'caller'
            variants = tuple((name, before, after, False) for name, before, after in (('baseline', None, None),) + MUTATIONS)
            variants += tuple((name, before, after, True) for name, before, after in MMIO_MUTATIONS)
            for name, before, after, mmio in variants:
                subject = mmio_source if mmio else source
                if before:
                    self.assertEqual(subject.count(before), 1, name)
                caller.write_text(source if before is None or mmio else source.replace(before, after, 1))
                (folder / 'n71-pcie-mmio.h').write_text(mmio_source.replace(before, after, 1) if mmio else mmio_source)
                compiled = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                           '-I', str(folder), str(ROOT / 'tests/n71_pcie_diagnostic_caller.c'),
                                           '-o', str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_PCIE_CALLER_OK cases=73', result.stdout)
                    self.assertIn('N71_PCIE_HELD_CALLER_OK cases=21', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print(f'N71_PCIE_CALLER_ASSERTION_KILL {name}', flush=True)


if __name__ == '__main__':
    unittest.main()
