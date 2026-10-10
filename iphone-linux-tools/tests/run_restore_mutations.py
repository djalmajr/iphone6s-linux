#!/usr/bin/env python3
"""Reject restore regressions after a passing dedicated VM baseline."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    'missing-pre-upload-journal': {
        'file': 'restore_journal.py',
        'before': '    write(store, record)\n    return record',
        'after': '    return record',
        'case': 'test_interrupted_extraction_and_cleanup_error_allow_explicit_recovery',
        'assertion': '88 != 255',
    },
    'ignored-remote-errors': {
        'file': 'persist.py',
        'before': 'check=True, **kwargs',
        'after': 'check=False, **kwargs',
        'case': 'test_full_tmpfs_allows_explicit_recovery',
        'assertion': 'CalledProcessError not raised',
    },
}


def baseline_passed(result):
    lines = result.stderr.splitlines()
    return (result.returncode == 0 and 'OK' in lines
            and any(line.startswith('Ran 2 tests in ') for line in lines)
            and not any(line.startswith(('FAIL:', 'ERROR:')) or 'skipped' in line for line in lines))


def expected_failure(result, mutation):
    lines = result.stderr.splitlines()
    case = mutation['case']
    header = f'FAIL: {case} (test_restore_failure_vm.RestoreFailureTests.{case})'
    return (result.returncode != 0 and header in lines
            and 'AssertionError: ' + mutation['assertion'] in lines
            and 'FAILED (failures=1)' in lines
            and any(line.startswith('Ran 1 test in ') for line in lines)
            and not any(line.startswith('ERROR:') or 'skipped' in line for line in lines))


def run(project, case=None):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    environment.pop('IPHONE_LINUX_PROFILE', None)
    command = [sys.executable, '-m', 'unittest']
    if case is None:
        command += ['discover', '-s', 'tests', '-p', 'test_restore_failure_vm.py', '-v']
    else:
        command += ['test_restore_failure_vm.RestoreFailureTests.' + case, '-v']
    return subprocess.run(command, cwd=project if case is None else project / 'tests',
                          env=environment, capture_output=True, text=True)


def main():
    if not (sys.platform == 'linux' and os.geteuid() == 0
            and os.environ.get('IPHONE_RESTORE_VM_TESTS') == '1'):
        raise SystemExit('Requires explicit disposable Linux VM/root opt-in.')
    with tempfile.TemporaryDirectory(prefix='iphone-restore-mutation-') as temporary:
        project = Path(temporary) / 'project'
        shutil.copytree(ROOT / 'scripts/host', project / 'scripts/host',
                        ignore=shutil.ignore_patterns('__pycache__'))
        (project / 'tests').mkdir()
        shutil.copy(ROOT / 'tests/test_restore_failure_vm.py', project / 'tests')
        result = run(project)
        if not baseline_passed(result):
            raise SystemExit('Original restore baseline failed:\n' + result.stdout + result.stderr)
        print('Original restore baseline passed', flush=True)
        for label, mutation in MUTATIONS.items():
            path = project / 'scripts/host' / mutation['file']
            original = path.read_text()
            if original.count(mutation['before']) != 1:
                raise SystemExit('Mutation anchor changed: ' + label)
            try:
                path.write_text(original.replace(mutation['before'], mutation['after'], 1))
                result = run(project, mutation['case'])
                if not expected_failure(result, mutation):
                    raise SystemExit('Mutation survived or failed outside expected assertion: ' + label
                                     + '\n' + result.stdout + result.stderr)
                print('Rejected ' + label, flush=True)
            finally:
                path.write_text(original)
    print('Both mutations rejected; disposable copies removed.')


if __name__ == '__main__':
    main()
