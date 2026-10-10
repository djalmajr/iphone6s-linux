#!/bin/bash
set -euo pipefail

# Build only in an isolated unprivileged ARM64 Linux guest; never touch USB.
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != aarch64 ] || [ "$EUID" -eq 0 ]; then
    printf 'Run as the user of an isolated Linux ARM64 guest.\n' >&2
    exit 1
fi
if [ "$#" -ne 2 ]; then
    printf 'Usage: %s PINNED_SOURCE_ROOT NEW_BUILD_DIRECTORY\n' "$0" >&2
    exit 2
fi
source_root=$(realpath -e "$1")
build_root=$(realpath -m "$2")
verifier=$(cd "$(dirname "$0")" && pwd)/verify-pongo-build.py
pongo="$source_root/PongoOS"
cctools="$source_root/cctools-port"
pongo_commit=bb492b004265ce91123caa23b8bc04b2eff6d2b7
newlib_commit=f9ea5054de8fb51dff6f6d3c2e7cdd4aa89744b8
cctools_commit=e79d784d667816e4b15a0abd78828f9abb0a0b99
if [ -e "$build_root" ] || [ -L "$build_root" ]; then
    printf 'Choose a new build directory; previous outputs are preserved.\n' >&2
    exit 1
fi
case "$build_root/" in "$source_root/"*) printf 'Build directory must be outside source root.\n' >&2; exit 1;; esac
verify_source() {
    test "$(git -C "$1" rev-parse HEAD)" = "$2"
    test -z "$(git -C "$1" status --porcelain --untracked-files=no)"
}
verify_source "$pongo" "$pongo_commit"
verify_source "$pongo/newlib" "$newlib_commit"
verify_source "$cctools" "$cctools_commit"
test "$(git -C "$pongo" ls-tree HEAD newlib | awk '{print $3}')" = "$newlib_commit"
for folder in "$pongo/build" "$pongo/newlib/build" "$pongo/newlib/aarch64-none-darwin"; do
    if [ -e "$folder" ] || [ -L "$folder" ]; then
        printf 'Pongo/newlib require a fresh source checkout without build outputs.\n' >&2
        exit 1
    fi
done
test -x "$cctools/cctools/configure"
test -f "$verifier"
for command in clang-18 clang++-18 llvm-config-18 llvm-ar-18 llvm-ranlib-18 make python3; do
    command -v "$command" > /dev/null
done
umask 077
mkdir -m 700 "$build_root"
mkdir -m 700 "$build_root/logs" "$build_root/artifacts" "$build_root/cctools-build"
prefix="$build_root/toolchain"
epoch=$(git -C "$pongo" show -s --format=%ct HEAD)
export PATH=/usr/lib/llvm-18/bin:/usr/bin:/bin
export LC_ALL=C SOURCE_DATE_EPOCH=$epoch
printf 'CCTOOLS_CONFIGURE_STARTED\n'
(
    cd "$build_root/cctools-build"
    env -i PATH="$PATH" LC_ALL=C SOURCE_DATE_EPOCH="$epoch" CC=clang-18 CXX=clang++-18 \
        "$cctools/cctools/configure" --prefix="$prefix" --target=aarch64-apple-darwin \
        --with-llvm-config=/usr/bin/llvm-config-18 --disable-tapi-support --disable-xar-support
) > "$build_root/logs/cctools-configure.log" 2>&1
printf 'CCTOOLS_COMPILE_STARTED\n'
env -i PATH="$PATH" LC_ALL=C SOURCE_DATE_EPOCH="$epoch" \
    make -C "$build_root/cctools-build" -j2 > "$build_root/logs/cctools-build.log" 2>&1
env -i PATH="$PATH" LC_ALL=C \
    make -C "$build_root/cctools-build" install > "$build_root/logs/cctools-install.log" 2>&1
linker="$prefix/bin/aarch64-apple-darwin-ld"
test -x "$linker"
printf 'PONGO_COMPILE_STARTED\n'
env -i PATH="$PATH" LC_ALL=C SOURCE_DATE_EPOCH="$epoch" \
    make -C "$pongo" -j2 build/Pongo.bin CC=clang-18 EMBEDDED_CC=clang-18 \
    EMBEDDED_LD="$linker" LLVM_AR=llvm-ar-18 LLVM_RANLIB=llvm-ranlib-18 \
    > "$build_root/logs/pongo-build.log" 2>&1
verify_source "$pongo" "$pongo_commit"
verify_source "$pongo/newlib" "$newlib_commit"
test "$(git -C "$cctools" rev-parse HEAD)" = "$cctools_commit"
generated_header="$cctools/cctools/include/llvm-c/lto.h"
cmp "$generated_header" /usr/lib/llvm-18/include/llvm-c/lto.h
changes=$(git -C "$cctools" status --porcelain --untracked-files=no)
if [ -n "$changes" ] && [ "$changes" != ' M cctools/include/llvm-c/lto.h' ]; then
    printf 'Unexpected tracked source changes after configure/build.\n' >&2
    exit 1
fi
git -C "$cctools" diff -- cctools/include/llvm-c/lto.h > "$build_root/logs/generated-lto-header.diff"
cp "$pongo/build/Pongo" "$build_root/artifacts/Pongo"
cp "$pongo/build/Pongo.bin" "$build_root/artifacts/Pongo.bin"
python3 "$verifier" "$build_root/artifacts/Pongo" "$build_root/artifacts/Pongo.bin" \
    > "$build_root/logs/verify.log"
python3 - "$build_root" "$epoch" "$generated_header" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys
root = Path(sys.argv[1])
outputs = {}
for name in ('Pongo', 'Pongo.bin'):
    path = root / 'artifacts' / name
    outputs[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}
report = {'format': 1, 'pongo_commit': 'bb492b004265ce91123caa23b8bc04b2eff6d2b7',
          'newlib_commit': 'f9ea5054de8fb51dff6f6d3c2e7cdd4aa89744b8',
          'cctools_commit': 'e79d784d667816e4b15a0abd78828f9abb0a0b99',
          'source_epoch': int(sys.argv[2]), 'target': 'arm64-apple-ios12.0',
          'compiler': subprocess.check_output(['clang-18', '--version'], text=True).splitlines()[0],
          'outputs': outputs, 'build_exit_code': 0, 'macho_extraction_verified': True,
          'generated_lto_header_sha256': hashlib.sha256(Path(sys.argv[3]).read_bytes()).hexdigest(),
          'generated_lto_header_matches_ubuntu_package': True,
          'physical_boot_tested': False, 'preserved_pongo_changed': False, 'host_packages_installed': False}
(root / 'artifacts/provenance.json').write_text(json.dumps(report, indent=2) + '\n')
PY
chmod 600 "$build_root/artifacts/"*
printf 'PONGO_SOURCE_BUILD_VERIFIED; no USB action or host installation\n'
