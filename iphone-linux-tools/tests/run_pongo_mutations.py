"""Falsify Pongo format guards in synthetic files, never firmware or devices."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/build/verify-pongo-build.py'
MUTATIONS = [
    ('cpu', 'cpu != 0x100000c', 'False'),
    ('file-type', 'kind != 5', 'False'),
    ('raw-comparison', 'mapping(macho) != raw', 'False'),
    ('version-markers', "b'bootm\\0' not in raw or b'2.6.3-bb492b00' not in raw", 'False'),
    ('input-type', 'not stat.S_ISREG(info.st_mode)', 'False'),
    ('mapped-padding', 'spans.append((first, last, file_offset + first - address))',
     'spans.append((first, mapped[0][1], file_offset + first - address))'),
]


def run(source=None):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    environment.pop('PONGO_VERIFY_SCRIPT', None)
    if source is not None:
        environment['PONGO_VERIFY_SCRIPT'] = str(source)
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                           '-p', 'test_pongo_verifier.py', '-v'], env=environment,
                          capture_output=True, text=True, timeout=30)


def main():
    baseline = run()
    if baseline.returncode:
        print(baseline.stderr, file=sys.stderr)
        return 1
    text = SOURCE.read_text()
    with tempfile.TemporaryDirectory(prefix='pongo-verifier-mutations-') as work:
        for name, before, after in MUTATIONS:
            if text.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            selected = Path(work) / (name + '.py')
            selected.write_text(text.replace(before, after, 1))
            result = run(selected)
            if not result.returncode or 'FAIL:' not in result.stderr:
                print('SURVIVED_OR_INFRA_ERROR ' + name, file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                return 1
            print('KILLED ' + name)
    print(f'PONGO_VERIFIER_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
