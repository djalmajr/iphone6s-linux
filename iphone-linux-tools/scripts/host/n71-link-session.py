#!/usr/bin/env python3
"""One bounded N71 endpoint discovery, with fresh latch and cleanup evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import device_profile

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


class Session:
    def __init__(self, output, modules):
        self.output = output
        self.modules = modules
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
        for line in process.stdout.splitlines():
            if 'N71_' in line or line.startswith('bound='):
                print(line, flush=True)
        print('N71_STAGE', stage, 'exit', process.returncode, flush=True)
        return process

    def preflight(self):
        p = self.capture('preflight', 'set -e; uname -r; uptime; '
                         'test ! -d /sys/module/n71_wlan_power_diagnostic; '
                         'test ! -d /sys/module/n71_pcie_diagnostic; '
                         'for n in i2c@20a111000 serial@20a0d4000; do '
                         'test -f /sys/firmware/devicetree/base/soc/$n/status; '
                         's=$(tr "\\000" "\\n" </sys/firmware/devicetree/base/soc/$n/status); '
                         'test "$s" = disabled; echo "N71_DT_DISABLED $n"; done; dmesg')
        require(p.returncode == 0 and p.stdout.startswith(RELEASE + '\n'),
                'Selected release and disabled HDQ resources not proved')
        require('N71_PCIE_' not in p.stdout, 'A PCIe diagnostic already exists in this boot')
        for record, raw in self.modules:
            target = '/run/' + record['module']
            p = self.capture('transfer-' + record['module'],
                             'umask 077; set -C; cat > ' + target, raw)
            require(p.returncode == 0, 'Module transfer failed')
            p = self.capture('hash-' + record['module'],
                             'echo "' + record['sha256'] + '  ' + target + '" | sha256sum -c -')
            require(p.returncode == 0, 'Remote module hash not proved')

    def experiment(self):
        self.preflight()
        self.reg_attempted = True
        p = self.capture('observe', 'set -e; insmod /run/n71-wlan-power-diagnostic.ko run=1; '
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
        p = self.capture('pcie', 'set -e; '
                         'test "$(cat ' + REG + 'state)" = "' + STATE_ACTIVE + '"; '
                         'test "$(cat ' + REG + 'control)" = "N71_REG_ON_CONTROL_READBACK value=81"; '
                         'insmod /run/n71-pcie-diagnostic.ko run=1 enumerate=1; dmesg')
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

    def cleanup(self):
        failures = []
        if self.pcie_attempted:
            try:
                p = self.capture('pcie-cleanup', 'dmesg')
                require(p.returncode == 0
                        and 'N71_PCIE_RESET_RESTORED asserted=1 readback=1' in p.stdout
                        and 'N71_PCIE_POWER_RELEASED powered=0 attached=0' in p.stdout,
                        'PCIe reset/power cleanup not proved')
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
    records = json.loads((ROOT / 'docs/evidence/kernel-n71-bundle-build.json').read_text())['diagnostic_modules']['modules']
    modules = [(record, module_bytes(profile['payload'].parent, record)) for record in records]
    if options.check:
        print('N71_SESSION_LOCAL_GATE_OK; no SSH or USB action')
        return 0
    require(options.output_dir is not None, 'New private output required')
    output = options.output_dir.absolute()
    require(output.parent == ROOT / 'runtime' and not output.exists() and not output.is_symlink(),
            'Output must be new, directly under runtime')
    device_profile.protected(output.parent, directory=True)
    output.mkdir(mode=0o700)
    return Session(output, modules).run()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, struct.error) as error:
        raise SystemExit('N71_SESSION_REFUSED: ' + str(error)) from error
