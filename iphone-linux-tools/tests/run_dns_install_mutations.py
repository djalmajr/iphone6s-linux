#!/usr/bin/env python3
"""Reject installer scope/identity mutations after a real isolated baseline."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    'existing-data': ([
        ("test ! -e \"$base\" || {{ echo 'DNS already has files; use start/restore, not install.' >&2; exit 1; }}\n", ''),
        ('test ! -e "$base"\n', ''),
    ], 'Install overwrote existing configuration'),
    'symlink-parent': ([
        ('''for parent in /srv /srv/data "$base"; do
    test ! -L "$parent" || {{ echo 'Symlink parent refused.' >&2; exit 1; }}
done
''', ''),
    ], 'Install followed symlink parent'),
    'bundle-identity': ([
        ("if len(data) != report['bundle_bytes'] or digest != report['bundle_sha256']:", 'if False:'),
    ], 'Bundle identity change accepted'),
    'name-scope': ([
        ("if (not name.endswith('.home.arpa') or len(name) > 253 or\n"
         "            any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)\n"
         "                for label in labels)):", 'if False:'),
    ], 'FAIL: test_record_rejects_names_and_addresses_before_ssh'),
    'address-scope': ([
        ('if not any(address in network for network in lan.PRIVATE):', 'if False:'),
    ], 'FAIL: test_record_rejects_names_and_addresses_before_ssh'),
}


def run(base, isolated_input=False):
    command = [sys.executable, str(base / 'tests/test_dns_install.py'), '-v']
    if isolated_input:
        command = ['unshare', '--net', '--'] + command + ['DnsInputTests']
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=65)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=5)
        raise SystemExit('Fixture timed out:\n' + stdout + stderr)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


if __name__ == '__main__':
    if not (sys.platform == 'linux' and os.geteuid() == 0 and
            os.environ.get('IPHONE_DNS_VM_TESTS') == '1'):
        raise SystemExit('Explicit dedicated VM/root opt-in required')
    original = (ROOT / 'scripts/host/dns.py').read_text()
    with tempfile.TemporaryDirectory(prefix='iphone-dns-install-mutations-') as folder:
        base = Path(folder)
        for directory in ('scripts/host', 'tests', 'phone/dns', 'docs/evidence'):
            (base / directory).mkdir(parents=True)
        for source in (ROOT / 'scripts/host').glob('*.py'):
            shutil.copy(source, base / 'scripts/host' / source.name)
        for name in ('test_dns_install.py', 'test_lan.py'):
            shutil.copy(ROOT / 'tests' / name, base / 'tests' / name)
        for name in ('phone/dns/manage-dns.sh', 'docs/evidence/dns-provenance.json'):
            shutil.copy(ROOT / name, base / name)
        target = base / 'scripts/host/dns.py'
        result = run(base)
        if result.returncode != 0 or 'skipped' in result.stderr:
            raise SystemExit('Original baseline failed:\n' + result.stdout + result.stderr)
        print('Original DNS installer baseline passed (2 tests)', flush=True)
        for name, (changes, expected) in MUTATIONS.items():
            mutated = original
            for before, after in changes:
                if mutated.count(before) != 1:
                    raise SystemExit('Mutation anchor is not unique: ' + name)
                mutated = mutated.replace(before, after)
            target.write_text(mutated)
            result = run(base, isolated_input=name in ('name-scope', 'address-scope'))
            if (result.returncode == 0 or 'skipped' in result.stderr
                    or expected not in result.stderr):
                raise SystemExit('Mutation survived or failed for an unexpected reason: '
                                 + name + '\n' + result.stdout + result.stderr)
            print('Rejected ' + name, flush=True)
