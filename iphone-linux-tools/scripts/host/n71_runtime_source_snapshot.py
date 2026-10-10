"""Freeze explicit Git source and reuse historical production qualification."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import device_profile
import n71_driver_runtime_build as build

PROOF = 'docs/evidence/n71-brcmfmac-caller-qualified.json'
MAX_FILES = 2048
MAX_BYTES = 16 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def archive(root, commit):
    require(type(commit) is str and re.fullmatch('[0-9a-f]{40}', commit), 'Explicit full Git commit required')
    top = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=root, text=True).strip())
    prefix = root.relative_to(top).as_posix()
    require(prefix != '.' and not prefix.startswith('../'), 'Project must be below the Git root')
    kind = subprocess.check_output(['git', 'cat-file', '-t', commit], cwd=root, text=True).strip()
    require(kind == 'commit', 'Source object must be a local commit')
    inventory = subprocess.check_output(['git', 'ls-tree', '-rlz', commit, '--', prefix + '/'], cwd=top)
    entries = [row for row in inventory.split(b'\0') if row]
    sizes = []
    for row in entries:
        metadata, _ = row.split(b'\t', 1)
        mode, kind, _, size = metadata.split()
        require(mode in (b'100644', b'100755') and kind == b'blob', 'Git source links or special files refused')
        sizes.append(int(size))
    require(0 < len(entries) <= MAX_FILES and sum(sizes) <= MAX_BYTES, 'Git source budget exceeded')
    raw = subprocess.check_output(['git', 'archive', '--format=tar', commit, prefix + '/'], cwd=top)
    require(len(raw) <= MAX_BYTES + MAX_FILES * 2048, 'Source archive budget exceeded')
    return raw, prefix


def members(raw, prefix):
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as source:
        for member in source:
            path = PurePosixPath(member.name.rstrip('/'))
            require(not path.is_absolute() and '..' not in path.parts
                and path.as_posix() == member.name.rstrip('/'), 'Noncanonical archive path refused')
            require(path == PurePosixPath(prefix) or PurePosixPath(prefix) in path.parents,
                'Archive entry outside project refused')
            require(member.isdir() or member.isfile(), 'Archive links or special entries refused')
            if member.isdir():
                continue
            name = path.relative_to(prefix).as_posix()
            require(name not in files and member.size <= MAX_BYTES, 'Duplicate or oversized source entry refused')
            stream = source.extractfile(member)
            require(stream is not None, 'Source entry unreadable')
            with stream:
                files[name] = (stream.read(), bool(member.mode & 0o111))
    require(0 < len(files) <= MAX_FILES and sum(len(raw) for raw, _ in files.values()) <= MAX_BYTES,
        'Extracted source budget exceeded')
    return files


def create(root, request):
    require(isinstance(request, dict) and set(request) == {'commit', 'output'}, 'Source snapshot request differs')
    require(isinstance(root, Path) and root.is_absolute() and root.resolve() == root, 'Canonical project root required')
    output = request['output']
    require(isinstance(output, Path) and output.is_absolute() and output.parent == root / 'runtime'
        and output.name not in ('', '.', '..') and not output.exists() and not output.is_symlink(),
        'New private snapshot directly under runtime required')
    device_profile.protected(output.parent, directory=True)
    require(output.parent.resolve() == output.parent, 'Snapshot parent links refused')
    raw, prefix = archive(root, request['commit'])
    files = members(raw, prefix)
    expected = (root / PROOF).read_bytes()
    require(PROOF in files and files[PROOF][0] == expected, 'Historical qualification record differs')
    # Historical code runs only when its scripts still match this trusted checkout.
    for name, (data, _) in files.items():
        if name.startswith('scripts/') and name.endswith('.py'):
            path = root / name
            require(path.is_file() and not path.is_symlink() and path.read_bytes() == data,
                'Historical script differs from current trusted source')
    output.mkdir(mode=0o700)
    snapshot = output / 'source'
    snapshot.mkdir(mode=0o700)
    for name, (data, executable) in files.items():
        path = snapshot / name
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        path.chmod(0o700 if executable else 0o600)
    proof = json.loads(expected)
    build.inputs(snapshot, proof)
    selector = """import json,sys
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'scripts/host'))
import n71_driver_runtime_build as build
proof=json.loads((root/'docs/evidence/n71-brcmfmac-caller-qualified.json').read_text())
print(json.dumps(build.select(root,{'release':proof['module']['vermagic'].split()[0],'pcie_sha256':proof['module']['sha256']})))
"""
    selected = json.loads(subprocess.check_output(['python3', '-B', '-c', selector, str(snapshot)], text=True, timeout=30))
    receipt = {'format': 1, 'commit': request['commit'], 'archive_sha256': hashlib.sha256(raw).hexdigest(),
        'proof_sha256': hashlib.sha256(expected).hexdigest(), 'source': 'source',
        'input_count': proof['input_count'], 'input_hashes_verified': True,
        'source_files': len(files), 'selected': selected, 'phone_accessed': False}
    path = output / 'receipt.json'
    with path.open('x') as stream:
        stream.write(json.dumps(receipt, indent=2) + '\n')
    path.chmod(0o600)
    return receipt
