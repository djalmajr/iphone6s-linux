"""Falsify host boot executable gates in disposable synthetic projects."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = 'scripts/boot/boot_tools.py'
MONITOR = 'scripts/boot/dfu_boot.py'
WRAPPER = 'scripts/host/iphone-linux.sh'
MUTATIONS = [
    ('digest', HELPER, 'if digest != expected:', 'if False:',
     'test_same_size_modification_and_missing_tools_are_refused'),
    ('size', HELPER, 'if info.st_size != size:', 'if False:',
     'test_foreign_owner_and_inconsistent_size_pin_are_refused'),
    ('owner', HELPER, 'info.st_uid != os.geteuid()', 'False',
     'test_foreign_owner_and_inconsistent_size_pin_are_refused'),
    ('hardlink', HELPER, 'info.st_nlink != 1', 'False',
     'test_links_special_types_and_unsafe_modes_are_refused'),
    ('permissions', HELPER, 'info.st_mode & 0o7022', 'False',
     'test_links_special_types_and_unsafe_modes_are_refused'),
    ('executable', HELPER, 'not info.st_mode & stat.S_IXUSR', 'False',
     'test_links_special_types_and_unsafe_modes_are_refused'),
    ('directory-link', HELPER, 'if not stat.S_ISDIR(directory.lstat().st_mode):', 'if False:',
     'test_linked_bin_directory_is_refused'),
    ('monitor-preflight', MONITOR, "palera = verify('palera1n-macos-arm64', ROOT)",
     "palera = ROOT / 'bin/palera1n-macos-arm64'",
     'test_direct_monitor_rejects_changed_tool_before_usb_state_or_child'),
    ('wrapper-preflight', WRAPPER,
     '    python3 "$ROOT/scripts/boot/boot_tools.py" palera1n-macos-arm64 pongoterm',
     '    :', 'test_wrapper_refuses_changed_tools_before_execution_or_payload'),
]


def main():
    with tempfile.TemporaryDirectory(prefix='boot-tool-mutations-') as temporary:
        project = Path(temporary).resolve()
        for name in (HELPER, MONITOR, WRAPPER, 'scripts/boot/dfu_state.py',
                     'scripts/boot/pongo_select.py', 'tests/test_boot_tools.py'):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', BOOT_TOOLS_SOURCE_ROOT=str(project))
        for name in ('IPHONE_LINUX_PROFILE', 'IPHONE_LINUX_PONGO'):
            environment.pop(name, None)
        command = [sys.executable, '-m', 'unittest']
        def run(test):
            return subprocess.run(command + [test], cwd=project / 'tests', env=environment,
                                  capture_output=True, text=True, timeout=30)
        baseline = run('test_boot_tools')
        if baseline.returncode:
            raise RuntimeError('Boot tools baseline failed:\n' + baseline.stderr)
        for name, filename, before, after, method in MUTATIONS:
            path = project / filename
            text = path.read_text()
            if text.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            try:
                path.write_text(text.replace(before, after, 1))
                result = run('test_boot_tools.BootToolTests.' + method)
                if not result.returncode or 'FAIL:' not in result.stderr:
                    raise RuntimeError('SURVIVED_OR_INFRA_ERROR ' + name + '\n' + result.stderr)
                print('KILLED ' + name, flush=True)
            finally:
                path.write_text(text)
    print(f'BOOT_TOOL_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')


if __name__ == '__main__':
    main()
