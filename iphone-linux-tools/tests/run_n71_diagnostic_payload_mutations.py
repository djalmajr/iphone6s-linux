"""Check diagnostic ABI/payload guards in public-only disposable source copies."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = 'scripts/build/compose-n71-diagnostic.py'
DEPENDENCIES = (
    SUBJECT, 'scripts/build/integrate-source-kernel.py', 'scripts/build/kernel_patchset.py',
    'scripts/build/kernel_bundle.py', 'scripts/build/prepare-n71-pcie-diagnostic.py',
    'scripts/build/prepare-n71-topology.py', 'scripts/research/n71_runtime_tunables.py',
    'scripts/host/device_profile.py', 'scripts/host/profile_image.py',
)
MUTATIONS = (
    ('known-abi', "if kernel_release not in ('7.2.0-iphone6s-source', '7.2.0' + KERNEL.kernel_bundle.LOCALVERSION):", 'if False:'),
    ('cross-abi', 'raw.count(vermagic) != 1', 'False'),
    ('elf-machine', "struct.unpack_from('<HH', raw, 16) != (1, 183)", 'False'),
    ('payload-binding', 'if original != expected:', 'if False:'),
    ('dt-mask', 'value & ~mask', 'False'),
)


def run(subject=None):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    environment.pop('N71_DIAGNOSTIC_COMPOSER_SCRIPT', None)
    if subject is not None:
        environment['N71_DIAGNOSTIC_COMPOSER_SCRIPT'] = str(subject)
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                           '-p', 'test_n71_diagnostic_payload.py', '-v'], env=environment,
                          capture_output=True, text=True, timeout=30)


def main():
    baseline = run()
    if baseline.returncode:
        print(baseline.stderr, file=sys.stderr)
        return 1
    text = (ROOT / SUBJECT).read_text()
    with tempfile.TemporaryDirectory(prefix='n71-diagnostic-public-mutations-') as folder:
        copied = Path(folder) / 'source'
        for name in DEPENDENCIES:
            target = copied / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        target = copied / SUBJECT
        for name, before, after in MUTATIONS:
            if text.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            target.write_text(text.replace(before, after, 1))
            compile(target.read_text(), str(target), 'exec')
            result = run(target)
            if (not result.returncode or 'FAIL:' not in result.stderr
                    or 'AssertionError' not in result.stderr or 'ERROR:' in result.stderr):
                print('SURVIVED_OR_INFRA_ERROR ' + name, file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                return 1
            print('KILLED ' + name)
    print(f'N71_DIAGNOSTIC_PAYLOAD_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
