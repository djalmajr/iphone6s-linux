"""Private recovery references for nontransactional file restores."""
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import tempfile
import uuid
import snapshot_lock

PENDING = {'prepared', 'applying', 'recovery-needed'}
PHASES = PENDING | {'succeeded', 'recovered'}
SNAPSHOT = r'\d{8}T\d{6}Z-[a-f0-9]{8}'


def write(store, record):
    snapshot_lock.check_local_path(store, directory=True)
    directory = store / 'restore-journal'
    directory.mkdir(mode=0o700, exist_ok=True)
    snapshot_lock.check_local_path(directory, directory=True)
    directory.chmod(0o700)
    record['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    descriptor, name = tempfile.mkstemp(prefix='.partial-', dir=directory)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w') as file:
            json.dump(record, file, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(directory / (record['id'] + '.json'))
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def prepare(store, source, before):
    record = {'format': 1, 'id': uuid.uuid4().hex, 'source': source,
              'before': before, 'phase': 'prepared'}
    write(store, record)
    return record


def records(store):
    snapshot_lock.check_local_path(store, directory=True)
    directory = store / 'restore-journal'
    try:
        snapshot_lock.check_local_path(directory, directory=True)
    except FileNotFoundError:
        return []
    result = []
    for path in sorted(directory.glob('*.json')):
        snapshot_lock.check_local_path(path)
        record = json.loads(path.read_text())
        if (not isinstance(record, dict) or record.get('format') != 1 or record.get('id') != path.stem
                or not re.fullmatch(r'[a-f0-9]{32}', path.stem)
                or not isinstance(record.get('phase'), str)
                or record['phase'] not in PHASES
                or not all(isinstance(record.get(key), str)
                           and re.fullmatch(SNAPSHOT, record[key])
                           for key in ('source', 'before'))):
            raise ValueError('Journal de restauração inválido; inspecione os backups locais.')
        result.append(record)
    return result


def transition(store, record, phase):
    if phase not in PHASES:
        raise ValueError('Estado inválido de restauração.')
    record['phase'] = phase
    write(store, record)


def recovered(store, source):
    for record in records(store):
        if record['phase'] in PENDING and record['before'] == source:
            transition(store, record, 'recovered')


def recovery_command(snapshot):
    launcher = Path(__file__).resolve().parents[2] / 'scripts/host/iphone-linux.sh'
    return 'bash ' + shlex.quote(str(launcher)) + ' restore ' + snapshot


def show_pending(store):
    for record in records(store):
        if record['phase'] in PENDING:
            print('Recuperação pendente:', record['id'], record['phase'])
            print(recovery_command(record['before']))
