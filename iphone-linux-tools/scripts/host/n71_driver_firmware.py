"""Select three privately owned, pinned firmware/regdb data files without effects."""
import hashlib
import json
from pathlib import Path
import device_profile

RELEASE = '7.2.0-iphone6s-dart-serdev-power2'
KERNEL = '958481f87fee0949ff6a9a4af77f7eb6dac8a149'
ORIGIN = 'https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware/'
COMMIT = '31ec35bf14df835e2f9f7c8b1a8516a34f836df5'
BLOB = '3031251977875a54acd80e607a718ec9a67a529a'
CERTIFICATE = 'eeb049594eb3a83e50bfb6782e7fdf9e96fbd5c2954a0bbb0931cd55321d0bcf'
CATALOG = (
    ('brcm/brcmfmac4350-pcie.bin', 626140, '5691d1e0ceb70baf18efb7a0ec6cb84feb9edd2d0700c525b42930c4e7e4b845'),
    ('regulatory.db', 6348, '7e236caecd939c8ec98be4870bf30422f28ffef2565a38aaaa2d9ddabd0c2641'),
    ('regulatory.db.p7s', 1085, '50332f0db09b8bcc719235ec4985c27377f2cc2f42abb7b5dcf951866c5a888a'),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def evidence(root, name):
    path = root / 'docs/evidence' / name
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 16384, 'Bounded public firmware evidence required')
    result = json.loads(path.read_text())
    require(isinstance(result, dict) and type(result.get('format')) is int and result['format'] == 1,
            'Firmware evidence format differs')
    return result


def qualified(root):
    proof = evidence(root, 'n71-wlan-firmware-origin.json')
    files = proof.get('files')
    require(proof.get('origin') == ORIGIN and proof.get('commit') == COMMIT
        and proof.get('license_and_whence_inspected') is True and proof.get('firmware_executed') is False
        and proof.get('iphone_compatibility_qualified') is False and isinstance(files, dict)
        and isinstance(files.get('WHENCE'), dict) and files['WHENCE'].get('file_declared') is True,
        'Official inspected firmware origin required')
    record = files.get(CATALOG[0][0])
    require(isinstance(record, dict) and record.get('git_blob_id') == BLOB
        and type(record.get('bytes')) is int and record['bytes'] == CATALOG[0][1]
        and record.get('sha256') == CATALOG[0][2], 'Pinned firmware source record differs')
    reg = evidence(root, 'n71-regdb-calibration-source-audit.json')
    require(reg.get('kernel_source_commit') == KERNEL and isinstance(reg.get('regdb'), dict),
            'Regdb kernel binding differs')
    reg = reg['regdb']
    require(reg.get('origin') == 'https://www.kernel.org/pub/software/network/wireless-regdb/'
        and reg.get('version') == '2026.09.03'
        and reg.get('kernel_certificate_der_sha256') == CERTIFICATE
        and reg.get('cms_signature_against_explicit_kernel_certificate') is True
        and reg.get('internal_signer_certificate_not_used') is True and reg.get('altered_content_refused') is True
        and reg.get('kernel_loader_physically_verified') is False and isinstance(reg.get('files'), dict),
        'Explicit kernel-certificate regdb qualification required')
    for name, size, sha in CATALOG[1:]:
        record = reg['files'].get(name)
        require(isinstance(record, dict) and type(record.get('bytes')) is int
            and record['bytes'] == size and record.get('sha256') == sha, 'Pinned regdb source record differs')


def select(root, request):
    require(isinstance(root, Path) and root == root.absolute(), 'Absolute firmware root required')
    require(isinstance(request, dict) and set(request) == {'directory', 'release'}
        and request['release'] == RELEASE, 'Exact firmware selection request required')
    folder = request['directory']
    require(isinstance(folder, Path) and folder.is_absolute() and folder.parent == root / 'runtime',
            'Firmware directory must be private and directly under runtime')
    device_profile.protected(root / 'runtime', directory=True); device_profile.protected(folder, directory=True)
    require({p.name for p in folder.iterdir()} == {'brcm', 'regulatory.db', 'regulatory.db.p7s'},
            'Exact three-file firmware package required')
    device_profile.protected(folder / 'brcm', directory=True)
    require({p.name for p in (folder / 'brcm').iterdir()} == {'brcmfmac4350-pcie.bin'}, 'Foreign firmware refused')
    qualified(root)
    result = []
    for name, size, sha in CATALOG:
        path = folder / name; device_profile.protected(path)
        require(path.stat().st_size == size, 'Firmware file length differs')
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == sha, 'Firmware file SHA differs')
        result.append(({'path': name, 'bytes': size, 'sha256': sha}, raw))
    return result
