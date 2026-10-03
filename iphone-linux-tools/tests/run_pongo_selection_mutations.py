"""Falsify Pongo selection with synthetic processes in disposable source trees."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = 'scripts/boot/pongo_select.py'
MONITOR = 'scripts/boot/dfu_boot.py'
WRAPPER = 'scripts/host/iphone-linux.sh'
MUTATIONS = [
    ('hash', HELPER, 'if digest != expected:', 'if False:',
     'PongoSelectionTests.test_modified_default_and_source_are_rejected'),
    ('empty-fallback', HELPER, "selected = os.environ.get('IPHONE_LINUX_PONGO')",
     "selected = os.environ.get('IPHONE_LINUX_PONGO') or None",
     'PongoSelectionTests.test_empty_or_invalid_selection_never_falls_back'),
    ('file-boundary', HELPER,
     'if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1\n            or info.st_uid != os.geteuid() or info.st_mode & 0o7022):',
     'if False:', 'PongoSelectionTests.test_links_and_public_writes_are_rejected'),
    ('parent-link', HELPER, 'if not stat.S_ISDIR(parent.lstat().st_mode):', 'if False:',
     'PongoSelectionTests.test_size_and_parent_symlinks_are_rejected'),
    ('source-hash', HELPER, 'expected = SOURCE_SHA256 if selected is not None else DEFAULT_SHA256',
     'expected = DEFAULT_SHA256',
     'PongoSelectionTests.test_default_and_explicit_candidate_choose_distinct_pinned_files'),
    ('wrapper-preflight', WRAPPER, '    python3 "$ROOT/scripts/boot/pongo_select.py" > /dev/null',
     '    :', 'PongoBootBoundaryTests.test_invalid_candidate_blocks_wrapper_and_direct_monitor_before_usb'),
    ('monitor-selection', MONITOR, 'pongo = select(ROOT)', "pongo = ROOT / 'artifacts/Pongo.bin'",
     'PongoBootBoundaryTests.test_monitor_passes_exact_candidate_path_and_cleans_child'),
    ('monitor-argument', MONITOR, '"-lp", "-k", str(pongo)',
     '"-lp", "-k", str(ROOT / "artifacts/Pongo.bin")',
     'PongoBootBoundaryTests.test_monitor_passes_exact_candidate_path_and_cleans_child'),
    ('wrapper-active-linux', WRAPPER, 'if [ "${IPHONE_LINUX_PONGO+x}" = x ]; then',
     'if false; then', 'PongoBootBoundaryTests.test_existing_pongo_or_linux_refuses_candidate_transfer'),
    ('wrapper-active-pongo', WRAPPER,
     'if [ "${IPHONE_LINUX_PONGO+x}" = x ] && ioreg -p IOUSB -w0',
     'if false && ioreg -p IOUSB -w0',
     'PongoBootBoundaryTests.test_existing_pongo_or_linux_refuses_candidate_transfer'),
    ('monitor-active-device', MONITOR,
     "if 'PongoOS USB Device' in usb.stdout or 'iPhone 6s Linux probe' in usb.stdout:",
     'if False:', 'PongoBootBoundaryTests.test_existing_pongo_or_linux_refuses_candidate_transfer'),
]


def main():
    with tempfile.TemporaryDirectory(prefix='pongo-selection-mutations-') as folder:
        project = Path(folder).resolve()
        for name in (HELPER, MONITOR, WRAPPER, 'scripts/boot/dfu_state.py', 'scripts/boot/boot_tools.py',
                     'tests/test_pongo_selection.py'):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PONGO_SELECTION_ROOT=str(project))
        environment.pop('IPHONE_LINUX_PROFILE', None)
        environment.pop('IPHONE_LINUX_PONGO', None)
        command = [sys.executable, '-m', 'unittest']
        def run(test):
            return subprocess.run(command + [test], cwd=project / 'tests', env=environment,
                                  capture_output=True, text=True, timeout=30)
        baseline = run('test_pongo_selection')
        if baseline.returncode:
            raise RuntimeError('Pongo selection baseline failed:\n' + baseline.stderr)
        for name, filename, before, after, test in MUTATIONS:
            path = project / filename
            text = path.read_text()
            if text.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            try:
                path.write_text(text.replace(before, after, 1))
                result = run('test_pongo_selection.' + test)
                if not result.returncode or 'FAIL:' not in result.stderr:
                    raise RuntimeError('SURVIVED_OR_INFRA_ERROR ' + name + '\n' + result.stderr)
                print('KILLED ' + name, flush=True)
            finally:
                path.write_text(text)
    print(f'PONGO_SELECTION_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')


if __name__ == '__main__':
    main()
