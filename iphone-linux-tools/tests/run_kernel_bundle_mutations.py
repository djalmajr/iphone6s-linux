"""Require actual assertion failures for source bundle boundary mutations."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = ROOT / 'scripts/build/kernel_bundle.py'
MUTATIONS = (
    ('patch-hash', 'kernel_patchset.digest(raw) != expected', 'False'),
    ('base', "git(root, 'rev-parse', 'HEAD').decode().strip() != BASE", 'False'),
    ('baseline', "kernel_patchset.plain_file(root / '.git')", 'pass'),
    ('hidden-index', "raise ValueError('Hidden tracked-file flags refused.')", 'pass'),
    ('original-blob', "raise ValueError('Original full blob differs.')", 'pass'),
    ('external-work', 'sorted(entries) != sorted(required)', 'False'),
    ('unapplied-check', "stage == 'original' and not allow_original", 'False'),
    ('alias', 'root = Path(checkout).absolute()', 'root = Path(checkout).resolve(strict=True)'),
    ('false-boot', "'physical_boot_tested': False", "'physical_boot_tested': True"),
    ('false-image', "'kernel_image_linked': False", "'kernel_image_linked': True"),
    ('reused-identity', "LOCALVERSION = '-iphone6s-dart-serdev1'", "LOCALVERSION = '-iphone6s-source'"),
)


def main():
    source = SUBJECT.read_text()
    with tempfile.TemporaryDirectory(prefix='kernel-bundle-mutations-') as directory:
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor not unique: ' + name)
            body = source if before is None else source.replace(before, after, 1)
            compile(body, name, 'exec')
            subject = Path(directory) / (name + '.py')
            subject.write_text(body)
            environment = dict(os.environ, KERNEL_BUNDLE_SCRIPT=str(subject),
                               PYTHONDONTWRITEBYTECODE='1',
                               PYTHONPATH=str(ROOT / 'scripts/build'))
            result = subprocess.run(
                [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                 '-p', 'test_kernel_bundle.py', '-v'], capture_output=True, text=True,
                timeout=40, env=environment)
            if before is None:
                if result.returncode:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif (not result.returncode or 'FAIL:' not in result.stderr or
                  'AssertionError' not in result.stderr or 'ERROR:' in result.stderr):
                raise RuntimeError('No assertion kill: ' + name + result.stderr)
            else:
                print('KERNEL_BUNDLE_ASSERTION_KILL ' + name, flush=True)
    print('KERNEL_BUNDLE_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
