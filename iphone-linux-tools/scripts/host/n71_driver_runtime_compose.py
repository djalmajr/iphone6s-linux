"""Read the five qualified private WCC files without loading or copying vendors."""
import hashlib
from pathlib import Path
import struct
import device_profile
import n71_driver_runtime_build as build


def require(condition, message):
    if not condition:
        raise ValueError(message)


def select(root, request):
    require(isinstance(request, dict) and set(request) == {'directory', 'pcie_sha256', 'release'},
        'Runtime composition selection differs')
    folder = request['directory']
    require(isinstance(folder, Path) and folder.is_absolute(), 'Private absolute WCC directory required')
    device_profile.protected(folder, directory=True)
    selected = build.select(root, {'release': request['release'], 'pcie_sha256': request['pcie_sha256']})
    drivers = []
    for record in selected['drivers']:
        path = folder / record['module']; device_profile.protected(path)
        require(path.stat().st_size == record['bytes'], 'Runtime WCC file size differs')
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == record['sha256'], 'Runtime WCC file SHA differs')
        magic = ('vermagic=' + record['vermagic'] + '\0').encode()
        require(len(raw) >= 64 and raw[:7] == b'\x7fELF\x02\x01\x01'
            and struct.unpack_from('<HH', raw, 16) == (1, 183) and raw.count(magic) == 1,
            'Runtime WCC requires the selected relocatable AArch64 ABI')
        drivers.append((record, raw))
    return {'diagnostics': selected['diagnostics'], 'drivers': drivers}
