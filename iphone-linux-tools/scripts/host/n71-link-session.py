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
import n71_scan_result
import n71_session_history

ROOT = Path(__file__).resolve().parents[2]
RELEASE = '7.2.0-iphone6s-dart-serdev1'
REG = '/sys/module/n71_wlan_power_diagnostic/parameters/'
STATE_ACTIVE = 'bound=1 active=1 restore_pending=1 original=80'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def module_bytes(profile, record):
    path = profile / record['module']
    device_profile.protected(path)
    require(path.stat().st_size == record['bytes'], 'Module size differs')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == record['sha256'], 'Module hash differs')
    magic = ('vermagic=' + RELEASE + ' SMP preempt mod_unload aarch64\0').encode()
    require(raw[:7] == b'\x7fELF\x02\x01\x01' and
            struct.unpack_from('<HH', raw, 16) == (1, 183) and raw.count(magic) == 1,
            'Module requires the selected AArch64 ABI')
    return raw


def selected_records(config_inventory, host_scan=False, bar_sizing=False, chip_id=False, *, dart_observe=False):
    require(host_scan + bar_sizing + chip_id + dart_observe <= 1, 'Diagnostic modes are mutually exclusive')
    records = json.loads((ROOT / 'docs/evidence/kernel-n71-bundle-build.json').read_text())['diagnostic_modules']['modules']
    if config_inventory or host_scan or bar_sizing or chip_id or dart_observe:
        name = ('n71-dart-observe-build.json' if dart_observe else
                'n71-pcie-chip-id-build.json' if chip_id else
                'n71-pcie-bar-sizing.json' if bar_sizing else
                'n71-pcie-host-scan.json' if host_scan else 'n71-pcie-config-inventory.json')
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
    def __init__(self, output, modules, *, config_inventory=False, host_scan=False, bar_sizing=False, chip_id=False, dart_observe=False, history=None):
        require(host_scan + bar_sizing + chip_id + dart_observe <= 1, 'Diagnostic modes are mutually exclusive')
        self.output = output
        self.modules = modules
        self.config_inventory = config_inventory or host_scan or bar_sizing or chip_id or dart_observe
        self.host_scan = host_scan
        self.bar_sizing = bar_sizing or chip_id
        self.chip_id = chip_id
        self.dart_observe = dart_observe
        self.history = history
        self.module_directory = '/run/n71-link-' + secrets.token_hex(12) if history else '/run'
        self.ssh = device_profile.ssh_options() + ['root@' + device_profile.PHONE]
        self.reg_attempted = False
        self.activation_attempted = False
        self.pcie_attempted = False
        self.result = {'kernel_release': RELEASE, 'endpoint_identified': False,
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
        p = self.capture('preflight', 'set -e; uname -r; uptime; '
                         'printf "N71_BOOT_ID "; cat /proc/sys/kernel/random/boot_id; '
                         'test ! -d /sys/module/n71_wlan_power_diagnostic; '
                         'test ! -d /sys/module/n71_pcie_diagnostic; '
                         'for n in i2c@20a111000 serial@20a0d4000; do '
                         'test -f /sys/firmware/devicetree/base/soc/$n/status; '
                         's=$(tr "\\000" "\\n" </sys/firmware/devicetree/base/soc/$n/status); '
                         'test "$s" = disabled; echo "N71_DT_DISABLED $n"; done; dmesg')
        require(p.returncode == 0 and p.stdout.startswith(RELEASE + '\n'),
                'Selected release and disabled HDQ resources not proved')
        boot = re.findall(r'^N71_BOOT_ID ([0-9a-f-]{36})$', p.stdout, re.M)
        require(len(boot) == 1, 'Unique live boot identity required')
        self.result['boot_id'] = boot[0]
        if self.history:
            self.history.verify_live(p.stdout)
            p = self.capture('module-directory', 'umask 077; mkdir -m 700 ' + self.module_directory)
            require(p.returncode == 0, 'Exclusive remote module directory not created')
        else:
            require('N71_PCIE_' not in p.stdout, 'A PCIe diagnostic already exists in this boot')
        if self.host_scan or self.bar_sizing or self.dart_observe or self.history:
            p = self.capture('pci-empty', 'set -e; test -z "$(ls /sys/bus/pci/devices)"; echo N71_PCI_PREFLIGHT_EMPTY')
            require(p.returncode == 0, 'Pre-existing PCI devices refused')
        for record, raw in self.modules:
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
        p = self.capture('observe', 'set -e; insmod ' + self.module_directory + '/n71-wlan-power-diagnostic.ko run=1; '
                         'cat ' + REG + 'state; cat ' + REG + 'control; dmesg')
        require(p.returncode == 0 and 'N71_REG_ON_OBSERVED control=80 bit0=0 compatible-plan=1' in p.stdout
                and 'N71_REG_ON_PARENT simple-mfd-i2c shared-regmap; no rebind' in p.stdout
                and 'bound=1 active=0 restore_pending=0' in p.stdout
                and 'N71_REG_ON_CONTROL_READBACK value=80' in p.stdout,
                'Exact original latch and owner not proved')
        self.activation_attempted = True
        p = self.capture('activate', 'set -e; printf "1\n" > ' + REG + 'power; '
                         'cat ' + REG + 'state; cat ' + REG + 'control; cat ' + REG + 'level; dmesg')
        require(p.returncode == 0 and STATE_ACTIVE in p.stdout
                and 'N71_REG_ON_CONTROL_READBACK value=81' in p.stdout,
                'Fresh acquired latch not proved')
        # Repeat the fresh checks on the phone immediately before the single insmod.
        self.pcie_attempted = True
        parameters = ' config_inventory=1' if self.config_inventory else ''
        if self.host_scan:
            parameters += ' host_scan=1'
        if self.chip_id:
            parameters += ' chip_id=1'
        elif self.bar_sizing:
            parameters += ' bar_sizing=1'
        elif self.dart_observe:
            parameters += ' dart_observe=1'
        p = self.capture('pcie', 'set -e; '
                         'test "$(cat ' + REG + 'state)" = "' + STATE_ACTIVE + '"; '
                         'test "$(cat ' + REG + 'control)" = "N71_REG_ON_CONTROL_READBACK value=81"; '
                         'insmod ' + self.module_directory + '/n71-pcie-diagnostic.ko run=1 enumerate=1' + parameters + '; dmesg')
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
            self.result['host_scan'] = n71_scan_result.parse(p.stdout)
        if self.bar_sizing:
            self.result['bar_sizing'] = n71_bar_result.parse(p.stdout, self.result['inventory']['bars_raw'])
        if self.chip_id:
            self.result['chip_id'] = n71_chip_result.parse(p.stdout)
        if self.dart_observe:
            self.result['dart_observation'] = n71_dart_result.parse(p.stdout)

    def cleanup(self):
        failures = []
        if self.pcie_attempted:
            try:
                p = self.capture('pcie-cleanup', 'dmesg')
                require(p.returncode == 0
                        and 'N71_PCIE_RESET_RESTORED asserted=1 readback=1' in p.stdout
                        and 'N71_PCIE_POWER_RELEASED powered=0 attached=0' in p.stdout,
                        'PCIe reset/power cleanup not proved')
                if self.host_scan or self.bar_sizing:
                    (n71_bar_result if self.bar_sizing else n71_scan_result).cleanup(p.stdout)
                    if self.chip_id:
                        n71_chip_result.cleanup(p.stdout)
                if self.dart_observe:
                    n71_dart_result.cleanup(p.stdout)
                if self.host_scan or self.bar_sizing or self.dart_observe:
                    p = self.capture('pci-empty-after', 'set -e; test -z "$(ls /sys/bus/pci/devices)"; echo N71_PCI_CLEANUP_EMPTY')
                    require(p.returncode == 0, 'PCI devices remain after cleanup')
                p = self.capture('pcie-unload', 'set -e; rmmod n71_pcie_diagnostic; '
                                 'test ! -d /sys/module/n71_pcie_diagnostic; echo N71_PCIE_UNLOADED')
                require(p.returncode == 0, 'PCIe unload not proved')
            except (ValueError, OSError) as error:
                failures.append(str(error))
        if self.reg_attempted:
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

    def run(self):
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
    modes.add_argument('--bar-sizing', action='store_true', help='Select endpoint-only BAR sizing module; implies inventory')
    modes.add_argument('--chip-id', action='store_true', help='Read ChipCommon ID once via restored BAR0 route; implies sizing/inventory')
    modes.add_argument('--dart-observe', action='store_true', help='Read stable DART state without provider activation; implies inventory')
    parser.add_argument('--previous-clean', type=Path, help='Continue only after matching private cleanup and this boot history')
    options = parser.parse_args()
    os.umask(0o077)
    os.environ['IPHONE_LINUX_PROFILE'] = str(options.profile.absolute())
    profile = device_profile.verify()
    provenance = profile['payload'].parent / 'provenance.json'
    device_profile.protected(provenance)
    require(provenance.stat().st_size <= 8192, 'Provenance size refused')
    metadata = json.loads(provenance.read_text())
    require(metadata['kernel_release'] == RELEASE and metadata['kernel_patchset'] == 'n71-dart-serdev-v1'
            and metadata['payload_sha256'] == profile['sha256'], 'Selected profile provenance differs')
    records = selected_records(options.config_inventory, options.host_scan, options.bar_sizing, options.chip_id,
                               dart_observe=options.dart_observe)
    if options.config_inventory or options.host_scan or options.bar_sizing or options.chip_id or options.dart_observe:
        require(metadata['module_sha256'] == records[0]['sha256'], 'Inventory profile provenance differs')
    modules = [(record, module_bytes(profile['payload'].parent, record)) for record in records]
    history = n71_session_history.History(options.previous_clean, ROOT, RELEASE) if options.previous_clean else None
    if options.check:
        print('N71_SESSION_LOCAL_GATE_OK; no SSH or USB action')
        return 0
    require(options.output_dir is not None, 'New private output required')
    output = options.output_dir.absolute()
    require(output.parent == ROOT / 'runtime' and not output.exists() and not output.is_symlink(),
            'Output must be new, directly under runtime')
    device_profile.protected(output.parent, directory=True)
    output.mkdir(mode=0o700)
    return Session(output, modules, config_inventory=options.config_inventory,
                   host_scan=options.host_scan, bar_sizing=options.bar_sizing,
                   chip_id=options.chip_id, dart_observe=options.dart_observe, history=history).run()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, struct.error) as error:
        raise SystemExit('N71_SESSION_REFUSED: ' + str(error)) from error
