"""Falsify reboot gates in a disposable copy without contacting a device."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ('skip-backup', "    if code or expired or not match:\n", "    if False:\n",
     'test_backup_exit_failure_even_with_valid_archive_blocks_reboot'),
    ('skip-published-snapshot-verification', '        persist.load_snapshot(match.group(1))',
     '        pass', 'test_snapshot_tampered_after_publication_blocks_reboot'),
    ('skip-sync-confirmation', 'if SYNC_MARKER not in output.splitlines() or (not expired and code not in (0, 255)):',
     'if not expired and code not in (0, 255):', 'test_missing_sync_confirmation_never_reports_success'),
    ('accept-wrong-ios-model', "model.strip() == 'iPhone8,1'", 'True',
     'test_wrong_ios_model_never_reports_success'),
    ('accept-multiple-usb-devices', 'if len(devices) == 1:', 'if devices:',
     'test_multiple_usb_devices_never_report_success'),
    ('skip-final-linux-check', 'and not linux_present(budget())):', 'and True):',
     'test_linux_reappears_after_model_query_never_reports_success'),
    ('normal-reboot', '/bin/busybox reboot -f', '/bin/busybox reboot',
     'test_success_requires_real_verified_snapshot_and_usb_observation'),
    ('drop-profile-alias', "ssh = device_profile.ssh_options(ROOT) + [f'root@{device_profile.PHONE}']",
     "ssh = ['ssh', '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes', f'root@{device_profile.PHONE}']",
     'test_selected_profile_is_used_by_backup_and_reboot'),
    ('cancel-only-parent', '    except BaseException:\n        autosnap.stop_job(process)',
     '    except BaseException:\n        process.kill()',
     'test_cancellation_stops_owned_backup_ssh_without_reboot'),
]


def main():
    with tempfile.TemporaryDirectory(prefix='return-ios-mutations-') as temporary:
        project = Path(temporary) / 'project'
        shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(
            'keys', 'runtime', 'backups', 'logs', 'bin', 'artifacts', '__pycache__', '.git'))
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        environment.pop('IPHONE_LINUX_PROFILE', None)
        command = [sys.executable, '-m', 'unittest']
        baseline = subprocess.run(command + ['discover', '-s', 'tests', '-p', 'test_return_ios.py'],
                                  cwd=project, env=environment, capture_output=True, text=True, timeout=180)
        if baseline.returncode:
            raise RuntimeError('Reboot baseline failed:\n' + baseline.stdout + baseline.stderr)
        print('BASELINE_RETURN_IOS_OK', flush=True)
        source = project / 'scripts/host/return_ios.py'
        original = source.read_text()
        for name, old, new, test in MUTATIONS:
            if original.count(old) != 1:
                raise RuntimeError('Mutation target is not unique: ' + name)
            try:
                source.write_text(original.replace(old, new, 1))
                result = subprocess.run(command + ['test_return_ios.ReturnIOSTests.' + test],
                                        cwd=project / 'tests', env=environment, capture_output=True,
                                        text=True, timeout=90)
                if result.returncode == 0 or 'FAIL:' not in result.stderr:
                    raise RuntimeError('Mutation survived or did not reach an assertion: ' + name
                                       + '\n' + result.stdout + result.stderr)
                print('KILLED', name, flush=True)
            finally:
                source.write_text(original)
        print(f'RETURN_IOS_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}', flush=True)


if __name__ == '__main__':
    main()
