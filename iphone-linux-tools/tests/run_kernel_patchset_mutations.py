"""Prove patchset guards with real Git worktrees and assertion failures."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = ROOT / 'scripts/build/kernel_patchset.py'
MUTATIONS = (
    ('patch-hash', 'digest(raw) != PATCH_SHA', 'False'),
    ('base-commit', "git(root, 'rev-parse', 'HEAD').decode().strip() != BASE", 'False'),
    ('preserved-checkout', "plain_file(root / '.git')", 'pass'),
    ('extra-changes', '[entry for entry in entries if entry] != required', 'False'),
    ('hidden-index', "raise ValueError('Hidden tracked-file index flags refused.')", 'pass'),
    ('false-physical-proof', "'physical_boot_tested': False", "'physical_boot_tested': True"),
    ('checkout-alias', 'root = Path(checkout).absolute()',
     'root = Path(checkout).resolve(strict=True)'),
)


def main():
    source = SUBJECT.read_text()
    root_anchor = 'ROOT = Path(__file__).resolve().parents[2]'
    if source.count(root_anchor) != 1:
        raise ValueError('Subject root anchor differs.')
    # Only fixture/patch lookup changes; mutants execute in temporary Git repos.
    source = source.replace(root_anchor, 'ROOT = Path(' + repr(str(ROOT)) + ')', 1)
    with tempfile.TemporaryDirectory(prefix='kernel-patchset-mutations-') as directory:
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            body = source if before is None else source.replace(before, after, 1)
            compile(body, name, 'exec')
            subject = Path(directory) / (name + '.py')
            subject.write_text(body)
            environment = dict(os.environ, KERNEL_PATCHSET_SCRIPT=str(subject),
                               PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run(
                [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                 '-p', 'test_kernel_patchset.py', '-v'], capture_output=True, text=True,
                timeout=30, env=environment)
            if before is None:
                if result.returncode:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif (not result.returncode or 'FAIL:' not in result.stderr or
                  'AssertionError' not in result.stderr or 'ERROR:' in result.stderr):
                raise RuntimeError('No assertion kill: ' + name + result.stderr)
            else:
                print('KERNEL_PATCHSET_ASSERTION_KILL ' + name, flush=True)
    print('KERNEL_PATCHSET_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
