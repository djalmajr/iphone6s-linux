#!/usr/bin/env python3
"""One bounded N71 endpoint discovery, with fresh latch and cleanup evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import struct
import subprocess
import sys
import device_profile
import n71_bar_result
import n71_chip_result
import n71_dart_result
import n71_dart_cycle_result
import n71_scan_result
import n71_scan_target_result
import n71_scan_pme_result
import n71_session_history
import n71_scan_held_result
import n71_resource_result
import n71_held_session
import n71_iommu_result
import n71_iommu_build
import n71_driver_runtime_profile
import n71_driver_runtime_result

ROOT = Path(__file__).resolve().parents[2]
RELEASE = '7.2.0-iphone6s-dart-serdev1'
BINDING_RELEASE = '7.2.0-iphone6s-dart-serdev-power2'
PROFILE_RELEASES = {'n71-dart-serdev-v1': RELEASE, 'n71-dart-serdev-power-v2': BINDING_RELEASE}
REG = '/sys/module/n71_wlan_power_diagnostic/parameters/'
STATE_ACTIVE = 'bound=1 active=1 restore_pending=1 original=80'
PCIE = '/sys/module/n71_pcie_diagnostic/parameters/'
ASPM_BOOTARGS = b'chosen.bootargs=rdinit=/init console=ttySAC0,115200 loglevel=7 pcie_aspm=off\n'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def selected_release(metadata, payload_sha256):
    release = PROFILE_RELEASES.get(metadata.get('kernel_patchset'))
    require(release is not None and metadata.get('kernel_release') == release
            and metadata.get('payload_sha256') == payload_sha256, 'Selected profile provenance differs')
    return release


def module_bytes(profile, record, *, release=RELEASE):
    require(release in PROFILE_RELEASES.values(), 'Unsupported diagnostic release')
    path = profile / record['module']
    device_profile.protected(path)
    require(path.stat().st_size == record['bytes'], 'Module size differs')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == record['sha256'], 'Module hash differs')
    magic = ('vermagic=' + release + ' SMP preempt mod_unload aarch64\0').encode()
    require(raw[:7] == b'\x7fELF\x02\x01\x01' and
            struct.unpack_from('<HH', raw, 16) == (1, 183) and raw.count(magic) == 1,
            'Module requires the selected AArch64 ABI')
    return raw


def aspm_payload(profile, metadata):
    loader = json.loads((ROOT / 'docs/evidence/m1n1-rebuild.json').read_text())['shallow_clone']
    require(loader['matches_original'] is True and 64 <= loader['bytes'] <= 2 * 1024 * 1024,
            'Recorded loader required for ASPM payload')
    with profile['payload'].open('rb') as stream:
        prefix = stream.read(loader['bytes'] + len(ASPM_BOOTARGS))
    require(hashlib.sha256(prefix[:loader['bytes']]).hexdigest() == loader['sha256']
            and prefix[loader['bytes']:] == ASPM_BOOTARGS
            and metadata.get('bootargs_sha256') == hashlib.sha256(ASPM_BOOTARGS).hexdigest(),
            'Exact ASPM payload bootargs and loader required')
    return len(prefix)


def selected_records(config_inventory, host_scan=False, bar_sizing=False, chip_id=False, *, dart_observe=False, dart_cycle=False, release=RELEASE, scan_link_target=False, scan_pme_noop=False, scan_pme_disable=False, scan_hold=False, resource_capable=False, resource_module_sha256=None, iommu_parent=False):
    require(type(iommu_parent) is bool and (not iommu_parent or (resource_capable and scan_hold)),
            'IOMMU selection requires exact boolean and held resources')
    require(type(resource_capable) is bool and (not resource_capable or scan_hold),
            'Resource capability requires an explicit boolean and held mode')
    require(host_scan + bar_sizing + chip_id + dart_observe + dart_cycle <= 1, 'Diagnostic modes are mutually exclusive')
    require(release in PROFILE_RELEASES.values(), 'Unsupported diagnostic release')
    require(not scan_pme_noop or scan_link_target, 'PME no-op scan requires target scan')
    require(not scan_pme_disable or (scan_link_target and not scan_pme_noop), 'Endpoint PME requires its own target candidate')
    require(not scan_hold or (host_scan and scan_link_target and scan_pme_disable
                              and not scan_pme_noop and release == BINDING_RELEASE),
            'Held scan requires its explicit power2 host/target/PME candidate')
    if scan_hold:
        if resource_capable:
            if iommu_parent:
                selection = {'pcie_sha256': resource_module_sha256, 'iommu_parent': True}
                return n71_resource_result.selected_records(ROOT, release=release, **selection)
            if resource_module_sha256 is not None:
                return n71_resource_result.selected_records(ROOT, release=release, pcie_sha256=resource_module_sha256)
            return n71_resource_result.selected_records(ROOT, release=release)
        return n71_scan_held_result.selected_records(ROOT, release=release)
    if scan_link_target:
        require(host_scan and release == BINDING_RELEASE, 'Target scan requires host-scan and power2')
        name = 'n71-pcie-pme-noop-build.json' if scan_pme_noop else 'n71-pcie-scan-target-build.json'
        if scan_pme_disable:
            name = 'n71-pcie-pme-aspm-build.json'
        evidence = json.loads((ROOT / 'docs/evidence' / name).read_text())
        build = evidence['module_build']
        require(evidence['kernel_release'] == release and evidence['kernel_patchset'] == 'n71-dart-serdev-power-v2'
                and build['modpost_passed'] is True and build['werror'] is True
                and evidence['contract']['module_pin_while_pending'] is True
                and evidence['contract']['bind_attributes_suppressed'] is True, 'Target scan build differs')
        if scan_pme_noop:
            require(evidence['contract']['pme_noop_without_write'] is True
                    and evidence['contract']['active_pme_status_refused'] is True
                    and evidence['contract']['same_word_rechecked'] is True
                    and evidence['contract']['pme_root_only'] is True, 'PME no-op contract differs')
        if scan_pme_disable:
            require(evidence['contract']['endpoint_pme_disable_restore'] is True
                    and evidence['contract']['pme_enable_only'] is True
                    and evidence['contract']['raw_pme_w1c_writes'] is False
                    and evidence['contract']['active_pme_status_refused'] is True
                    and evidence['contract']['same_word_rechecked'] is True
                    and evidence['contract']['caller_opt_in_required'] is True
                    and evidence['contract']['bridge_retained_until_config_pme_tls_verified'] is True
                    and evidence['contract']['aspm_off_required'] is True, 'Endpoint PME/ASPM contract differs')
        records = [dict(evidence['selected_modules'][name], module=name)
                   for name in ('n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko')]
        require(all(r['vermagic'] == release + ' SMP preempt mod_unload aarch64' for r in records),
                'Target scan ABI differs')
        return records
    if release == BINDING_RELEASE:
        evidence = json.loads((ROOT / 'docs/evidence/n71-binding-profile.json').read_text())
        build = evidence['module_build']
        require(evidence['diagnostic_profile']['kernel_release'] == release
                and evidence['diagnostic_profile']['kernel_patchset'] == 'n71-dart-serdev-power-v2'
                and build['werror'] is True and build['modpost_passed'] is True,
                'Binding diagnostic build identity differs')
        records = [dict(build['modules'][name], module=name)
                   for name in ('n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko')]
        require(all(record['vermagic'] == release + ' SMP preempt mod_unload aarch64' for record in records),
                'Binding diagnostic module ABI differs')
        return records
    records = json.loads((ROOT / 'docs/evidence/kernel-n71-bundle-build.json').read_text())['diagnostic_modules']['modules']
    if config_inventory or host_scan or bar_sizing or chip_id or dart_observe or dart_cycle:
        name = ('n71-dart-cycle-build.json' if dart_cycle else
                'n71-dart-state-build.json' if dart_observe else
                'n71-pcie-chip-id-build.json' if chip_id else
                'n71-pcie-bar-sizing.json' if bar_sizing else
                'n71-pcie-controls-scan-build.json' if host_scan else 'n71-pcie-config-inventory.json')
        evidence = json.loads((ROOT / 'docs/evidence' / name).read_text())
        require(evidence['kernel_release'] == RELEASE, 'Inventory ABI differs')
        records = [dict(evidence['module'], module=record['module'])
                   if record['module'] == 'n71-pcie-diagnostic.ko' else record for record in records]
    return records


def inventory_result(text):
    def one(pattern):
        matches = re.findall(pattern, text)
        require(len(matches) == 1, 'Exactly one complete inventory record required')
        return tuple(int(value, 16) for value in matches[0])

    require(re.findall(r'N71_PCIE_INVENTORY_RESULT error=(-?\d+); no config writes', text) == ['0'],
            'Successful unique inventory result required')
    revision, header, subsystem = one(r'N71_PCIE_INVENTORY class-revision=([0-9a-f]{8}) header=([0-9a-f]{8}) subsystem=([0-9a-f]{8})')
    matches = re.findall(r'N71_PCIE_INVENTORY command-status=([0-9a-f]{8}) interrupt=([0-9a-f]{8}) reads=(\d+) caps=(\d+)', text)
    require(len(matches) == 1, 'Unique inventory counts required')
    command, interrupt, reads, caps = matches[0]
    require(not (int(command, 16) & 4) and not ((header >> 16) & 0x7f),
            'Endpoint header and bus-master clear required')
    require(1 <= int(reads) <= 63 and 1 <= int(caps) <= 48, 'Inventory budget differs')
    bars = re.findall(r'N71_PCIE_BAR_RAW index=(\d+) value=([0-9a-f]{8}); no sizing or MMIO access', text)
    require([int(index) for index, _ in bars] == list(range(6)), 'Six ordered unique raw BARs required')
    capabilities = one(r'N71_PCIE_CAP_RAW express=([0-9a-f]{2})/([0-9a-f]{8}) msi=([0-9a-f]{2})/([0-9a-f]{8}) msix=([0-9a-f]{2})/([0-9a-f]{8})')
    offsets = []
    for index, expected in enumerate((0x10, 5, 0x11)):
        offset, raw = capabilities[index * 2:index * 2 + 2]
        require((index != 0 and offset == raw == 0) or
                (0x40 <= offset <= (0xcc if index == 0 else 0xfc) and offset % 4 == 0
                 and raw & 0xff == expected), 'Capability identity or bounds differ')
        if offset:
            offsets.append(offset)
    require(len(offsets) == len(set(offsets)), 'Capability offsets overlap')
    express = capabilities[1]
    require((express >> 16) & 0xf and (express >> 20) & 0xf in (0, 1), 'PCIe endpoint capability required')
    return {'class_revision': revision, 'header': header, 'subsystem': subsystem,
            'command_status': int(command, 16), 'interrupt': int(interrupt, 16),
            'reads': int(reads), 'capabilities': int(caps),
            'bars_raw': [int(value, 16) for _, value in bars], 'capability_headers_raw': capabilities}


class Session:
    def __init__(self, output, modules, *, config_inventory=False, host_scan=False, bar_sizing=False, chip_id=False, dart_observe=False, dart_cycle=False, history=None, scan_link_target=False, release=RELEASE, scan_pme_disable=False, scan_hold=False, resource_capable=False, iommu_parent=False, runtime=None):
        require(type(resource_capable) is bool and (not resource_capable or scan_hold),
                'Resource session requires an explicit boolean and held mode')
        require(host_scan + bar_sizing + chip_id + dart_observe + dart_cycle <= 1, 'Diagnostic modes are mutually exclusive')
        require(release in PROFILE_RELEASES.values(), 'Unsupported diagnostic release')
        require(not scan_link_target or (host_scan and release == BINDING_RELEASE), 'Target session requires host-scan and power2')
        require(not scan_pme_disable or scan_link_target, 'Endpoint PME session requires target mode')
        require(not scan_hold or (host_scan and scan_link_target and scan_pme_disable and release == BINDING_RELEASE),
                'Held session requires its explicit power2 host/target/PME candidate')
        self.scan_hold = scan_hold
        self.iommu_parent = iommu_parent
        self.resource_capable = resource_capable
        self.resource_attempted = False
        self.resource_assignment = None
        self.scan_link_target = scan_link_target
        self.scan_pme_disable = scan_pme_disable
        self.scan_parser = n71_scan_pme_result if scan_pme_disable else n71_scan_target_result if scan_link_target else n71_scan_result
        if scan_hold:
            self.scan_parser = n71_scan_held_result
        self.release = release
        self.output = output
        self.modules = modules
        self.driver_runtime = False
        self.driver_modules = None
        self.driver_module_data = []
        self.driver_runtime_journal = []; self.driver_module_journal = []
        if runtime is not None:
            n71_driver_runtime_profile.configure(self, {'root': ROOT, 'modules': runtime})
        n71_iommu_result.selected(self, ROOT)
        self.config_inventory = config_inventory or host_scan or bar_sizing or chip_id or dart_observe or dart_cycle
        self.host_scan = host_scan
        self.bar_sizing = bar_sizing or chip_id
        self.chip_id = chip_id
        self.dart_observe = dart_observe
        self.dart_cycle = dart_cycle
        self.history = history
        self.module_directory = '/run/n71-link-' + secrets.token_hex(12) if history or scan_hold else '/run'
        self.before_effect = lambda: None
        self.ssh = device_profile.ssh_options() + ['root@' + device_profile.PHONE]
        self.reg_attempted = False
        self.activation_attempted = False
        self.pcie_attempted = False
        self.result = {'kernel_release': self.release, 'endpoint_identified': False,
                       'cleanup_verified': False, 'wifi_verified': False,
                       'hdq_io_performed': False, 'dma_enabled': False}

    def capture(self, stage, command, raw=None):
        path = self.output / (stage + '-private.log')
        # Reserve the log before issuing any command: a repeated stage is refused.
        with path.open('xb') as log:
            try:
                process = subprocess.run(self.ssh + [command], input=raw,
                                         capture_output=True, timeout=35)
            except subprocess.TimeoutExpired as error:
                log.write((error.stdout or b'') + b'\nSSH_TIMEOUT\n' + (error.stderr or b''))
                raise ValueError('SSH stage timed out: ' + stage) from error
            log.write(process.stdout + b'\nSTDERR\n' + process.stderr)
        process.stdout = process.stdout.decode(errors='replace')
        if self.history and stage != 'preflight':
            process.stdout = self.history.fresh(process.stdout)
        for line in process.stdout.splitlines():
            if ('N71_' in line or line.startswith('bound=')) and 'N71_DART_TTBR ' not in line and not (self.history and line in self.history.known):
                print(line, flush=True)
        print('N71_STAGE', stage, 'exit', process.returncode, flush=True)
        return process

    def preflight(self):
        n71_driver_runtime_profile.selected(self, ROOT)
        p = self.capture('preflight', 'set -e; uname -r; uptime; '
                         'printf "N71_BOOT_ID "; cat /proc/sys/kernel/random/boot_id; '
                         'test ! -d /sys/module/n71_wlan_power_diagnostic; '
                         'test ! -d /sys/module/n71_pcie_diagnostic; '
                         'for n in i2c@20a111000 serial@20a0d4000; do '
                         'test -f /sys/firmware/devicetree/base/soc/$n/status; '
                         's=$(tr "\\000" "\\n" </sys/firmware/devicetree/base/soc/$n/status); '
                         'test "$s" = disabled; echo "N71_DT_DISABLED $n"; done; dmesg')
        require(p.returncode == 0 and p.stdout.startswith(self.release + '\n'),
                'Selected release and disabled HDQ resources not proved')
        boot = re.findall(r'^N71_BOOT_ID ([0-9a-f-]{36})$', p.stdout, re.M)
        require(len(boot) == 1, 'Unique live boot identity required')
        self.result['boot_id'] = boot[0]
        preflight_text = p.stdout
        if self.scan_pme_disable:
            p = self.capture('aspm', 'set -e; printf "N71_PCIE_CMDLINE "; cat /proc/cmdline; '
                             'dmesg | grep -F "PCIe ASPM is disabled" >/dev/null; echo N71_PCIE_ASPM_DISABLED')
            rows = re.findall(r'^N71_PCIE_CMDLINE (.*)$', p.stdout, re.M)
            require(p.returncode == 0 and len(rows) == 1
                    and [arg for arg in rows[0].split() if arg.startswith('pcie_aspm=')] == ['pcie_aspm=off']
                    and p.stdout.splitlines().count('N71_PCIE_ASPM_DISABLED') == 1, 'Live ASPM off not proved')
            self.result['aspm_off_verified'] = True
        if self.history:
            self.history.verify_live(preflight_text)
        else:
            require('N71_PCIE_' not in preflight_text, 'A PCIe diagnostic already exists in this boot')
        if self.history or self.scan_hold:
            p = self.capture('module-directory', 'umask 077; mkdir -m 700 ' + self.module_directory)
            require(p.returncode == 0, 'Exclusive remote module directory not created')
        if self.host_scan or self.bar_sizing or self.dart_observe or self.dart_cycle or self.history:
            p = self.capture('pci-empty', 'set -e; test -z "$(ls /sys/bus/pci/devices)"; echo N71_PCI_PREFLIGHT_EMPTY')
            require(p.returncode == 0, 'Pre-existing PCI devices refused')
        if n71_driver_runtime_result.capable(self):
            p = self.capture('runtime-stack-empty', n71_driver_runtime_profile.preflight_command())
            require(p.returncode == 0 and p.stdout.splitlines().count('N71_RUNTIME_STACK_EMPTY') == 1,
                    'Pre-existing runtime modules or driver refused')
        for record, raw in self.modules + n71_driver_runtime_profile.staged(self):
            target = self.module_directory + '/' + record['module']
            p = self.capture('transfer-' + record['module'],
                             'umask 077; set -C; cat > ' + target, raw)
            require(p.returncode == 0, 'Module transfer failed')
            p = self.capture('hash-' + record['module'],
                             'echo "' + record['sha256'] + '  ' + target + '" | sha256sum -c -')
            require(p.returncode == 0, 'Remote module hash not proved')

    def experiment(self):
        self.preflight()
        self.reg_attempted = True
        self.before_effect()
        p = self.capture('observe', 'set -e; insmod ' + self.module_directory + '/n71-wlan-power-diagnostic.ko run=1; '
                         'cat ' + REG + 'state; cat ' + REG + 'control; dmesg')
        require(p.returncode == 0 and 'N71_REG_ON_OBSERVED control=80 bit0=0 compatible-plan=1' in p.stdout
                and 'N71_REG_ON_PARENT simple-mfd-i2c shared-regmap; no rebind' in p.stdout
                and 'bound=1 active=0 restore_pending=0' in p.stdout
                and 'N71_REG_ON_CONTROL_READBACK value=80' in p.stdout,
                'Exact original latch and owner not proved')
        self.activation_attempted = True
        self.before_effect()
        p = self.capture('activate', 'set -e; printf "1\n" > ' + REG + 'power; '
                         'cat ' + REG + 'state; cat ' + REG + 'control; cat ' + REG + 'level; dmesg')
        require(p.returncode == 0 and STATE_ACTIVE in p.stdout
                and 'N71_REG_ON_CONTROL_READBACK value=81' in p.stdout,
                'Fresh acquired latch not proved')
        # Repeat the fresh checks on the phone immediately before the single insmod.
        self.pcie_attempted = True
        self.before_effect()
        parameters = ' config_inventory=1' if self.config_inventory else ''
        if self.host_scan:
            parameters += ' host_scan=1'
        if self.scan_pme_disable:
            parameters += ' scan_pme_disable=1'
        if self.scan_hold:
            parameters += ' scan_hold=1'
        if self.iommu_parent:
            parameters += ' msi_parent=1 iommu_parent=1'
        if n71_driver_runtime_result.capable(self):
            parameters += ' driver_runtime=1'
        if self.chip_id:
            parameters += ' chip_id=1'
        elif self.bar_sizing:
            parameters += ' bar_sizing=1'
        elif self.dart_observe:
            parameters += ' dart_observe=1'
        elif self.dart_cycle:
            parameters += ' dart_cycle=1'
        status = 'printf "N71_PCIE_STATUS "; cat ' + PCIE + 'status; ' if self.scan_link_target else ''
        if self.scan_hold:
            status += 'printf "N71_PCIE_HELD "; cat ' + PCIE + 'held; '
        status += n71_iommu_result.getter(self)
        p = self.capture('pcie', 'set -e; '
                         'test "$(cat ' + REG + 'state)" = "' + STATE_ACTIVE + '"; '
                         'test "$(cat ' + REG + 'control)" = "N71_REG_ON_CONTROL_READBACK value=81"; '
                         'insmod ' + self.module_directory + '/n71-pcie-diagnostic.ko run=1 enumerate=1' + parameters + '; ' + status + 'dmesg')
        require(p.returncode == 0, 'PCIe command did not complete')
        matches = re.findall(r'N71_PCIE_LINK_RESULT error=(-?\d+) port88=([0-9a-f]+) reads=(\d+)', p.stdout)
        require(len(matches) == 1, 'Exactly one completed link result required')
        error, status, reads = matches[0]
        require(0 <= int(reads) <= 10000, 'Link read budget exceeded')
        self.result['link'] = {'error': int(error), 'port88': status, 'reads': int(reads)}
        identities = re.findall(r'N71_PCIE_ENDPOINT_ID=([0-9a-f]{8}); bus-master clear; no radio', p.stdout)
        if int(error) == 0:
            require(int(status, 16) & 1 and len(identities) == 1
                    and identities[0] not in ('00000000', 'ffffffff'),
                    'Successful link lacks unique endpoint evidence')
            self.result['endpoint_identified'] = True
            self.result['endpoint_id'] = identities[0]
        if self.config_inventory:
            require(int(error) == 0 and identities == ['43a314e4'], 'Measured inventory endpoint required')
            self.result['inventory'] = inventory_result(p.stdout)
        if self.host_scan:
            parser = self.scan_parser
            self.result['host_scan'] = parser.parse(p.stdout)
        if self.bar_sizing:
            self.result['bar_sizing'] = n71_bar_result.parse(p.stdout, self.result['inventory']['bars_raw'])
        if self.chip_id:
            self.result['chip_id'] = n71_chip_result.parse(p.stdout)
        if self.dart_observe:
            self.result['dart_observation'] = n71_dart_result.parse(p.stdout)
        if self.dart_cycle:
            self.result['dart_cycle'] = n71_dart_cycle_result.parse(p.stdout)
        n71_iommu_result.retained(self, p.stdout)

    def cleanup(self):
        failures = []
        pcie_released = not self.pcie_attempted
        if self.pcie_attempted:
            try:
                command = 'dmesg'
                if self.scan_link_target:
                    require('boot_id' in self.result, 'Cleanup requires this live boot identity')
                    live = ('set -e; test "$(uname -r)" = "' + self.release + '"; '
                            'test "$(cat /proc/sys/kernel/random/boot_id)" = "' + self.result['boot_id'] + '"; '
                            'test ! -e /sys/bus/platform/drivers/n71-pcie-diagnostic/bind; '
                            'test ! -e /sys/bus/platform/drivers/n71-pcie-diagnostic/unbind; ')
                    p = self.capture('pcie-status', live + 'printf "N71_PCIE_STATUS "; cat ' + PCIE + 'status')
                    require(p.returncode == 0, 'Live caller status unavailable; retain REG_ON')
                    state = n71_scan_target_result.live_status(p.stdout)
                    if not n71_scan_target_result.is_clean(state):
                        p = self.capture('pcie-retry', live + 'if printf "cleanup\n" > ' + PCIE
                                         + 'action; then cleanup_exit=0; else cleanup_exit=$?; fi; '
                                         'printf "N71_PCIE_STATUS "; cat ' + PCIE + 'status; dmesg; exit "$cleanup_exit"')
                        require(p.returncode == 0 and n71_scan_target_result.is_clean(n71_scan_target_result.live_status(p.stdout)),
                                'Bounded caller cleanup failed; retain REG_ON')
                    command = live + 'printf "N71_PCIE_STATUS "; cat ' + PCIE + 'status; dmesg'
                p = self.capture('pcie-cleanup', command)
                require(p.returncode == 0
                        and 'N71_PCIE_RESET_RESTORED asserted=1 readback=1' in p.stdout
                        and 'N71_PCIE_POWER_RELEASED powered=0 attached=0' in p.stdout,
                        'PCIe reset/power cleanup not proved')
                if self.host_scan or self.bar_sizing:
                    parser = n71_bar_result if self.bar_sizing else self.scan_parser
                    parser.cleanup(p.stdout)
                    if self.chip_id:
                        n71_chip_result.cleanup(p.stdout)
                if self.dart_observe:
                    n71_dart_result.cleanup(p.stdout)
                if self.dart_cycle:
                    n71_dart_cycle_result.cleanup(p.stdout)
                if self.host_scan or self.bar_sizing or self.dart_observe or self.dart_cycle:
                    p = self.capture('pci-empty-after', 'set -e; test -z "$(ls /sys/bus/pci/devices)"; echo N71_PCI_CLEANUP_EMPTY')
                    require(p.returncode == 0, 'PCI devices remain after cleanup')
                p = self.capture('pcie-unload', 'set -e; rmmod n71_pcie_diagnostic; '
                                 'test ! -d /sys/module/n71_pcie_diagnostic; echo N71_PCIE_UNLOADED')
                require(p.returncode == 0, 'PCIe unload not proved')
                pcie_released = True
            except (ValueError, OSError) as error:
                failures.append(str(error))
        if self.reg_attempted and pcie_released:
            try:
                release = 'printf "0\n" > ' + REG + 'power; ' if self.activation_attempted else ''
                p = self.capture('restore', 'set -e; '
                                 'if [ ! -d /sys/module/n71_wlan_power_diagnostic ]; then '
                                 'echo N71_REG_MODULE_ABSENT; exit 0; fi; '
                                 + release + 'cat ' + REG + 'state; '
                                 'cat ' + REG + 'control; dmesg')
                absent = 'N71_REG_MODULE_ABSENT' in p.stdout and not self.activation_attempted
                restored = ('bound=1 active=0 restore_pending=0' in p.stdout
                            and (not self.activation_attempted
                                 or 'N71_REG_ON_CONTROL_READBACK value=80' in p.stdout))
                require(p.returncode == 0 and (absent or restored), 'REG_ON restore not proved; do not unload')
                if not absent:
                    p = self.capture('reg-unload', 'set -e; rmmod n71_wlan_power_diagnostic; '
                                     'test ! -d /sys/module/n71_wlan_power_diagnostic; '
                                     'echo N71_REG_UNLOADED; dmesg')
                    require(p.returncode == 0 and 'N71_REG_ON_REMOVE error=0 restore_pending=0' in p.stdout,
                            'REG_ON unload not proved')
            except (ValueError, OSError) as error:
                failures.append(str(error))
        self.result['cleanup_verified'] = not failures
        self.result['cleanup_errors'] = failures
        self.result['reg_on_release_skipped'] = self.reg_attempted and not pcie_released

    def run(self):
        require(not self.scan_hold, 'Held session requires its durable coordinator')
        try:
            self.experiment()
        except (ValueError, OSError, KeyboardInterrupt) as error:
            self.result['experiment_error'] = str(error)
        finally:
            self.cleanup()
        with (self.output / 'result-private.json').open('x') as file:
            json.dump(self.result, file, indent=2)
            file.write('\n')
        print('N71_SESSION_RESULT', json.dumps(self.result), flush=True)
        return 0 if self.result['cleanup_verified'] and 'experiment_error' not in self.result else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--check', action='store_true', help='Local gates only, no SSH')
    parser.add_argument('--config-inventory', action='store_true', help='Require the separately recorded read-only inventory module')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--host-scan', action='store_true', help='Select recorded PCI-core sizing module; implies inventory')
    parser.add_argument('--scan-link-target', action='store_true', help='Explicit power2 host-scan candidate with retained TLS/caller cleanup')
    parser.add_argument('--scan-pme-noop', action='store_true', help='Explicit target candidate with inactive root PME acknowledgement without a write')
    parser.add_argument('--scan-pme-disable', action='store_true', help='Explicit endpoint PME disable/restore candidate; requires ASPM off')
    parser.add_argument('--scan-hold', action='store_true', help='Retain the qualified PCI bus and power owners until explicit same-boot release')
    parser.add_argument('--resource-capable', action='store_true', help='Select the qualified held module with explicit resource assignment support')
    parser.add_argument('--iommu-parent', action='store_true', help='Select qualified retained IOMMU association; requires held resources and matching Image')
    held_actions = parser.add_mutually_exclusive_group()
    held_actions.add_argument('--release-held', type=Path, help='Release owners from a private held session in this exact boot; requires --scan-hold')
    held_actions.add_argument('--assign-held', type=Path, help='Assign PCI resources in this saved held boot; requires --resource-capable')
    modes.add_argument('--bar-sizing', action='store_true', help='Select endpoint-only BAR sizing module; implies inventory')
    modes.add_argument('--chip-id', action='store_true', help='Read ChipCommon ID once via restored BAR0 route; implies sizing/inventory')
    modes.add_argument('--dart-observe', action='store_true', help='Read stable DART state without provider activation; implies inventory')
    modes.add_argument('--dart-cycle', action='store_true', help='Test temporary provider and restore tables; requires prior complete private observation')
    parser.add_argument('--previous-clean', type=Path, help='Continue only after matching private cleanup and this boot history')
    options = parser.parse_args()
    require(not options.iommu_parent or options.resource_capable, 'IOMMU requires explicit resource capability')
    require(not options.release_held or (options.scan_hold and options.previous_clean is None),
            'Held release requires held mode without previous-clean')
    require(not options.assign_held or (options.resource_capable and options.previous_clean is None and options.scan_hold),
            'Held assignment requires resource-capable held mode without previous-clean')
    os.umask(0o077)
    os.environ['IPHONE_LINUX_PROFILE'] = str(options.profile.absolute())
    profile = device_profile.verify()
    provenance = profile['payload'].parent / 'provenance.json'
    device_profile.protected(provenance)
    require(provenance.stat().st_size <= 8192, 'Provenance size refused')
    metadata = json.loads(provenance.read_text())
    release = selected_release(metadata, profile['sha256'])
    require(metadata.get('pcie_scan_link_target', False) is options.scan_link_target, 'Target profile selection differs')
    require(metadata.get('pcie_scan_pme_noop', False) is options.scan_pme_noop, 'PME profile selection differs')
    require(metadata.get('pcie_scan_pme_disable', False) is options.scan_pme_disable, 'Endpoint PME profile selection differs')
    require(metadata.get('pcie_aspm_off', False) is options.scan_pme_disable, 'ASPM profile selection differs')
    require(metadata.get('pcie_scan_hold', False) is options.scan_hold, 'Held profile selection differs')
    require(metadata.get('pcie_resource_capable', False) is options.resource_capable, 'Resource profile selection differs')
    require(metadata.get('pcie_iommu_parent', False) is options.iommu_parent, 'IOMMU profile selection differs')
    if options.scan_pme_disable:
        prefix_bytes = aspm_payload(profile, metadata)
    if options.iommu_parent:
        require(options.scan_hold and options.scan_pme_disable, 'IOMMU requires held power2/PME profile')
        n71_iommu_build.payload_image(ROOT, profile, metadata, prefix_bytes=prefix_bytes, release=release)
    records = selected_records(options.config_inventory, options.host_scan, options.bar_sizing, options.chip_id,
                               dart_observe=options.dart_observe, dart_cycle=options.dart_cycle, release=release,
                               scan_link_target=options.scan_link_target, scan_pme_noop=options.scan_pme_noop,
                               scan_pme_disable=options.scan_pme_disable, scan_hold=options.scan_hold,
                               resource_capable=options.resource_capable,
                               resource_module_sha256=metadata['module_sha256'] if options.resource_capable else None,
                               iommu_parent=options.iommu_parent)
    if release == BINDING_RELEASE or options.config_inventory or options.host_scan or options.bar_sizing or options.chip_id or options.dart_observe or options.dart_cycle:
        require(metadata['module_sha256'] == records[0]['sha256'], 'Inventory profile provenance differs')
    modules = [(record, module_bytes(profile['payload'].parent, record, release=release)) for record in records]
    held_identity = n71_held_session.identity(options.profile.absolute(), profile, modules) if options.scan_hold else None
    history = n71_session_history.History(options.previous_clean, ROOT, release) if options.previous_clean else None
    if options.dart_cycle:
        require(history is not None, 'Provider cycle requires prior private same-boot cleanup')
        n71_dart_cycle_result.previous(options.previous_clean.absolute())
    if options.check:
        if options.release_held or options.assign_held:
            session = Session(ROOT / 'runtime', modules, host_scan=True, scan_link_target=True,
                              scan_pme_disable=True, scan_hold=True, release=release,
                              resource_capable=options.resource_capable, iommu_parent=options.iommu_parent)
            n71_held_session.load_source(session, ROOT, options.release_held or options.assign_held, held_identity)
        print('N71_SESSION_LOCAL_GATE_OK; no SSH or USB action')
        return 0
    require(options.output_dir is not None, 'New private output required')
    output = options.output_dir.absolute()
    require(output.parent == ROOT / 'runtime' and not output.exists() and not output.is_symlink(),
            'Output must be new, directly under runtime')
    device_profile.protected(output.parent, directory=True)
    output.mkdir(mode=0o700)
    if options.scan_hold:
        session = Session(output, modules, host_scan=options.host_scan, scan_link_target=options.scan_link_target,
                          scan_pme_disable=options.scan_pme_disable, scan_hold=True, release=release, history=history,
                          resource_capable=options.resource_capable, iommu_parent=options.iommu_parent)
        return n71_held_session.run(session, held_identity, root=ROOT, source=options.release_held or options.assign_held,
                                    assign=options.assign_held is not None)
    return Session(output, modules, config_inventory=options.config_inventory,
                   host_scan=options.host_scan, bar_sizing=options.bar_sizing,
                   chip_id=options.chip_id, dart_observe=options.dart_observe,
                   dart_cycle=options.dart_cycle, scan_pme_disable=options.scan_pme_disable,
                   history=history, scan_link_target=options.scan_link_target, release=release).run()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, struct.error) as error:
        raise SystemExit('N71_SESSION_REFUSED: ' + str(error)) from error
