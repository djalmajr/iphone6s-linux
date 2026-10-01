#!/usr/bin/env python3
"""Exercise destructive-path regressions only in disposable synthetic projects."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if sys.platform not in ('darwin', 'linux'):
    raise SystemExit('Requires macOS or Linux with the POSIX snapshot tools.')

ROOT = Path(__file__).resolve().parents[1]
HOST_FILES = ('autosnap.py', 'persist.py', 'device_profile.py', 'restore_journal.py', 'snapshot_lock.py', 'snapshot_retention.py', 'iphone-linux.sh')
RETENTION_TEST = 'test_snapshot_retention.SnapshotRetentionTests.'
SCHEDULER_TEST = 'test_autosnap.AutoSnapshotTests.'
MUTATIONS = (
    ('pending-references', 'snapshot_retention.py', 'protected = _pending_references(store)', 'protected = set()', RETENTION_TEST + 'test_prune_keeps_latest_pending_manual_invalid_and_extra'),
    ('invalid-journal', 'snapshot_retention.py', 'protected = _pending_references(store)', 'protected = set()', RETENTION_TEST + 'test_invalid_journal_blocks_retention'),
    ('latest-snapshot', 'snapshot_retention.py', 'protected.add(latest)', 'pass', RETENTION_TEST + 'test_latest_survives_clock_regression'),
    ('microseconds', 'snapshot_retention.py', "created_at = manifest.get('created_at')", 'created_at = None', RETENTION_TEST + 'test_created_at_microseconds_order_same_second'),
    ('historical-date', 'snapshot_retention.py', 'snapshot_id[:15]', 'snapshot_id[:16]', RETENTION_TEST + 'test_historical_ids_are_fallback_order'),
    ('candidate-integrity', 'snapshot_retention.py', '            validate(snapshot_id)', '            pass', RETENTION_TEST + 'test_prune_keeps_latest_pending_manual_invalid_and_extra'),
    ('flock', 'snapshot_lock.py', 'fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)', 'pass', RETENTION_TEST + 'test_lock_is_nonblocking_and_releases_without_deleting_inode'),
    ('hardlink-lock', 'snapshot_lock.py', 'info.st_nlink != 1', 'False', RETENTION_TEST + 'test_lock_rejects_symlink_and_hardlink'),
    ('nonregular-lock', 'snapshot_lock.py', 'not valid_type', 'False', RETENTION_TEST + 'test_lock_rejects_fifo_without_blocking'),
    ('keep-limit', 'autosnap.py', "'automatic', '--keep', str(options.keep)", "'automatic', '--keep', '12'", SCHEDULER_TEST + 'test_recurrence_publishes_valid_private_snapshot_and_retains_latest'),
    ('failed-transfer-state', 'autosnap.py', "outcome = 'failed'", "outcome = 'success'", SCHEDULER_TEST + 'test_offline_and_truncated_transfer_preserve_all_previous_snapshots'),
    ('timeout-state', 'autosnap.py', "outcome = 'timeout'", "outcome = 'failed'", SCHEDULER_TEST + 'test_timeout_preserves_backup_and_next_attempt_can_run'),
    ('signal-forwarding', 'autosnap.py', 'signal.signal(signal.SIGTERM, cancelled)', 'pass', SCHEDULER_TEST + 'test_sigterm_cancels_owned_job_without_publishing'),
    ('finite-watch-exit', 'autosnap.py', '            return result', '            return 0', SCHEDULER_TEST + 'test_finite_watch_reports_failed_job'),
    ('active-restore-guard', 'iphone-linux.sh', "            printf 'Restauração automática exige um novo boot; Linux já está ativo.\\n' >&2\n            return 1", '            :', SCHEDULER_TEST + 'test_auto_restore_refuses_active_linux_and_invalid_snapshot_before_boot'),
)

selection = sys.argv[1:]
if any(label not in {mutation[0] for mutation in MUTATIONS} for label in selection):
    raise SystemExit('Unknown mutation selection.')
selected = [mutation for mutation in MUTATIONS if not selection or mutation[0] in selection]
for label, filename, original, changed, test in selected:
    with tempfile.TemporaryDirectory(prefix='iphone-autosnap-mutation-') as temporary:
        project = Path(temporary)
        host = project / 'scripts/host'
        host.mkdir(parents=True)
        for name in HOST_FILES:
            shutil.copy(ROOT / 'scripts/host' / name, host / name)
        boot = project / 'scripts/boot'
        boot.mkdir(parents=True)
        shutil.copy(ROOT / 'scripts/boot/pongo_select.py', boot / 'pongo_select.py')
        tests = project / 'tests'
        tests.mkdir()
        for name in ('test_autosnap.py', 'test_snapshot_retention.py'):
            shutil.copy(ROOT / 'tests' / name, tests / name)
        path = host / filename
        content = path.read_text()
        if content.count(original) != 1:
            raise SystemExit('Mutation anchor changed: ' + label)
        path.write_text(content.replace(original, changed))
        result = subprocess.run([sys.executable, '-m', 'unittest', test, '-v'],
                                cwd=tests, capture_output=True, text=True, timeout=20)
        output = result.stdout + result.stderr
        if result.returncode == 0 or ('FAILED (failures=' not in output):
            raise SystemExit('Mutation survived or gate failed unexpectedly: ' + label + '\n' + output)
        print(label + ': rejected', flush=True)
print(str(len(selected)) + ' mutations rejected; synthetic copies removed.')
