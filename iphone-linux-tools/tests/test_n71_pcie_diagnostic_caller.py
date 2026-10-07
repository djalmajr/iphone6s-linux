"""Compile the real caller and MMIO backend with fault-injected kernel dependencies."""
from pathlib import Path
import resource
import re
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
    ('skip-scan-cleanup', 'error = n71_pcie_scan_cleanup(state);', 'error = false ? n71_pcie_scan_cleanup(state) : 0;'),
    ('skip-reset-cleanup', 'if (state->reset_pending) {', 'if (false) {'),
    ('ignore-reset-error', 'if (error)\n\t\t\treturn error;\n\t\tstate->reset_pending', 'if (false)\n\t\t\treturn error;\n\t\tstate->reset_pending'),
    ('skip-power-release', 'error = n71_release_power(state);', 'error = false ? n71_release_power(state) : 0;'),
    ('ignore-power-status', '!pm_runtime_status_suspended(domain)', '(false && !pm_runtime_status_suspended(domain))'),
    ('duplicate-power-put', 'error = pm_runtime_suspend(domain);',
     'error = false ? pm_runtime_suspend(domain) : pm_runtime_put_sync_suspend(domain);'),
    ('ignore-power-error', 'if (error < 0 ||', 'if ((false && error < 0) ||'),
    ('early-unpin', 'if (!state->cleanup_error && !state->dart && !state->scan_bridge && !state->reset_pending &&\n\t    !state->powered && !state->attached && !state->power_put_pending && state->module_retained)',
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
    ('hold-by-default', 'if (scan_hold)\n\t\t\t\terror =',
     'if (true || scan_hold)\n\t\t\t\terror ='),
    ('ignore-hold-opt-in', 'if (scan_hold)\n\t\t\t\terror =',
     'if (false && scan_hold)\n\t\t\t\terror ='),
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
RESOURCE_MUTATIONS = (
    ('ignore-assign-dispatch', 'if (sysfs_streq(text, "assign"))',
     'if (false && sysfs_streq(text, "assign"))'),
    ('assign-without-opt-in', 'if (!scan_hold)\n\t\treturn -EINVAL;',
     'if (false && !scan_hold)\n\t\treturn -EINVAL;'),
    ('missing-assign-pin', 'pinned = try_module_get(THIS_MODULE);', 'pinned = true;'),
    ('ignore-assign-pin-failure', 'if (!pinned)', 'if (false && !pinned)'),
    ('assign-without-lock', 'mutex_lock(&session_lock);\n\tif (!session ||',
     'if (false) mutex_lock(&session_lock);\n\tif (!session ||'),
    ('assign-without-held-bus', '!session || !n71_session_has_held_bus(session)', '!session'),
    ('assign-without-retained-owner', '!session->module_retained || !session->reset_pending ||',
     '(false && !session->module_retained) || !session->reset_pending ||'),
    ('assign-without-reset-owner', '!session->module_retained || !session->reset_pending ||',
     '!session->module_retained || (false && !session->reset_pending) ||'),
    ('assign-with-partial-power', 'session->powered != 4', '(false && session->powered != 4)'),
    ('assign-with-partial-domains', 'session->attached != 4', '(false && session->attached != 4)'),
    ('assign-with-pending-power-put', 'session->power_put_pending ||\n\t\t   session->primary_error',
     '(false && session->power_put_pending) ||\n\t\t   session->primary_error'),
    ('assign-after-primary-error', 'session->primary_error || session->cleanup_error)',
     '(false && session->primary_error) || session->cleanup_error)'),
    ('assign-after-cleanup-error', 'session->primary_error || session->cleanup_error)',
     'session->primary_error || (false && session->cleanup_error))'),
    ('skip-assign-effects', 'error = n71_pcie_assign_resources(session);',
     'error = false ? n71_pcie_assign_resources(session) : 0;'),
    ('lose-assign-error', 'session->primary_error = error;', 'session->primary_error = 0;'),
    ('ealready-poisons-session', 'error != -EALREADY && !session->primary_error',
     'true && !session->primary_error'),
    ('leak-assign-pin', 'module_put(THIS_MODULE);\n\treturn error;',
     'if (false) module_put(THIS_MODULE);\n\treturn error;'),
    ('duplicate-assign-unpin', 'module_put(THIS_MODULE);\n\treturn error;',
     'module_put(THIS_MODULE); module_put(THIS_MODULE);\n\treturn error;'),
    ('resources-getter-without-lock', 'mutex_lock(&session_lock);\n\tif (session && session->scan_bridge)',
     'if (false) mutex_lock(&session_lock);\n\tif (session && session->scan_bridge)'),
    ('assigned-after-bus-removal', 'assigned = session->scan_bridge->bus &&', 'assigned = true &&'),
    ('assigned-without-bus-owner', 'host->bus_held && host->resources_assigned &&',
     'true && host->resources_assigned &&'),
    ('assigned-without-assignment', 'host->bus_held && host->resources_assigned &&',
     'host->bus_held && true &&'),
    ('assigned-without-window-claim', 'host->window_claimed && host->windows[1].parent',
     'true && host->windows[1].parent'),
    ('assigned-with-foreign-window', 'host->windows[1].parent == &iomem_resource &&',
     '(true || host->windows[1].parent == &iomem_resource) &&'),
    ('assigned-during-active-phase', '!host->resources.active && !error;',
     '(true || !host->resources.active) && !error;'),
    ('assigned-after-error', '!host->resources.active && !error;',
     '!host->resources.active && (true || !error);'),
    ('resources-hides-primary-error', 'error = session->primary_error ? session->primary_error :',
     'error = false && session->primary_error ? session->primary_error :'),
    ('resources-hides-policy-error', 'host->io_error ? host->io_error : host->resources.error;',
     'host->io_error ? host->io_error : 0;'),
    ('resources-hides-error-after-release', 'session ? session->primary_error : 0);',
     'session ? 0 : 0);'),
)
DART_MUTATIONS = (
    ('dart-ignore-hold-dispatch', 'n71_cleanup_action', 'if (sysfs_streq(text, "dart-hold"))',
     'if (false && sysfs_streq(text, "dart-hold"))'),
    ('dart-ignore-release-dispatch', 'n71_cleanup_action', 'if (sysfs_streq(text, "dart-release"))',
     'if (false && sysfs_streq(text, "dart-release"))'),
    ('dart-without-opt-in', 'n71_dart_action', 'if (!scan_hold)', 'if (false && !scan_hold)'),
    ('dart-missing-pin', 'n71_dart_action', 'if (!try_module_get(THIS_MODULE))',
     'if (false && !try_module_get(THIS_MODULE))'),
    ('dart-without-lock', 'n71_dart_action', 'mutex_lock(&session_lock);',
     'if (false) mutex_lock(&session_lock);'),
    ('dart-skip-acquire', 'n71_dart_action', 'error = n71_pcie_dart_acquire(session_device, session);',
     'error = false ? n71_pcie_dart_acquire(session_device, session) : 0;'),
    ('dart-skip-release', 'n71_dart_action', 'error = n71_pcie_dart_cleanup(session_device, session);',
     'error = false ? n71_pcie_dart_cleanup(session_device, session) : 0;'),
    ('dart-lose-primary-error', 'n71_dart_action', 'session->primary_error = error;',
     'session->primary_error = 0;'),
    ('dart-ealready-poisons-session', 'n71_dart_action', 'error != -EALREADY', 'true'),
    ('dart-leak-action-pin', 'n71_dart_action', 'module_put(THIS_MODULE);',
     'if (false) module_put(THIS_MODULE);'),
    ('dart-getter-without-lock', 'n71_dart_status', 'mutex_lock(&session_lock);',
     'if (false) mutex_lock(&session_lock);'),
    ('dart-getter-always-ready', 'n71_dart_status', '!!session, !!provider', '1, !!provider'),
    ('dart-getter-hides-pending', 'n71_dart_status', 'provider ? n71_dart_lease_pending(&provider->lease) : 0',
     'false && provider ? n71_dart_lease_pending(&provider->lease) : 0'),
    ('dart-cleanup-skips-owner', 'n71_session_cleanup',
     'error = n71_pcie_dart_cleanup(session_device, state);',
     'error = false ? n71_pcie_dart_cleanup(session_device, state) : 0;'),
    ('dart-cleanup-ignores-pending', 'n71_session_cleanup', 'if (error || state->dart)',
     'if (false && (error || state->dart))'),
)
DART_GUARDS = (
    '!session->module_retained', '!session->reset_pending', 'session->powered != 4',
    'session->attached != 4', 'session->power_put_pending', '!n71_session_has_held_bus(session)',
    'session->primary_error', 'session->cleanup_error', '!host->resources_assigned',
    '!host->window_claimed', 'host->resources.active', 'host->windows[1].parent != &iomem_resource',
    'host->resources.error', 'host->config.error', 'host->io_error',
)
DART_GUARD_ANCHORS = {
    'session->primary_error': ('|| session->primary_error || session->cleanup_error)',
                               '|| (false && session->primary_error) || session->cleanup_error)'),
}
DART_MUTATIONS += tuple((f'dart-missing-guard-{index}', 'n71_dart_action',
                         *DART_GUARD_ANCHORS.get(guard, (guard, f'(false && {guard})')))
                        for index, guard in enumerate(DART_GUARDS))

MSI_MUTATIONS = (
    ('msi-without-held-bus', 'n71_init', '(msi_parent && !scan_hold)',
     '(false && msi_parent && !scan_hold)'),
    ('msi-ignore-opt-in', 'n71_probe_locked', 'msi_parent ? n71_pcie_scan_hold_msi',
     '(false && msi_parent) ? n71_pcie_scan_hold_msi'),
    ('msi-by-default', 'n71_probe_locked', 'msi_parent ? n71_pcie_scan_hold_msi',
     '(true || msi_parent) ? n71_pcie_scan_hold_msi'),
    ('msi-getter-without-lock', 'n71_msi_status', 'mutex_lock(&session_lock);',
     'if (false) mutex_lock(&session_lock);'),
    ('msi-getter-loses-owner', 'n71_msi_status', 'if (session && session->scan_bridge)',
     'if (false && session && session->scan_bridge)'),
    ('msi-getter-hides-request', 'n71_msi_status', 'msi_parent, !!session', 'false && msi_parent, !!session'),
    ('msi-getter-always-ready', 'n71_msi_status', 'msi_parent, !!session', 'msi_parent, 1'),
    ('msi-getter-hides-held-bus', 'n71_msi_status', 'n71_session_has_held_bus(session),',
     'false && n71_session_has_held_bus(session),'),
    ('msi-getter-hides-association', 'n71_msi_status', 'owner ? owner->associated : 0',
     'false && owner ? owner->associated : 0'),
    ('msi-getter-hides-lease', 'n71_msi_status', 'owner ? !!owner->bridge : 0',
     'false && owner ? !!owner->bridge : 0'),
    ('msi-getter-hides-domain', 'n71_msi_status', 'owner ? !!owner->native.domain : 0',
     'false && owner ? !!owner->native.domain : 0'),
    ('msi-getter-hides-mappings', 'n71_msi_status', 'owner->native.domain->mapcount : 0',
     '0U * owner->native.domain->mapcount : 0'),
    ('msi-getter-hides-child', 'n71_msi_status', 'owner ? !!owner->native.child : 0',
     'false && owner ? !!owner->native.child : 0'),
    ('msi-getter-hides-session-error', 'n71_msi_status', 'session ? session->cleanup_error : 0',
     'false && session ? session->cleanup_error : 0'),
)

IOMMU_MUTATIONS = (
    ('iommu-without-msi-contract', 'n71_init', '(iommu_parent && (!msi_parent || !scan_hold))',
     '(false && iommu_parent && (!msi_parent || !scan_hold))'),
    ('iommu-ignore-acquisition', 'n71_probe_locked', 'error = n71_pcie_dart_acquire(dev, state);',
     'error = false ? n71_pcie_dart_acquire(dev, state) : 0;'),
    ('iommu-acquire-by-default', 'n71_probe_locked', 'if (!error && iommu_parent)',
     'if (!error && (true || iommu_parent))'),
    ('iommu-ignore-selection', 'n71_probe_locked', 'if (iommu_parent)', 'if (false && iommu_parent)'),
    ('iommu-stopped-provider', 'n71_probe_locked', '!state->dart->lease.running',
     '(false && !state->dart->lease.running)'),
    ('iommu-missing-device', 'n71_probe_locked', '!state->dart->device', '(false && !state->dart->device)'),
    ('iommu-skip-consumers', 'n71_session_cleanup', 'error = n71_pcie_scan_remove_consumers(state);',
     'error = false ? n71_pcie_scan_remove_consumers(state) : 0;'),
    ('iommu-ignore-consumer-error', 'n71_session_cleanup', 'if (error)\n\t\t\t\treturn error;',
     'if (false)\n\t\t\t\treturn error;'),
    ('iommu-release-live-provider', 'n71_dart_action', 'if (host && host->dart.bridge)',
     'if (false && host && host->dart.bridge)'),
    ('iommu-getter-without-lock', 'n71_iommu_status', 'mutex_lock(&session_lock);',
     'if (false) mutex_lock(&session_lock);'),
    ('iommu-getter-loses-host', 'n71_iommu_status', 'if (session && session->scan_bridge)',
     'if (false && session && session->scan_bridge)'),
    ('iommu-getter-hides-request', 'n71_iommu_status', 'iommu_parent, !!session', 'false && iommu_parent, !!session'),
    ('iommu-getter-always-ready', 'n71_iommu_status', 'iommu_parent, !!session', 'iommu_parent, 1'),
    ('iommu-getter-hides-owner', 'n71_iommu_status', 'host ? !!host->dart.bridge : 0', 'false && host ? !!host->dart.bridge : 0'),
    ('iommu-getter-hides-availability', 'n71_iommu_status', 'host ? host->dart.available : 0', 'false && host ? host->dart.available : 0'),
    ('iommu-getter-hides-map', 'n71_iommu_status', 'host ? host->dart.mapped : 0', 'false && host ? host->dart.mapped : 0'),
    ('iommu-getter-hides-observations', 'n71_iommu_status', 'host ? host->iommu_devices : 0', '0U * (host ? host->iommu_devices : 0)'),
    ('iommu-getter-hides-session-error', 'n71_iommu_status', 'session ? session->cleanup_error : 0', 'false && session ? session->cleanup_error : 0'),
)
IOMMU_CHECKS = (
    'n71_session_has_held_bus(session)', 'host->dart.bridge', 'host->dart.available',
    'host->dart.mapped', 'host->iommu_domain', 'host->iommu_devices == 2',
    '!host->config.error', '!host->io_error',
)
IOMMU_MUTATIONS += tuple(
    (f'iommu-check-missing-{index}', 'n71_iommu_status',
     f'{guard} &&' if index < 7 else f'{guard};',
     f'(true || {guard}) &&' if index < 7 else f'(true || {guard});')
    for index, guard in enumerate(IOMMU_CHECKS))


def function_span(source, name):
    match = re.search(r'static int (?:__init )?' + re.escape(name) + r'\([^)]*\)\n\{', source)
    if match is None:
        raise ValueError('Caller function not found: ' + name)
    position, depth = match.end(), 1
    while depth:
        if position >= len(source):
            raise ValueError('Caller function unterminated: ' + name)
        depth += (source[position] == '{') - (source[position] == '}')
        position += 1
    return match.start(), position


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
            for name in ('n71-pcie-contract.h', 'n71-pcie-mmio.h', 'n71-dart-lease.h', 'n71-dart-cycle.h', 'n71-dart-observe.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            for name in ('port', 'link', 'inventory', 'scan', 'resource-assign', 'chip-mmio'):
                (folder / f'n71-pcie-{name}.h').write_text('/* Dependency supplied by fixture. */\n')
            for name in ('mmio', 'provider'):
                (folder / f'n71-dart-{name}.h').write_text('/* Dependency supplied by fixture. */\n')
            caller, binary = folder / 'n71-pcie-diagnostic.c', folder / 'caller'
            variants = tuple((name, before, after, False) for name, before, after in
                             (('baseline', None, None),) + MUTATIONS + RESOURCE_MUTATIONS)
            variants += tuple((name, before, after, True) for name, before, after in MMIO_MUTATIONS)
            variants += tuple((name, before, after, False) for name, _, before, after in DART_MUTATIONS)
            variants += tuple((name, before, after, False) for name, _, before, after in MSI_MUTATIONS)
            variants += tuple((name, before, after, False) for name, _, before, after in IOMMU_MUTATIONS)
            scoped_functions = {name: function for name, function, _, _ in DART_MUTATIONS + MSI_MUTATIONS + IOMMU_MUTATIONS}
            for name, before, after, mmio in variants:
                subject = mmio_source if mmio else source
                start, end = 0, len(subject)
                if name == 'missing-action-pin':
                    start, end = function_span(subject, 'n71_cleanup_action')
                if name in {entry[0] for entry in RESOURCE_MUTATIONS}:
                    function = ('n71_cleanup_action' if name == 'ignore-assign-dispatch' else
                                'n71_resource_status' if name.startswith(('resources-', 'assigned-')) else
                                'n71_assign_action')
                    start, end = function_span(subject, function)
                if name in scoped_functions:
                    start, end = function_span(subject, scoped_functions[name])
                scoped = subject[start:end]
                if before:
                    self.assertEqual(scoped.count(before), 1, name)
                changed = subject if before is None else subject[:start] + scoped.replace(before, after, 1) + subject[end:]
                caller.write_text(source if before is None or mmio else changed)
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
                    self.assertIn('N71_PCIE_RESOURCE_CALLER_OK cases=27', result.stdout)
                    self.assertIn('N71_DART_CALLER_OK cases=22', result.stdout)
                    self.assertIn('N71_MSI_CALLER_OK cases=13', result.stdout)
                    self.assertIn('N71_IOMMU_CALLER_OK cases=29', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print(f'N71_PCIE_CALLER_ASSERTION_KILL {name}', flush=True)


if __name__ == '__main__':
    unittest.main()
