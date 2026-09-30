"""Safe retention for validated automatic snapshots."""

import datetime
import json
from pathlib import Path
import re
import stat
import sys
import tarfile

import restore_journal


SNAPSHOT_RE = re.compile(r'\d{8}T\d{6}Z-[a-f0-9]{8}\Z')
SNAPSHOT_CHILDREN = {'files.tar.gz', 'manifest.json'}


def _warning(snapshot_id, reason):
    print(f'Aviso de retenção: {snapshot_id}: {reason}.', file=sys.stderr)


def _check_options(options):
    if not isinstance(options, dict):
        raise ValueError('Opções de retenção inválidas.')
    keep = options.get('keep')
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 1:
        raise ValueError('A retenção exige keep >= 1.')
    latest = options.get('latest')
    if latest is not None and (not isinstance(latest, str) or not SNAPSHOT_RE.fullmatch(latest)):
        raise ValueError('Snapshot latest inválido.')
    return keep, latest


def _pending_references(store):
    directory = store / 'restore-journal'
    try:
        directory_info = directory.lstat()
    except FileNotFoundError:
        return set()
    if stat.S_ISLNK(directory_info.st_mode) or not stat.S_ISDIR(directory_info.st_mode):
        raise ValueError('Journal de restauração inválido.')
    for path in directory.iterdir():
        if path.suffix != '.json':
            continue
        path_info = path.lstat()
        if stat.S_ISLNK(path_info.st_mode) or not stat.S_ISREG(path_info.st_mode):
            raise ValueError('Journal de restauração inválido.')
    try:
        records = restore_journal.records(store)
    except (OSError, ValueError) as error:
        raise ValueError('Journal de restauração inválido.') from error
    return {record[field] for record in records if record['phase'] in restore_journal.PENDING
            for field in ('source', 'before')}


def _safe_snapshot_directory(path):
    """Return true only for a directory that is safe to remove as a unit."""

    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return False
    children = list(path.iterdir())
    if {child.name for child in children} != SNAPSHOT_CHILDREN or len(children) != 2:
        return False
    for child in children:
        child_info = child.lstat()
        if (stat.S_ISLNK(child_info.st_mode) or not stat.S_ISREG(child_info.st_mode)
                or child_info.st_nlink != 1):
            return False
    return True


def _timestamp(manifest, snapshot_id):
    created_at = manifest.get('created_at')
    if isinstance(created_at, str):
        try:
            value = created_at[:-1] + '+00:00' if created_at.endswith('Z') else created_at
            parsed = datetime.datetime.fromisoformat(value)
            if parsed.tzinfo is not None:
                epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
                delta = parsed.astimezone(datetime.timezone.utc) - epoch
                return delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
        except ValueError:
            pass
    try:
        parsed = datetime.datetime.strptime(snapshot_id[:15], '%Y%m%dT%H%M%S').replace(tzinfo=datetime.timezone.utc)
        epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        delta = parsed - epoch
        return delta.days * 86_400_000_000 + delta.seconds * 1_000_000
    except ValueError:
        return 0


def _remove_snapshot(path):
    if not _safe_snapshot_directory(path):
        raise ValueError('A estrutura do snapshot mudou; remoção bloqueada.')
    for name in sorted(SNAPSHOT_CHILDREN):
        (path / name).unlink()
    path.rmdir()


def prune(store, options, validate):
    """Remove only old, valid automatic snapshots and return their IDs."""

    store = Path(store)
    keep, latest = _check_options(options)
    if not callable(validate):
        raise ValueError('Validador de snapshot inválido.')
    protected = _pending_references(store)
    if latest is not None:
        validate(latest)
        protected.add(latest)

    eligible = []
    for path in sorted(store.iterdir()):
        snapshot_id = path.name
        if not SNAPSHOT_RE.fullmatch(snapshot_id):
            continue
        if not _safe_snapshot_directory(path):
            _warning(snapshot_id, 'estrutura extra, link ou tipo inválido preservado')
            continue
        try:
            manifest = json.loads((path / 'manifest.json').read_text())
            if not isinstance(manifest, dict) or manifest.get('kind') != 'automatic':
                continue
            validate(snapshot_id)
        except (OSError, ValueError, TypeError, tarfile.TarError):
            _warning(snapshot_id, 'snapshot automático inválido preservado')
            continue
        eligible.append((_timestamp(manifest, snapshot_id), snapshot_id, path))

    eligible.sort(key=lambda item: (item[0], item[1]), reverse=True)
    keep_ids = protected | {snapshot_id for _, snapshot_id, _ in eligible[:keep]}
    removed = []
    for _, snapshot_id, path in sorted(eligible, key=lambda item: (item[0], item[1])):
        if snapshot_id in keep_ids:
            continue
        try:
            _remove_snapshot(path)
        except (OSError, ValueError):
            _warning(snapshot_id, 'remoção bloqueada')
            continue
        removed.append(snapshot_id)
    return removed
