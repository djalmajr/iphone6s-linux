"""Select only the preserved compiled PMD inputs, never archived executable code."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import device_profile

ENV = 'IPHONE_LINUX_PMD_SOURCE_RECEIPT'
COMMIT = '28b2c922a6a0ca847489b3253cfbe52b1c3e16e9'
INPUTS_PIN = '8dcc0e2684c3e14ba3d0cfbdd91a755815c1d2224d1a5d63351a0575e7e28158'
COMPILED_PIN = '4e9221335b6f944f99a33fb3172307f612767ff21312b3616abc657b2c991e0f'
FIELDS = {'format', 'status', 'source_commit', 'source', 'inputs', 'compiled_input_count',
          'native_input_count', 'files', 'bytes', 'compiled_manifest_sha256',
          'no_code_executed_from_copy', 'no_phone_access'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def resolve(root):
    value = os.environ.get(ENV)
    if value is None:
        return root
    require(bool(value) and isinstance(root, Path) and root.is_absolute() and root.resolve() == root,
            'Explicit PMD source receipt and canonical project required')
    path = Path(value)
    require(path.is_absolute() and path.resolve() == path and path.name == 'receipt-private.json'
            and path.parent.parent == root / 'runtime', 'PMD source receipt must be directly under private runtime')
    for directory in (root / 'runtime', path.parent):
        device_profile.protected(directory, directory=True)
    device_profile.protected(path)
    require(0 < path.stat().st_size <= 65536, 'PMD source receipt exceeds budget')
    data = json.loads(path.read_text())
    require(isinstance(data, dict) and set(data) == FIELDS
            and type(data.get('format')) is int and data['format'] == 1
            and data.get('status') == 'preserved_compiled_inputs'
            and data.get('source_commit') == COMMIT and data.get('source') == 'source'
            and data.get('no_code_executed_from_copy') is True and data.get('no_phone_access') is True
            and data.get('compiled_manifest_sha256') == COMPILED_PIN,
            'PMD source provenance differs from the compiled snapshot')
    for name, expected in (('compiled_input_count', 62), ('native_input_count', 69), ('files', 78), ('bytes', 633894)):
        require(type(data.get(name)) is int and data[name] == expected, 'PMD source count or byte budget differs')
    inputs = data.get('inputs')
    require(isinstance(inputs, dict) and len(inputs) == 78
            and hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == INPUTS_PIN,
            'PMD preserved input manifest differs')
    source = path.parent / 'source'
    device_profile.protected(source, directory=True)
    require(source.resolve() == source, 'PMD source root aliases refused')
    for name, record in inputs.items():
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and '..' not in relative.parts and relative.as_posix() == name,
                'PMD preserved source path refused')
        current = source
        for part in relative.parts[:-1]:
            current = current / part
            device_profile.protected(current, directory=True)
        current = source / name
        device_profile.protected(current)
        require(current.resolve() == current and current.stat().st_size == record['bytes']
                and hashlib.sha256(current.read_bytes()).hexdigest() == record['sha256'],
                'PMD preserved source content changed')
    return source
