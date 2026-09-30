#!/usr/bin/env python3
"""Reject LAN safety regressions in disposable public-source copies."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCAL = 'test_lan.LanTests.test_invalid_bind_and_ports_fail_before_keys_or_network'
VM = 'test_lan.LanVmTests.test_real_forwarding_security_and_cleanup_in_owned_namespace'
MUTATIONS = (
    ('public-bind', "if str(address) != '127.0.0.1' and not any(address in network for network in PRIVATE):", 'if False:', LOCAL),
    ('usb-bind', "if address in ipaddress.ip_network('172.16.42.0/24'):", 'if False:', LOCAL),
    ('privileged-port', 'if not 1024 <= number <= 65535:', 'if not 1 <= number <= 65535:', LOCAL),
    ('strict-trust', "'StrictHostKeyChecking=yes'", "'StrictHostKeyChecking=no'", VM),
    ('listen-failure', "'ExitOnForwardFailure=yes'", "'ExitOnForwardFailure=no'", VM),
    ('omitted-bind', "f'{options.bind}:{options.ssh_port}:{PHONE}:22'", "f'{options.ssh_port}:{PHONE}:22'", VM),
    ('wildcard-bind', "f'{options.bind}:{options.http_port}:{PHONE}:8080'", "f'0.0.0.0:{options.http_port}:{PHONE}:8080'", VM),
)


def main():
    requested = set(sys.argv[1:])
    unknown = requested - {entry[0] for entry in MUTATIONS}
    if unknown:
        raise SystemExit('Unknown mutation labels: ' + ', '.join(sorted(unknown)))
    ready_vm = sys.platform == 'linux' and os.geteuid() == 0 and os.environ.get('IPHONE_LAN_VM_TESTS') == '1'
    baselines = {test for label, _old, _new, test in MUTATIONS
                 if (not requested or label in requested) and (test != VM or ready_vm)}
    for test in sorted(baselines):
        result = subprocess.run([sys.executable, '-m', 'unittest', test, '-v'], cwd=ROOT / 'tests',
                                capture_output=True, text=True, timeout=40)
        if result.returncode != 0:
            print(result.stdout + result.stderr)
            raise SystemExit('Baseline failed; no mutation evidence accepted')
    print('Unmodified baseline passed', flush=True)
    rejected, unavailable = 0, 0
    for label, old, new, test in MUTATIONS:
        if requested and label not in requested:
            continue
        if test == VM and not ready_vm:
            if requested:
                raise SystemExit(label + ': requires explicit disposable VM/root opt-in')
            unavailable += 1
            continue
        with tempfile.TemporaryDirectory(prefix='iphone-lan-mutation-') as temporary:
            project = Path(temporary)
            host = project / 'scripts/host'
            tests = project / 'tests'
            host.mkdir(parents=True)
            tests.mkdir()
            source = (ROOT / 'scripts/host/lan.py').read_text()
            if source.count(old) != 1:
                raise SystemExit(label + ': source anchor must occur once')
            (host / 'lan.py').write_text(source.replace(old, new))
            shutil.copy(ROOT / 'tests/test_lan.py', tests / 'test_lan.py')
            result = subprocess.run([sys.executable, '-m', 'unittest', test, '-v'], cwd=tests,
                                    capture_output=True, text=True, timeout=40)
            if result.returncode == 0 or 'FAILED (failures=' not in result.stderr:
                print(result.stdout + result.stderr)
                raise SystemExit(label + ': survived or failed outside assertion gate')
            print(label + ': rejected', flush=True)
            rejected += 1
    print(f'{rejected} mutations rejected; {unavailable} VM mutations not executed; disposable copies removed.')


if __name__ == '__main__':
    main()
