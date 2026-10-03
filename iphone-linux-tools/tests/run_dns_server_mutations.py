#!/usr/bin/env python3
"""Run real server mutations only after a passing isolated VM baseline."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'phone/dns/manage-dns.sh'
TEST = ROOT / 'tests/test_dns_server_vm.py'
MUTATIONS = {
    'kernel-bind': [('--bind-interfaces ', '')],
    'root-user': [('--user=nobody', '--user=root')],
    'external-upstream': [('--no-resolv ', ''), ("'--local=/#/' ", '')],
    'stale-pid': [('    [ "$(process_ticks "$pid")" = "$ticks" ] || return 2\n', '')],
    'foreign-executable': [('    [ "$(readlink "/proc/$pid/exe")" = "$BINARY" ] || return 2\n', '')],
}
EXPECTED_FAILURES = {
    'kernel-bind': ('Unexpected kernel bind', 'Unexpected IPv6 DNS listener'),
    'root-user': ('DNS retained root privileges',),
    'external-upstream': ('Unexpected negative DNS behavior', 'DNS forwarded an external query'),
    'stale-pid': ('Stale start-time record signaled process',),
    'foreign-executable': ('Foreign executable received signal',),
}


def baseline_passed(result):
    lines = result.stderr.splitlines()
    return (result.returncode == 0 and 'OK' in lines
            and any(line.startswith('Ran 1 test in ') for line in lines)
            and not any(line.startswith(('FAIL:', 'ERROR:')) or 'skipped' in line for line in lines))


def expected_assertion(result, name):
    lines = result.stderr.splitlines()
    return (result.returncode != 0 and any(line.startswith('FAIL:') for line in lines)
            and not any(line.startswith('ERROR:') or 'skipped' in line for line in lines)
            and any(line.startswith('AssertionError: ' + message)
                    for line in lines for message in EXPECTED_FAILURES[name]))


def run(base):
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s',
                           str(base / 'tests'), '-p', 'test_dns_server_vm.py', '-v'],
                          capture_output=True, text=True, timeout=55)


if __name__ == '__main__':
    if not (sys.platform == 'linux' and os.geteuid() == 0 and
            os.environ.get('IPHONE_DNS_VM_TESTS') == '1'):
        raise SystemExit('Explicit dedicated VM/root opt-in required')
    names = sys.argv[1:] or list(MUTATIONS)
    if any(name not in MUTATIONS for name in names):
        raise SystemExit('Unknown mutation')
    original = SOURCE.read_text()
    with tempfile.TemporaryDirectory(prefix='iphone-dns-mutations-') as folder:
        base = Path(folder)
        target = base / 'phone/dns/manage-dns.sh'
        target.parent.mkdir(parents=True)
        (base / 'tests').mkdir()
        shutil.copy(TEST, base / 'tests' / TEST.name)
        target.write_text(original)
        result = run(base)
        if not baseline_passed(result):
            raise SystemExit('Original baseline failed:\n' + result.stdout + result.stderr)
        print('Original DNS server baseline passed', flush=True)
        for name in names:
            mutated = original
            for before, after in MUTATIONS[name]:
                if mutated.count(before) != 1:
                    raise SystemExit('Mutation anchor is not unique: ' + name)
                mutated = mutated.replace(before, after)
            target.write_text(mutated)
            result = run(base)
            if not expected_assertion(result, name):
                raise SystemExit('Mutation survived or failed outside expected assertion: ' + name
                                 + '\n' + result.stdout + result.stderr)
            print('Rejected ' + name, flush=True)
