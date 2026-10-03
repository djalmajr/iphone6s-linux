#!/bin/bash
set -euo pipefail

# Build only in an isolated, unprivileged Linux ARM64 guest; never install outputs.
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != aarch64 ] || [ "$EUID" -eq 0 ]; then
    printf 'Run as the VM user in an isolated Linux ARM64 guest.\n' >&2
    exit 1
fi
if [ "$#" -ne 2 ] && [ "$#" -ne 3 ]; then
    printf 'Usage: %s SOURCE_DIRECTORY NEW_BUILD_DIRECTORY [n71-dart-tcr-v1]\n' "$0" >&2
    exit 2
fi
source_dir=$(realpath -e "$1")
build_dir=$(realpath -m "$2")
fragment=$(cd "$(dirname "$0")" && pwd)/kernel-n71.config
patch_checker=$(dirname "$fragment")/kernel_patchset.py
patchset=${3:-}
patch_record=
commit=958481f87fee0949ff6a9a4af77f7eb6dac8a149
if [ -e "$build_dir" ] || [ -L "$build_dir" ]; then
    printf 'Build directory already exists; preserve it and choose another.\n' >&2
    exit 1
fi
case "$build_dir/" in
    "$source_dir/"*) printf 'Build must remain outside the source checkout.\n' >&2; exit 1 ;;
esac
test "$(git -C "$source_dir" rev-parse HEAD)" = "$commit"
if [ -n "$patchset" ]; then
    patch_record=$(python3 "$patch_checker" check "$source_dir" "$patchset")
else
    test -z "$(git -C "$source_dir" status --porcelain --untracked-files=no)"
fi
test -f "$source_dir/arch/arm64/boot/dts/apple/s8000-n71.dts"
free_kib=$(df -Pk "$(dirname "$build_dir")" | awk 'NR == 2 {print $4}')
if [ "$free_kib" -lt 8388608 ]; then
    printf 'At least 8 GiB of free guest disk is required before this build.\n' >&2
    exit 1
fi
umask 077
mkdir -m 700 "$build_dir"
mkdir -m 700 "$build_dir/logs" "$build_dir/artifacts"
epoch=$(git -C "$source_dir" show -s --format=%ct HEAD)
SOURCE_DATE_EPOCH=$epoch
KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$epoch" '+%a %b %e %T %Y')
export SOURCE_DATE_EPOCH KBUILD_BUILD_TIMESTAMP
export KBUILD_BUILD_USER=build KBUILD_BUILD_HOST=iphone6s-kernel-source KBUILD_BUILD_VERSION=1
export LC_ALL=C LOCALVERSION=
make -C "$source_dir" O="$build_dir" ARCH=arm64 defconfig > "$build_dir/logs/config.log" 2>&1
bash "$source_dir/scripts/kconfig/merge_config.sh" -m -O "$build_dir" \
    "$build_dir/.config" "$fragment" >> "$build_dir/logs/config.log" 2>&1
make -C "$source_dir" O="$build_dir" ARCH=arm64 olddefconfig >> "$build_dir/logs/config.log" 2>&1
python3 - "$fragment" "$build_dir/.config" <<'PY'
from pathlib import Path
import re
import sys

def values(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        match = re.fullmatch(r'(CONFIG_[A-Z0-9_]+)=(.*)', line)
        disabled = re.fullmatch(r'# (CONFIG_[A-Z0-9_]+) is not set', line)
        if match:
            result[match[1]] = match[2]
        elif disabled:
            result[disabled[1]] = 'n'
    return result

required, actual = map(values, sys.argv[1:])
missing = [key for key, value in required.items() if actual.get(key, 'n') != value]
if missing:
    raise SystemExit('Required Kconfig values did not survive: ' + ', '.join(missing))
print('KERNEL_CONFIG_VERIFIED', len(required))
PY
printf 'KERNEL_COMPILE_STARTED\n'
make -C "$source_dir" O="$build_dir" ARCH=arm64 -j2 Image apple/s8000-n71.dtb \
    > "$build_dir/logs/build.log" 2>&1
if [ -n "$patchset" ]; then
    test "$patch_record" = "$(python3 "$patch_checker" check "$source_dir" "$patchset")"
else
    test -z "$(git -C "$source_dir" status --porcelain --untracked-files=no)"
fi
cp "$build_dir/arch/arm64/boot/Image" "$build_dir/artifacts/Image"
cp "$build_dir/arch/arm64/boot/dts/apple/s8000-n71.dtb" "$build_dir/artifacts/s8000-n71.dtb"
cp "$build_dir/.config" "$build_dir/artifacts/config"
gzip -n -9 -c "$build_dir/artifacts/Image" > "$build_dir/artifacts/Image.gz"
python3 - "$build_dir" "$commit" "$epoch" "$patch_record" <<'PY'
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

root = Path(sys.argv[1])
artifacts = root / 'artifacts'
header = (artifacts / 'Image').read_bytes()[:64]
if header[56:60] != b'ARM\x64' or (struct.unpack_from('<Q', header, 24)[0] >> 1) & 3 != 2:
    raise SystemExit('Image is not an ARM64 16 KiB kernel.')
compatible = subprocess.check_output(['fdtget', str(artifacts / 's8000-n71.dtb'), '/', 'compatible'], text=True).strip()
if 'apple,n71' not in compatible.split():
    raise SystemExit('Device tree does not identify N71.')
outputs = {}
for path in artifacts.iterdir():
    with path.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    outputs[path.name] = {'sha256': digest, 'bytes': path.stat().st_size}
report = {'format': 1, 'source_commit': sys.argv[2], 'source_epoch': int(sys.argv[3]),
          'source_patchset': json.loads(sys.argv[4]) if sys.argv[4] else None,
          'kernel_release': (root / 'include/config/kernel.release').read_text().strip(),
          'page_size_kib': 16, 'dtb_compatible': compatible, 'usb_ncm': 'builtin',
          'compiler_version': subprocess.check_output(['gcc', '-dumpfullversion'], text=True).strip(),
          'outputs': outputs, 'physical_boot_tested': False, 'installed': False}
(artifacts / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')
print('KERNEL_BUILD_VERIFIED', report['kernel_release'])
PY
printf 'Build complete; outputs were not installed.\n'
