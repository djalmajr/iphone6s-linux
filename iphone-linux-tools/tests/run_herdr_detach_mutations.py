"""Prove startup rejects missing nohup and lost hangup protection in owned copies."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASE = 'test_start_without_nohup_survives_hangup'
ANCHOR = "(trap '' HUP; exec setsid /usr/local/bin/herdr"
MUTATIONS = {
    'require-missing-nohup': "(trap '' HUP; exec nohup setsid /usr/local/bin/herdr",
    'drop-hangup-protection': '(exec setsid /usr/local/bin/herdr',
}


def run(base):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    environment.pop('IPHONE_LINUX_PROFILE', None)
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                           '-p', 'test_herdr_start.py', '-k', CASE, '-v'], cwd=base,
                          env=environment, capture_output=True, text=True, timeout=30)


def main():
    with tempfile.TemporaryDirectory(prefix='iphone-herdr-detach-') as directory:
        base = Path(directory)
        shutil.copytree(ROOT / 'scripts/host', base / 'scripts/host',
                        ignore=shutil.ignore_patterns('__pycache__'))
        (base / 'tests').mkdir()
        shutil.copy2(ROOT / 'tests/test_herdr_start.py', base / 'tests/test_herdr_start.py')
        result = run(base)
        report = result.stdout + result.stderr
        if (result.returncode or '\nOK\n' not in report or 'Ran 1 test in ' not in report
                or 'skipped=' in report):
            raise SystemExit('Herdr detach baseline failed; no mutation accepted.')
        source = base / 'scripts/host/herdr.py'
        original = source.read_text()
        if original.count(ANCHOR) != 1:
            raise SystemExit('Herdr detach mutation anchor changed.')
        for name, replacement in MUTATIONS.items():
            source.write_text(original.replace(ANCHOR, replacement))
            try:
                result = run(base)
                report = result.stdout + result.stderr
                failure = f'FAIL: {CASE} (test_herdr_start.HerdrStartTests.{CASE})'
                if (not result.returncode or failure not in report
                        or 'AssertionError: 1 != 0 :' not in report
                        or '\nFAILED (failures=1)\n' not in report
                        or 'Ran 1 test in ' not in report
                        or '\nERROR:' in report or 'skipped=' in report):
                    raise SystemExit('Herdr detach mutation not rejected by startup assertion: ' + name)
                print('Rejected ' + name)
            finally:
                source.write_text(original)
    print('Both Herdr detach mutations rejected; disposable sources removed.')


if __name__ == '__main__':
    main()
