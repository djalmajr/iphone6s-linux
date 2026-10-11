"""Build an offline, isolated ARM64 Wi-Fi tool bundle from pinned Ubuntu data."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import posixpath
import re
import stat
import struct
import subprocess
import tarfile

PINS = 'docs/evidence/n71-wifi-userspace-packages.json'
PINS_SHA256 = 'eccfac8efd4080b6574be6a8f60d9397a1ea4474a6acd09ce4b2fbb7abed9f24'
TOOLS = {'iw': 'usr/sbin/iw', 'wpa_supplicant': 'usr/sbin/wpa_supplicant',
    'wpa_cli': 'usr/sbin/wpa_cli', 'wpa_passphrase': 'usr/bin/wpa_passphrase'}
LIBRARIES = ('usr/lib/aarch64-linux-gnu', 'lib/aarch64-linux-gnu')
LOADER = 'ld-linux-aarch64.so.1'
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_FILE = 16 * 1024 * 1024
COMMAND_ENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_host(system, machine):
    require(system == 'Linux' and machine == 'aarch64', 'Builder requires the dedicated Linux/aarch64 VM')


def private(path, directory=False):
    require(isinstance(path, Path) and path.is_absolute() and path.resolve() == path,
        'Canonical private path required')
    info = path.lstat()
    require((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
        and info.st_uid == os.geteuid() and not info.st_mode & 0o7077
        and (directory or info.st_nlink == 1), 'Owned private regular paths required')


def pins(raw):
    require(hashlib.sha256(raw).hexdigest() == PINS_SHA256, 'Wi-Fi package manifest differs from the qualified source')
    value = json.loads(raw)
    require(value['format'] == 1 and value['architecture'] == 'arm64'
        and len(value['packages']) == 38
        and sum(row['bytes'] for row in value['packages']) == value['total_bytes'], 'Package manifest scope differs')
    return value['packages']


def paths(root, request):
    require(isinstance(root, Path) and root.is_absolute() and root.resolve() == root, 'Canonical project root required')
    require(isinstance(request, dict) and set(request) == {'packages', 'output'}, 'Builder request differs')
    private(request['packages'], directory=True)
    output = request['output']
    require(isinstance(output, Path) and output.is_absolute() and output.parent == root / 'runtime'
        and not output.exists() and not output.is_symlink(), 'New output directly under runtime required')
    private(output.parent, directory=True)


def packages(directory, rows):
    private(directory, directory=True)
    names = {row['downloaded_filename'] for row in rows}
    require(len(names) == len(rows) and {path.name for path in directory.iterdir()} == names,
        'Exact qualified package set required')
    result = []
    for row in rows:
        name = row['downloaded_filename']
        require(re.fullmatch('[A-Za-z0-9.+:~%_-]+[.]deb', name), 'Package filename differs')
        path = directory / name
        private(path)
        require(path.stat().st_size == row['bytes'], 'Package size differs')
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == row['sha256'], 'Package SHA-256 differs')
        result.append((row['package'], raw))
    return result


def catalog(raw, owner):
    require(len(raw) <= MAX_ARCHIVE, 'Deb data archive exceeds budget')
    result, count = {}, 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for entry in archive:
            count += 1
            require(count <= 10000, 'Deb data entry budget exceeded')
            name = entry.name.removeprefix('./').rstrip('/')
            path = PurePosixPath(name)
            require(not path.is_absolute() and '..' not in path.parts
                and (path.as_posix() == name or entry.isdir() and name == ''), 'Deb data path escapes its root')
            require(entry.isdir() or entry.isfile() or entry.issym() or entry.islnk(), 'Special Deb data entry refused')
            if entry.isdir():
                continue
            selected = (name in TOOLS.values() or name.endswith('/copyright')
                or path.parent.as_posix() in LIBRARIES and '.so' in path.name)
            if not selected:
                continue
            require(name not in result and entry.size <= MAX_FILE, 'Duplicate or oversized selected data')
            if entry.isfile():
                stream = archive.extractfile(entry)
                require(stream is not None, 'Selected data unreadable')
                with stream:
                    data = stream.read(MAX_FILE + 1)
                require(len(data) == entry.size and len(data) <= MAX_FILE, 'Selected data size differs')
                result[name] = ('file', data, owner)
            else:
                require(not PurePosixPath(entry.linkname).is_absolute(), 'Absolute data links refused')
                target = (path.parent / entry.linkname).as_posix() if entry.issym() else entry.linkname.removeprefix('./')
                result[name] = ('link', posixpath.normpath(target), owner)
    return result


def resolve(entries, name):
    seen = set()
    while True:
        require(name not in seen and len(seen) < 32 and not name.startswith('../')
            and name in entries, 'Missing, escaping or cyclic data reference')
        seen.add(name)
        kind, value, owner = entries[name]
        if kind == 'file':
            return value, owner
        name = value


def library(entries, name):
    candidates = [resolve(entries, path) for path in entries
        if PurePosixPath(path).parent.as_posix() in LIBRARIES and PurePosixPath(path).name == name]
    require(bool(candidates), 'Missing library: ' + name)
    require(len({hashlib.sha256(raw).hexdigest() for raw, _ in candidates}) == 1, 'Conflicting library: ' + name)
    return candidates[0]


def validate_elf(raw):
    require(len(raw) >= 64 and raw[:7] == b'\x7fELF\x02\x01\x01'
        and struct.unpack_from('<H', raw, 16)[0] in (2, 3)
        and struct.unpack_from('<H', raw, 18)[0] == 183, 'Executable/shared ELF64 little-endian AArch64 required')


def dynamic(text):
    require(len(text) <= 65536 and 'Dynamic section at offset' in text, 'Dynamic ELF inspection differs')
    require('(RPATH)' not in text and '(RUNPATH)' not in text, 'External ELF search paths refused')
    needed = re.findall(r'\(NEEDED\).*Shared library: \[([^]]+)\]', text)
    require(all(re.fullmatch('[A-Za-z0-9_.+-]+', name) for name in needed), 'Nonlocal library name refused')
    interpreter = re.findall(r'Requesting program interpreter: ([^]]+)', text)
    require(interpreter in ([], ['/lib/' + LOADER]), 'Unknown program interpreter')
    return {'needed': needed, 'interpreter': interpreter}


def write_file(root, name, raw):
    path = root / name
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
    path.chmod(0o700 if name.startswith(('bin/', 'lib/')) else 0o600)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def inspect(path, raw):
    validate_elf(raw)
    result = subprocess.run(['readelf', '-d', '-l', str(path)], capture_output=True,
        text=True, env=COMMAND_ENV, timeout=15, check=True)
    return dynamic(result.stdout)


def common_licenses(root):
    source = Path('/usr/share/common-licenses')
    result = {}
    for path in sorted(source.iterdir()):
        actual = path.resolve()
        info = actual.lstat()
        require(actual.parent == source and stat.S_ISREG(info.st_mode) and info.st_uid == 0
            and not info.st_mode & 0o7022 and info.st_size <= MAX_FILE, 'Guest common license source differs')
        result['licenses/common-' + path.name] = write_file(root, 'licenses/common-' + path.name, actual.read_bytes())
    return result


def bundle(root, records):
    target = root / 'wifi-userspace-private.tar'
    with tarfile.open(target, 'x', format=tarfile.USTAR_FORMAT) as archive:
        for name in ('bin', 'lib', 'licenses'):
            entry = tarfile.TarInfo(name)
            entry.type = tarfile.DIRTYPE
            entry.mode = 0o700
            archive.addfile(entry)
        for name in sorted(records):
            raw = (root / name).read_bytes()
            require(hashlib.sha256(raw).hexdigest() == records[name]['sha256'], 'Bundle data changed before archive')
            entry = tarfile.TarInfo(name)
            entry.size = len(raw)
            entry.mode = 0o700 if name.startswith(('bin/', 'lib/')) else 0o600
            archive.addfile(entry, io.BytesIO(raw))
    target.chmod(0o600)
    return {'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


def build(root, request):
    validate_host(platform.system(), platform.machine())
    paths(root, request)
    manifest = root / PINS
    require(manifest.resolve() == manifest, 'Package manifest links refused')
    rows = pins(manifest.read_bytes())
    sources = packages(request['packages'], rows)
    output = request['output']
    output.mkdir(mode=0o700)
    entries = {}
    for owner, raw in sources:
        result = subprocess.run(['dpkg-deb', '--fsys-tarfile', '-'], input=raw,
            capture_output=True, env=COMMAND_ENV, timeout=30, check=True)
        selected = catalog(result.stdout, owner)
        require(not set(selected) & set(entries), 'Conflicting package data paths')
        entries.update(selected)
    records, objects, pending = {}, {}, [LOADER]
    for name, source in TOOLS.items():
        raw, _ = resolve(entries, source)
        records['bin/' + name] = write_file(output, 'bin/' + name, raw)
        objects['bin/' + name] = inspect(output / 'bin' / name, raw)
        require(objects['bin/' + name]['interpreter'] == ['/lib/' + LOADER], 'Tool loader differs')
        pending.extend(objects['bin/' + name]['needed'])
    while pending:
        name = pending.pop()
        if 'lib/' + name in objects:
            continue
        raw, _ = library(entries, name)
        records['lib/' + name] = write_file(output, 'lib/' + name, raw)
        objects['lib/' + name] = inspect(output / 'lib' / name, raw)
        pending.extend(objects['lib/' + name]['needed'])
    for source, (kind, raw, owner) in entries.items():
        if source.endswith('/copyright') and kind == 'file':
            records['licenses/' + owner + '.copyright'] = write_file(output, 'licenses/' + owner + '.copyright', raw)
    records.update(common_licenses(output))
    receipt = {'format': 1, 'manifest_sha256': PINS_SHA256, 'input_packages': len(rows),
        'tools': sorted(TOOLS), 'objects': objects, 'files': records, 'requires_explicit_loader': True,
        'package': bundle(output, records), 'package_code_executed': False, 'phone_actions': False}
    write_file(output, 'receipt.json', (json.dumps(receipt, indent=2) + '\n').encode())
    return receipt
