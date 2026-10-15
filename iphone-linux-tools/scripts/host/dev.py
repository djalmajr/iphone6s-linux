#!/usr/bin/env python3
"""Update the declared phone DNS service without rebooting Linux."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tarfile
import uuid
import device_profile
import dns
import persist

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / 'runtime/dev'
MAX_BYTES = 65536


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_regular(path):
    path = Path(path).absolute()
    for ancestor in reversed((path,) + tuple(path.parents)):
        if ancestor.is_symlink():
            raise ValueError('Linked source path refused.')
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_mode & 0o7022 or info.st_size > MAX_BYTES):
        raise ValueError('Source type, links, permissions or size refused.')
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError('Source exceeds the size limit.')
    return data


def validate_hosts(data):
    if len(data) > MAX_BYTES:
        raise ValueError('Hosts size refused.')
    records = {}
    for line in data.decode('ascii').splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 2:
            raise ValueError('Use one private IPv4 and one home.arpa name per line.')
        address, name = fields
        try:
            name = dns.local_name(name)
            address = dns.service_ip(address)
        except argparse.ArgumentTypeError as error:
            raise ValueError(str(error)) from error
        if name in records:
            raise ValueError('Duplicate DNS name refused.')
        records[name] = address
    if records.get('iphone-usb.home.arpa') != device_profile.PHONE:
        raise ValueError('The USB health record must remain present.')
    return records


def bundle(manager, hosts):
    validate_hosts(hosts)
    if not manager.startswith(b'#!/bin/sh\n') or len(manager) > MAX_BYTES:
        raise ValueError('DNS manager format/size refused.')
    updater = read_regular(ROOT / 'phone/dev/update-dns.sh')
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as archive:
        for name, data in (('manager', manager), ('hosts', hosts), ('update.sh', updater)):
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o600
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def ssh(command, payload=None):
    return subprocess.run(device_profile.ssh_options() +
                          ['root@' + device_profile.PHONE, command], input=payload,
                          capture_output=True, timeout=40)


def state():
    result = ssh('set -eu; cat /proc/sys/kernel/random/boot_id; '
                 'cut -d " " -f1 /proc/uptime; uname -r; '
                 'sha256sum /srv/data/dns/manage-dns.sh /srv/data/dns/hosts')
    if result.returncode:
        raise RuntimeError('Phone Linux/SSH or declared DNS files unavailable; no DFU started.')
    lines = result.stdout.decode('ascii').splitlines()
    if len(lines) != 5 or not re.fullmatch(r'[a-f0-9-]{36}', lines[0]):
        raise ValueError('Phone state format refused.')
    hashes = [line.split()[0] for line in lines[3:]]
    if not all(re.fullmatch('[a-f0-9]{64}', item) for item in hashes):
        raise ValueError('Phone file digest refused.')
    return {'boot_id': lines[0], 'uptime': float(lines[1]), 'kernel': lines[2],
            'manager_sha256': hashes[0], 'hosts_sha256': hashes[1]}


def apply(transaction, files, before):
    manager, hosts = files
    payload = bundle(manager, hosts)
    stage = '/srv/data/.dev-dns-' + transaction
    arguments = [stage, digest(manager), digest(hosts), before['manager_sha256'], before['hosts_sha256']]
    command = ('set -eu; umask 077; test -d /srv/data; test ! -L /srv; test ! -L /srv/data; '
               'mkdir ' + shlex.quote(stage) + '; trap ' +
               shlex.quote('rm -rf ' + stage) + ' EXIT HUP INT TERM; '
               'cat > ' + stage + '/payload.tar; echo ' +
               shlex.quote(digest(payload) + '  ' + stage + '/payload.tar') +
               ' | sha256sum -c - >/dev/null; tar -xf ' + stage + '/payload.tar -C ' + stage +
               '; /bin/sh ' + stage + '/update.sh ' + ' '.join(shlex.quote(x) for x in arguments))
    result = ssh(command, payload)
    expected = 'DEV_APPLIED ' + transaction
    if result.returncode or expected not in result.stdout.decode().splitlines():
        recovered = 'DEV_ROLLBACK_VERIFIED' in result.stdout.decode().splitlines()
        raise RuntimeError('DNS update refused; automatic rollback=' + str(recovered))


def answer_matches(answer, name, address):
    answers = []
    for line in answer.splitlines():
        fields = line.split()
        if len(fields) == 5 and fields[0] == name + '.' and fields[2:4] == ['IN', 'A']:
            answers.append(fields[4])
    return 'status: NOERROR' in answer and answers == [address]


def health(records):
    for name, address in records.items():
        for mode in ([], ['+tcp']):
            answer = subprocess.check_output(['dig', '@' + device_profile.PHONE, '-p', '5353',
                                               name, 'A', '+norecurse', '+time=2', '+tries=1'] + mode,
                                              text=True, timeout=8)
            if not answer_matches(answer, name, address):
                raise RuntimeError('DNS UDP/TCP health check failed.')


def private_store():
    for parent in (ROOT, ROOT / 'runtime'):
        persist.snapshot_lock.check_local_path(parent, directory=True)
    if not STORE.exists():
        STORE.mkdir(mode=0o700)
    persist.snapshot_lock.check_local_path(STORE, directory=True)
    if STORE.stat().st_mode & 0o077:
        raise ValueError('Private dev store required.')


def snapshot_files(snapshot):
    archive_path, _ = persist.load_snapshot(snapshot)
    with tarfile.open(archive_path, 'r:gz') as archive:
        files = []
        for name in ('srv/data/dns/manage-dns.sh', 'srv/data/dns/hosts'):
            member = archive.getmember(name)
            if not member.isfile() or member.size > MAX_BYTES:
                raise ValueError('Checkpoint DNS member refused.')
            files.append(archive.extractfile(member).read(MAX_BYTES + 1))
    bundle(*files)
    return files


def update(manager, hosts, profile):
    records = validate_hosts(hosts)
    bundle(manager, hosts)  # Validate the entire local input before SSH/backup.
    private_store()
    transaction = uuid.uuid4().hex
    directory = STORE / transaction
    directory.mkdir(mode=0o700)
    report = {'format': 1, 'service': 'dns', 'server_pin': digest(profile['server_public']),
              'state': 'prepared', 'transaction': transaction}
    def save():
        path = directory / 'result.json'
        path.write_text(json.dumps(report, indent=2) + '\n')
        path.chmod(0o600)
    save()
    before = state()
    report['before'] = before
    report['checkpoint_before'] = persist.backup()
    persist.verify(report['checkpoint_before'])
    old_manager, old_hosts = snapshot_files(report['checkpoint_before'])
    if digest(old_manager) != before['manager_sha256'] or digest(old_hosts) != before['hosts_sha256']:
        report['state'] = 'refused-concurrent-change'
        save()
        raise RuntimeError('DNS changed during checkpoint; no update started.')
    report['state'] = 'applying'
    save()
    try:
        apply(transaction, (manager, hosts), before)
        after = state()
        if (after['boot_id'] != before['boot_id'] or after['uptime'] < before['uptime']
                or after['kernel'] != before['kernel'] or after['manager_sha256'] != digest(manager)
                or after['hosts_sha256'] != digest(hosts)):
            raise RuntimeError('Boot or file integrity changed during update.')
        health(records)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        report['state'] = 'failed'
        save()
        # Recover only the two declared files; never restore unrelated services.
        try:
            recovery = state()
            if recovery['boot_id'] != before['boot_id']:
                raise RuntimeError('Recovery refused across a reboot.')
            apply(uuid.uuid4().hex, (old_manager, old_hosts), recovery)
            health(validate_hosts(old_hosts))
            report['state'] = 'rolled-back-after-failure'
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            report['state'] = 'recovery-required'
        save()
        raise RuntimeError('Update failed; ' + report['state']) from error
    report.update(state='applied', after=after)
    save()
    report['checkpoint_after'] = persist.backup()
    persist.verify(report['checkpoint_after'])
    save()
    print('DEV_UPDATED ' + transaction + '; same Linux boot; DNS UDP/TCP verified')
    return transaction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('check')
    deploy = commands.add_parser('dns')
    deploy.add_argument('--hosts', required=True, type=Path)
    rollback = commands.add_parser('rollback')
    rollback.add_argument('transaction')
    options = parser.parse_args()
    profile = device_profile.load()
    if not profile['explicit']:
        raise ValueError('An explicit deployment profile is required.')
    if options.action == 'check':
        print(json.dumps(state()))
    elif options.action == 'dns':
        update(read_regular(ROOT / 'phone/dns/manage-dns.sh'), read_regular(options.hosts), profile)
    else:
        if not re.fullmatch('[a-f0-9]{32}', options.transaction):
            raise ValueError('Transaction ID refused.')
        private_store()
        directory = STORE / options.transaction
        persist.snapshot_lock.check_local_path(directory, directory=True)
        record_path = directory / 'result.json'
        persist.snapshot_lock.check_local_path(record_path)
        record = json.loads(read_regular(record_path))
        if (record.get('state') != 'applied' or record.get('service') != 'dns'
                or record.get('server_pin') != digest(profile['server_public'])):
            raise ValueError('Rollback requires an applied DNS update for this server identity.')
        manager, hosts = snapshot_files(record['checkpoint_before'])
        update(manager, hosts, profile)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit('DEV_REFUSED: ' + str(error)) from error
