"""Falsify composer output guards using only disposable synthetic inputs."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'scripts/build/compose-payload.py'
MUTATIONS = [
    ('output-link', 'regular_output(path.lstat())', 'regular_output(path.stat())',
     'test_existing_and_dangling_links_preserve_external_target'),
    ('parent-link', 'stat.S_ISDIR(parent.lstat().st_mode)', 'stat.S_ISDIR(parent.stat().st_mode)',
     'test_linked_parent_does_not_publish_outside_chosen_tree'),
    ('hardlink', 'info.st_nlink != 1', 'False', 'test_hardlink_and_special_mode_are_refused'),
    ('special-mode', 'info.st_mode & 0o7000', 'False', 'test_hardlink_and_special_mode_are_refused'),
    ('special-type', 'not stat.S_ISREG(info.st_mode)', 'False',
     'test_fifo_is_refused_before_open_without_blocking'),
    ('parent-owner', 'directory.st_uid != os.geteuid()', 'False', 'test_unowned_or_writable_parent_is_refused'),
    ('parent-mode', 'directory.st_mode & 0o7022', 'False', 'test_unowned_or_writable_parent_is_refused'),
    ('different-content', 'if existing.read() != blob:', 'if False:',
     'test_different_existing_output_remains_unchanged'),
    ('identical-rewrite', '        return\n    temporary = None', '        pass\n    temporary = None',
     'test_identical_recompose_keeps_inode_and_mtime'),
    ('private-publication', 'os.replace(temporary, path)', 'path.write_bytes(blob)\n        os.chmod(path, 0o644)',
     'test_cli_publishes_exact_private_payload'),
    ('cleanup', 'temporary.unlink(missing_ok=True)', 'pass', 'test_failed_rename_removes_only_its_temporary'),
    ('dotdot', "if '..' in path.parts:", 'if False:', 'test_dotdot_destination_is_refused_before_reading_inputs'),
]


def main():
    with tempfile.TemporaryDirectory(prefix='compose-mutations-') as folder:
        project = Path(folder).resolve()
        for name in (SOURCE, 'tests/test_compose_payload.py'):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        def run(test):
            return subprocess.run([sys.executable, '-m', 'unittest', test], cwd=project / 'tests',
                                  env=environment, capture_output=True, text=True, timeout=15)
        baseline = run('test_compose_payload')
        if baseline.returncode:
            raise RuntimeError('Composer baseline failed:\n' + baseline.stderr)
        path = project / SOURCE
        original = path.read_text()
        for name, before, after, method in MUTATIONS:
            if original.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            try:
                path.write_text(original.replace(before, after, 1))
                result = run('test_compose_payload.ComposePayloadTests.' + method)
                if not result.returncode or 'FAIL:' not in result.stderr:
                    raise RuntimeError('SURVIVED_OR_INFRA_ERROR ' + name + '\n' + result.stderr)
                print('KILLED ' + name, flush=True)
            finally:
                path.write_text(original)
    print(f'COMPOSE_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')


if __name__ == '__main__':
    main()
