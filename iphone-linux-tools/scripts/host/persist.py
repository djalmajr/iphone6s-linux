#!/usr/bin/env python3
"""Private, scoped file snapshots for the RAM-only phone server."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import tarfile
import tempfile
import uuid
import restore_journal
import snapshot_lock
import snapshot_retention

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / 'backups'
EXCLUDED = ('root/.ssh', 'root/.cache', 'root/.bash_history',
            'root/.config/herdr/sessions', 'root/.local/state')
MAX_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 50000
SSH = ['ssh', '-F', '/dev/null', '-i', str(ROOT / 'keys/iphone_ed25519'),
       '-o', f'UserKnownHostsFile={ROOT / "keys/known_hosts"}',
       '-o', 'StrictHostKeyChecking=yes', '-o', 'IdentitiesOnly=yes',
       '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
       '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=3',
       'root@172.16.42.1']


def excluded(name):
    return any(name == prefix or name.startswith(prefix + '/') for prefix in EXCLUDED)


def check_member(member):
    name = member.name.rstrip('/')
    path = PurePosixPath(name)
    allowed = name == 'root' or name.startswith('root/') or name == 'srv/data' or name.startswith('srv/data/')
    if (not allowed or path.is_absolute() or '..' in path.parts
            or path.as_posix() != name or any(ord(c) < 32 for c in name)
            or excluded(name)):
        raise ValueError('Caminho fora do escopo permitido no snapshot.')
    if not (member.isfile() or member.isdir()):
        raise ValueError('Snapshot contém link ou arquivo especial.')
    if member.mode & 0o7000:
        raise ValueError('Permissões especiais não são permitidas no snapshot.')
    return name


def validate_archive(path):
    members = []
    seen = set()
    size = 0
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            name = check_member(member)
            if name in seen:
                raise ValueError('Snapshot contém caminho duplicado.')
            seen.add(name)
            members.append((name, member.isdir()))
            size += member.size
            if size > MAX_BYTES or len(members) > MAX_MEMBERS:
                raise ValueError('Snapshot excede o limite de tamanho ou arquivos.')
    if not members:
        raise ValueError('Snapshot vazio.')
    types = dict(members)
    for name, _ in members:
        for parent in PurePosixPath(name).parents:
            if str(parent) in types and not types[str(parent)]:
                raise ValueError('Arquivo usado como diretório no snapshot.')
    return members


def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def remote(command, **kwargs):
    return subprocess.run(SSH + [command], check=True, **kwargs)


def _backup_locked(kind='manual'):
    STORE.mkdir(mode=0o700, exist_ok=True)
    STORE.chmod(0o700)
    snapshot_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    with tempfile.TemporaryDirectory(prefix='.partial-', dir=STORE) as work:
        work = Path(work)
        archive_path = work / 'files.tar.gz'
        process = subprocess.Popen(SSH + ['mkdir -p /srv/data; cd /; tar -czf - root srv/data'], stdout=subprocess.PIPE)
        skipped = 0
        total_bytes = 0
        total_members = 0
        try:
            with tarfile.open(fileobj=process.stdout, mode='r|gz') as source, tarfile.open(archive_path, 'w:gz') as target:
                for member in source:
                    if excluded(member.name.rstrip('/')) or not (member.isfile() or member.isdir()):
                        skipped += 1
                        continue
                    total_bytes += member.size
                    total_members += 1
                    if total_bytes > MAX_BYTES or total_members > MAX_MEMBERS:
                        raise ValueError('Snapshot excede o limite de tamanho ou arquivos.')
                    member.mode &= 0o777
                    check_member(member)
                    member.uid = member.gid = 0
                    member.uname = member.gname = 'root'
                    target.addfile(member, source.extractfile(member) if member.isfile() else None)
            if process.wait() != 0:
                raise ValueError('Transferência SSH do snapshot falhou.')
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                process.wait()
        members = validate_archive(archive_path)
        archive_path.chmod(0o600)
        manifest = {'format': 1, 'id': snapshot_id, 'kind': kind,
                    'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
                    'sha256': digest(archive_path), 'entries': len(members),
                    'skipped_entries': skipped, 'scope': ['root', 'srv/data'],
                    'excluded': list(EXCLUDED)}
        manifest_path = work / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        manifest_path.chmod(0o600)
        work.rename(STORE / snapshot_id)
    return snapshot_id


def backup(kind='manual'):
    with snapshot_lock.lock(STORE):
        snapshot_id = _backup_locked(kind)
    print('Snapshot:', snapshot_id, flush=True)
    return snapshot_id


def automatic(keep):
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 1:
        raise ValueError('A retenção exige keep >= 1.')
    with snapshot_lock.lock(STORE):
        snapshot_id = _backup_locked('automatic')
        removed = snapshot_retention.prune(STORE, {'keep': keep, 'latest': snapshot_id}, load_snapshot)
    print('Snapshot:', snapshot_id, flush=True)
    if removed:
        print('Snapshots removidos:', ' '.join(removed), flush=True)
    return snapshot_id


def snapshots():
    if not STORE.exists():
        return []
    return sorted(p for p in STORE.iterdir() if p.is_dir() and re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{8}', p.name))


def load_snapshot(snapshot_id):
    if snapshot_id is None:
        candidates = [p for p in snapshots() if json.loads((p / 'manifest.json').read_text()).get('kind') == 'manual']
        if not candidates:
            raise ValueError('Nenhum snapshot manual encontrado.')
        snapshot_id = candidates[-1].name
    if not re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{8}', snapshot_id):
        raise ValueError('Identificador inválido de snapshot.')
    directory = STORE / snapshot_id
    manifest = json.loads((directory / 'manifest.json').read_text())
    archive = directory / 'files.tar.gz'
    if manifest.get('format') != 1 or manifest.get('id') != snapshot_id or digest(archive) != manifest.get('sha256'):
        raise ValueError('Integridade do snapshot inválida; restauração bloqueada.')
    members = validate_archive(archive)
    if len(members) != manifest.get('entries'):
        raise ValueError('Manifesto não corresponde ao snapshot.')
    return archive, members


def target_checks(members):
    checks = ['set -e']
    parents = set()
    directories = set()
    for name, _ in members:
        ancestors = {str(p) for p in PurePosixPath('/' + name).parents if str(p) != '/'}
        parents.update(ancestors)
        directories.update(ancestors)
        parents.add('/' + name)
    for path in sorted(parents):
        quoted = shlex.quote(path)
        checks.append(f'if [ -L {quoted} ]; then echo "Destino contém symlink; restauração bloqueada." >&2; exit 1; fi')
    for directory in sorted(directories):
        path = shlex.quote(directory)
        checks.append(f'if [ -e {path} ] && [ ! -d {path} ]; then echo "Diretório pai incompatível." >&2; exit 1; fi')
    for name, directory in members:
        path = shlex.quote('/' + name)
        test = '-d' if directory else '-f'
        checks.append(f'if [ -e {path} ] && [ ! {test} {path} ]; then echo "Tipo incompatível no destino." >&2; exit 1; fi')
        if not directory:
            checks.append(f'if [ -f {path} ] && [ "$(stat -c %h {path})" -gt 1 ]; then echo "Destino contém hardlink; restauração bloqueada." >&2; exit 1; fi')
    return '\n'.join(checks) + '\n'


def _restore_locked(snapshot_id):
    archive, members = load_snapshot(snapshot_id)
    restore_journal.records(STORE)
    checks = target_checks(members)
    remote('/bin/bash -se', input=checks.encode())
    before = _backup_locked('pre-restore')
    source = archive.parent.name
    record = restore_journal.prepare(STORE, source, before)
    print('Snapshot para recuperação:', before, flush=True)
    print(restore_journal.recovery_command(before), flush=True)
    temporary = '/run/iphone-restore-' + uuid.uuid4().hex + '.tar.gz'
    quoted = shlex.quote(temporary)
    try:
        with archive.open('rb') as file:
            remote(f'umask 077; set -C; cat > {quoted}', stdin=file)
        script = checks + f'echo "{digest(archive)}  {temporary}" | sha256sum -c -\ntar -xzf {quoted} -C /\n'
        restore_journal.transition(STORE, record, 'applying')
        remote('/bin/bash -se', input=script.encode())
    except BaseException:
        try:
            restore_journal.transition(STORE, record, 'recovery-needed')
        except OSError as error:
            print('Falha ao atualizar journal:', error, flush=True)
        print('Restauração incompleta. Para recuperar arquivos anteriores:', flush=True)
        print(restore_journal.recovery_command(before), flush=True)
        raise
    finally:
        try:
            remote(f'rm -f {quoted}')
        except (OSError, subprocess.SubprocessError) as error:
            print('Aviso: limpeza do arquivo temporário falhou:', error, flush=True)
    try:
        restore_journal.transition(STORE, record, 'succeeded')
        restore_journal.recovered(STORE, source)
    except (OSError, ValueError) as error:
        raise ValueError('Arquivos aplicados, mas atualização do journal falhou: ' + str(error)) from error
    print('Restauração concluída. Snapshot anterior:', before)


def restore(snapshot_id):
    with snapshot_lock.lock(STORE):
        return _restore_locked(snapshot_id)


def verify(snapshot_id):
    with snapshot_lock.lock(STORE):
        _, members = load_snapshot(snapshot_id)
    print(snapshot_id, len(members), 'entradas', flush=True)


def show_backups():
    with snapshot_lock.lock(STORE):
        for directory in snapshots():
            manifest = json.loads((directory / 'manifest.json').read_text())
            print(directory.name, manifest['kind'], manifest['entries'], 'entradas')
        restore_journal.show_pending(STORE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['backup', 'automatic', 'restore', 'backups', 'verify'])
    parser.add_argument('snapshot', nargs='?')
    parser.add_argument('--keep', type=int)
    args = parser.parse_args()
    os.umask(0o077)
    if args.command == 'automatic' and (args.snapshot or args.keep is None or args.keep < 1):
        parser.error('automatic exige --keep N com N >= 1 e não aceita snapshot.')
    if args.command == 'verify' and (not args.snapshot or args.keep is not None):
        parser.error('verify exige um identificador e não aceita --keep.')
    if args.command in ('backup', 'backups', 'restore') and args.keep is not None:
        parser.error('--keep só é usado com automatic.')
    if args.snapshot and args.command not in ('restore', 'verify'):
        parser.error('O identificador só é usado com restore.')
    if args.command == 'backup':
        backup()
    elif args.command == 'automatic':
        automatic(args.keep)
    elif args.command == 'restore':
        restore(args.snapshot)
    elif args.command == 'verify':
        verify(args.snapshot)
    else:
        show_backups()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, tarfile.TarError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
