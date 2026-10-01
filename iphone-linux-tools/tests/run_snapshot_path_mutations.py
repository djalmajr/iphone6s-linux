"""Falsify local snapshot path guards using only synthetic disposable trees."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ('owner', 'snapshot_lock.py', 'info.st_uid != os.geteuid()', 'False',
     'test_foreign_owned_regular_file_is_rejected_by_shared_boundary'),
    ('inode-type', 'snapshot_lock.py', 'not valid_type', 'False',
     'test_snapshot_archive_and_manifest_links_are_rejected'),
    ('hardlink', 'snapshot_lock.py', '(not directory and info.st_nlink != 1)', 'False',
     'test_snapshot_archive_and_manifest_links_are_rejected'),
    ('journal-write-directory', 'restore_journal.py',
     '    snapshot_lock.check_local_path(directory, directory=True)\n    directory.chmod(0o700)',
     '    directory.chmod(0o700)', 'test_journal_directory_link_never_writes_or_chmods_external_directory'),
    ('journal-read-directory', 'restore_journal.py',
     '    try:\n        snapshot_lock.check_local_path(directory, directory=True)\n    except FileNotFoundError:\n        return []',
     '    if not directory.exists():\n        return []', 'test_dangling_journal_link_is_not_an_empty_journal'),
    ('journal-record', 'restore_journal.py', '        snapshot_lock.check_local_path(path)\n', '',
     'test_journal_record_links_are_rejected_before_read'),
    ('snapshot-directory', 'persist.py',
     "    snapshot_lock.check_local_path(directory, directory=True)\n    manifest =",
     '    manifest =', 'test_snapshot_directory_link_is_rejected_for_explicit_and_default_selection'),
    ('snapshot-manifest', 'persist.py',
     "manifest = snapshot_lock.check_local_path(directory / 'manifest.json')",
     "manifest = directory / 'manifest.json'", 'test_snapshot_archive_and_manifest_links_are_rejected'),
    ('snapshot-archive', 'persist.py',
     "archive = snapshot_lock.check_local_path(directory / 'files.tar.gz')",
     "archive = directory / 'files.tar.gz'", 'test_snapshot_archive_and_manifest_links_are_rejected'),
    ('snapshot-list-directory', 'persist.py',
     '    for directory in directories:\n        snapshot_lock.check_local_path(directory, directory=True)',
     '    for directory in directories:\n        pass',
     'test_snapshot_directory_link_is_rejected_for_explicit_and_default_selection'),
    ('store-scope', 'snapshot_lock.py', '    check_local_path(store, directory=True)\n', '',
     'test_store_link_is_rejected_by_lock_and_journal_before_external_changes'),
]


def main():
    with tempfile.TemporaryDirectory(prefix='snapshot-path-mutations-') as work:
        project = Path(work).resolve()
        shutil.copytree(ROOT / 'scripts/host', project / 'scripts/host',
                        ignore=shutil.ignore_patterns('__pycache__'))
        tests = project / 'tests'
        tests.mkdir()
        shutil.copyfile(ROOT / 'tests/test_local_snapshot_paths.py', tests / 'test_local_snapshot_paths.py')
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        command = [sys.executable, '-m', 'unittest']
        def run(test):
            return subprocess.run(command + [test], cwd=tests, env=environment,
                                  capture_output=True, text=True, timeout=15)
        baseline = run('test_local_snapshot_paths')
        if baseline.returncode:
            raise RuntimeError('Local path baseline failed:\n' + baseline.stderr)
        for name, filename, before, after, test in MUTATIONS:
            path = project / 'scripts/host' / filename
            text = path.read_text()
            if text.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            try:
                path.write_text(text.replace(before, after, 1))
                result = run('test_local_snapshot_paths.LocalSnapshotPathTests.' + test)
                if not result.returncode or 'FAIL:' not in result.stderr:
                    raise RuntimeError('SURVIVED_OR_INFRA_ERROR ' + name + '\n' + result.stderr)
                print('KILLED ' + name, flush=True)
            finally:
                path.write_text(text)
    print(f'LOCAL_SNAPSHOT_PATH_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')


if __name__ == '__main__':
    main()
