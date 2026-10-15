#!/usr/bin/env python3
"""Run proxy security mutations only after a real DNS/SSH VM baseline."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    'udp-allowlist': ('dns_lan.py',
                      'if peer[0] not in allowed or not wire.query_valid(message):',
                      'if not wire.query_valid(message):', 'Disallowed UDP client received DNS'),
    'tcp-allowlist': ('dns_lan.py',
                      'if peer[0] not in allowed or not slots.acquire(blocking=False):',
                      'if not slots.acquire(blocking=False):', 'Disallowed TCP client received DNS'),
    'proxy-bind': ('dns_lan.py', 'udp.bind((options.bind, options.port))',
                   "udp.bind(('0.0.0.0', options.port))", 'Unexpected proxy kernel bind'),
    'capacity': ('dns_lan.py', 'if not slots.acquire(blocking=False):',
                 'if not slots.acquire():', 'Excess request queued instead of refused'),
    'forward-failure': ('dns_lan.py', 'ExitOnForwardFailure=yes',
                        'ExitOnForwardFailure=no', 'Failed startup published a proxy'),
    'host-trust': ('device_profile.py', 'StrictHostKeyChecking=yes',
                   'StrictHostKeyChecking=no', 'Failed startup published a proxy'),
    'response-identity': ('dns_transport.py', 'answer[:2] != message[:2] or ',
                          '', 'not raised'),
    'response-size': ('dns_transport.py',
                      "if not 12 <= length <= MAX_MESSAGE:\n            raise ValueError('DNS response size refused')",
                      "if False:\n            raise ValueError('DNS response size refused')", 'not raised'),
}


def run(base):
    process = subprocess.Popen([sys.executable, str(base / 'tests/test_dns_lan.py'), '-v'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=65)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=5)
        raise SystemExit('Fixture timed out:\n' + stdout + stderr)
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


if __name__ == '__main__':
    if not (sys.platform == 'linux' and os.geteuid() == 0 and
            os.environ.get('IPHONE_DNS_VM_TESTS') == '1'):
        raise SystemExit('Explicit dedicated VM/root opt-in required')
    selected = sys.argv[1:] or list(MUTATIONS)
    if any(name not in MUTATIONS for name in selected):
        raise SystemExit('Unknown mutation')
    with tempfile.TemporaryDirectory(prefix='iphone-dns-lan-mutations-') as folder:
        base = Path(folder)
        for name in ('scripts/host', 'tests', 'phone/dns'):
            (base / name).mkdir(parents=True)
        originals = {}
        for source in (ROOT / 'scripts/host').glob('*.py'):
            shutil.copy(source, base / 'scripts/host' / source.name)
            originals[source.name] = source.read_text()
        for name in ('test_lan.py', 'test_dns_lan.py'):
            shutil.copy(ROOT / 'tests' / name, base / 'tests' / name)
        shutil.copy(ROOT / 'phone/dns/manage-dns.sh', base / 'phone/dns/manage-dns.sh')
        result = run(base)
        if result.returncode or 'skipped' in result.stderr:
            raise SystemExit('Original baseline failed:\n' + result.stdout + result.stderr)
        print('Original DNS LAN baseline passed (4 tests; high and standard ports)', flush=True)
        for name in selected:
            source, before, after, expected = MUTATIONS[name]
            original = originals[source]
            if original.count(before) != 1:
                raise SystemExit('Mutation anchor is not unique: ' + name)
            target = base / 'scripts/host' / source
            target.write_text(original.replace(before, after))
            result = run(base)
            target.write_text(original)
            if (result.returncode == 0 or 'skipped' in result.stderr
                    or expected not in result.stderr):
                raise SystemExit('Mutation survived or failed for an unexpected reason: '
                                 + name + '\n' + result.stdout + result.stderr)
            print('Rejected ' + name, flush=True)
