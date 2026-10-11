"""Opt-in historical input bytes; never execute archived Python or change ABI."""
import hashlib
import json
import os
from pathlib import Path
import re
import device_profile

ENV = 'IPHONE_LINUX_RUNTIME_SOURCE_RECEIPT'
PROOF = 'docs/evidence/n71-brcmfmac-caller-qualified.json'
FIELDS = {'format', 'commit', 'archive_sha256', 'proof_sha256', 'source', 'input_count',
    'input_hashes_verified', 'source_files', 'selected', 'phone_accessed'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def resolve(root, proof):
    value = os.environ.get(ENV)
    if value is None:
        return root
    require(bool(value) and isinstance(root, Path) and root.resolve() == root,
        'Explicit source receipt and canonical root required')
    path = Path(value)
    require(path.is_absolute() and path.resolve() == path and path.name == 'receipt.json'
        and path.parent.parent == root / 'runtime', 'Source receipt must be owned directly under runtime')
    for directory in (root / 'runtime', path.parent):
        device_profile.protected(directory, directory=True)
    device_profile.protected(path)
    require(0 < path.stat().st_size <= 65536, 'Source receipt budget exceeded')
    receipt = json.loads(path.read_text())
    require(isinstance(receipt, dict) and set(receipt) == FIELDS
        and type(receipt['format']) is int and receipt['format'] == 1
        and type(receipt['input_count']) is int and receipt['input_count'] == proof['input_count'] == 69
        and receipt['input_hashes_verified'] is True and receipt['phone_accessed'] is False
        and receipt['source'] == 'source' and type(receipt['source_files']) is int
        and 69 <= receipt['source_files'] <= 2048 and isinstance(receipt['selected'], dict),
        'Source receipt qualification differs')
    require(isinstance(receipt['commit'], str) and re.fullmatch('[0-9a-f]{40}', receipt['commit'])
        and isinstance(receipt['archive_sha256'], str) and re.fullmatch('[0-9a-f]{64}', receipt['archive_sha256']),
        'Source receipt provenance differs')
    expected = (root / PROOF).read_bytes()
    require(receipt['proof_sha256'] == hashlib.sha256(expected).hexdigest(), 'Source receipt belongs to another proof')
    source = path.parent / 'source'
    device_profile.protected(source, directory=True)
    require(source.resolve() == source, 'Historical source root links refused')
    recorded = source / PROOF
    require(recorded.resolve() == recorded, 'Historical proof parent links refused')
    device_profile.protected(recorded)
    require(recorded.read_bytes() == expected, 'Historical source proof differs')
    return source
