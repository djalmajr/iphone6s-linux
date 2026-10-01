"""Falsify scheduler state guards only in disposable synthetic projects."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ('root', 'autosnap.py', '    snapshot_lock.check_local_path(ROOT, directory=True)', '    pass',
     'test_linked_root_is_refused_without_creating_external_logs'),
    ('directory', 'autosnap.py', '    try:\n        snapshot_lock.check_local_path(directory, directory=True)',
     '    try:\n        directory.stat()', 'test_logs_redirect_refused_before_read_write_or_job'),
    ('state', 'autosnap.py', '        snapshot_lock.check_local_path(path)', '        path.stat()',
     'test_state_links_refused_and_external_bytes_preserved'),
    ('hardlink', 'snapshot_lock.py', 'info.st_nlink != 1', 'False', 'test_hardlink_state_refused_before_job'),
    ('special-type', 'snapshot_lock.py', 'not valid_type', 'False', 'test_fifo_state_refused_without_open_or_job'),
    ('owner', 'snapshot_lock.py', 'info.st_uid != os.geteuid()', 'False',
     'test_incompatible_owner_and_special_modes_refused'),
    ('special-mode', 'snapshot_lock.py', 'info.st_mode & 0o7000', 'False',
     'test_incompatible_owner_and_special_modes_refused'),
    ('read-only', 'autosnap.py', '    path = status_path()\n    try:', '    path = status_path(create=True)\n    try:',
     'test_missing_status_has_no_filesystem_side_effects'),
    ('private-publication', 'autosnap.py', '        temporary.replace(path)',
     '        temporary.replace(path)\n        path.chmod(0o644)', 'test_regular_cli_state_is_private_and_readable'),
    ('cleanup', 'autosnap.py', '        temporary.unlink(missing_ok=True)', '        pass',
     'test_failed_publication_preserves_previous_state_and_cleans_temporary'),
    ('revalidation', 'autosnap.py', '        status_path()\n        temporary.replace(path)',
     '        temporary.replace(path)', 'test_changed_destination_is_refused_before_publication'),
]


def main():
    with tempfile.TemporaryDirectory(prefix='autosnap-path-mutations-') as folder:
        project = Path(folder).resolve()
        sources = {}
        for name in ('scripts/host/autosnap.py', 'scripts/host/snapshot_lock.py', 'tests/test_autosnap_paths.py'):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
            sources[name] = target.read_text()
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

        def run(test):
            return subprocess.run([sys.executable, '-m', 'unittest', test], cwd=project / 'tests',
                                  env=environment, capture_output=True, text=True, timeout=15)

        baseline = run('test_autosnap_paths')
        if baseline.returncode:
            raise RuntimeError('Baseline failed:\n' + baseline.stderr)
        for label, filename, before, after, method in MUTATIONS:
            name = 'scripts/host/' + filename
            original = sources[name]
            if original.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + label)
            path = project / name
            try:
                path.write_text(original.replace(before, after, 1))
                result = run('test_autosnap_paths.AutoSnapshotPathTests.' + method)
                if not result.returncode or 'FAIL:' not in result.stderr:
                    raise RuntimeError('SURVIVED_OR_INFRA_ERROR ' + label + '\n' + result.stderr)
                print('KILLED ' + label, flush=True)
            finally:
                path.write_text(original)
    print(f'AUTOSNAP_PATH_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')


if __name__ == '__main__':
    main()
