#!/usr/bin/env python3
"""Repack the preserved console image with only the loopback init correction.

Run as root inside the dedicated VM with private inputs in the base directory.
The fixed original digest and exact init delta keep this historical rebuild
bounded. Its output contains the server identity and must never be published.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

base = Path('/home/ubuntu/iphone6s-loopback-input')
archive = base / 'original.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == 'b51e78b9acafea87685f3e09c9329a46929e288c582a91deb76593979480844e'
work = Path(tempfile.mkdtemp(prefix='iphone6s-loopback.', dir='/home/ubuntu'))
work.chmod(0o700)
(base / 'work-path').write_text(str(work))

def unpack(source, destination):
    destination.mkdir()
    subprocess.run(['bash', '-o', 'pipefail', '-c',
                    'gzip -dc "$1" | cpio -idm --no-absolute-filenames',
                    'unpack', str(source)], cwd=destination, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def manifest(root):
    result = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            item = Path(parent) / name
            info = item.lstat()
            # cpio extraction updates parent directory timestamps as it writes.
            mtime = None if stat.S_ISDIR(info.st_mode) else int(info.st_mtime)
            record = [info.st_mode, info.st_uid, info.st_gid, info.st_rdev,
                      info.st_nlink, mtime]
            if stat.S_ISREG(info.st_mode):
                record.append(hashlib.sha256(item.read_bytes()).hexdigest())
            elif stat.S_ISLNK(info.st_mode):
                record.append(os.readlink(item))
            result[str(item.relative_to(root))] = record
    return result

root = work / 'root'
unpack(archive, root)
before = manifest(root)
original_init = (root / 'init').read_bytes()
new_init = (base / 'init').read_bytes()
assert new_init == original_init.replace(b'uname -a\n', b'uname -a\nip link set lo up\n', 1), 'Unexpected source differences'
shutil.copyfile(base / 'init', root / 'init')
(root / 'init').chmod(0o755)
output = base / 'candidate.gz'
with output.open('wb') as stream:
    subprocess.run(['bash', '-o', 'pipefail', '-c',
                    'find . -print0 | cpio --null -o -H newc 2>/dev/null | gzip -n -9'],
                   cwd=root, stdout=stream, check=True)
output.chmod(0o600)
check = work / 'check'
unpack(output, check)
after = manifest(check)
assert before.keys() == after.keys(), 'Archive paths changed'
changes = [name for name in before if before[name] != after[name]]
assert changes == ['init'], changes
assert before['init'][:5] == after['init'][:5], 'Init permissions or links changed'
report = {'entries': len(before), 'changed': changes,
          'candidate_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
          'candidate_bytes': output.stat().st_size,
          'init_sha256': hashlib.sha256(new_init).hexdigest()}
(base / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
