#!/usr/bin/env python3
"""Capture the existing Pongo dt command privately; no boot or MMIO commands."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import selectors
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/boot'))
import boot_tools

MAX_OUTPUT = 2 * 1024 * 1024
PROPERTIES = ('apcie-phy-tunables', 'apcie-common-tunables', 'apcie-axi2af-tunables',
              'apcie-config-tunables', 'pcie-rc-tunables', 'function-battery_swi',
              'function-battery_swi_request', 'function-tx')


def usb_ready(blob):
    names = []
    def visit(value):
        if isinstance(value, dict):
            name = value.get('IORegistryEntryName')
            if name == 'PongoOS USB Device':
                names.append(name)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(plistlib.loads(blob))
    if len(names) != 1:
        raise ValueError('One already-running Pongo device required; no DFU started')


def summary(output):
    if not output.rstrip().endswith(b'pongoOS>') or b'device-tree' not in output:
        raise ValueError('DT completion marker missing; capture is not valid')
    text = output.decode('ascii', errors='replace')
    present = [name for name in PROPERTIES if re.search(r'(?m)^\s*' + re.escape(name) + r'\s', text)]
    return {'bytes': len(output), 'sha256': hashlib.sha256(output).hexdigest(),
            'property_names_present_anywhere': present, 'parsed_tunables': False,
            'read_only_command': 'dt', 'mmio_commands_sent': False,
            'payload_sent': False, 'boot_started': False,
            'board_and_tunable_semantics_verified': False}


def capture(arguments, timeout=45, maximum=MAX_OUTPUT):
    output = bytearray()
    deadline = time.monotonic() + timeout
    process = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    try:
        process.stdin.write(b'dt\n')
        process.stdin.close()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('DT capture deadline exceeded')
                for key, _ in selector.select(min(remaining, 0.25)):
                    chunk = os.read(key.fd, 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if len(output) + len(chunk) > maximum:
                        raise ValueError('DT capture output bound exceeded')
                    output.extend(chunk)
        code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        if code:
            raise ValueError('DT client exited unsuccessfully; output remains private')
        return bytes(output)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        with contextlib.suppress(OSError):
            process.stdin.close()
        process.stdout.close()


def destination(value):
    runtime = ROOT / 'runtime'
    path = value.absolute()
    for parent in (runtime,) + tuple(runtime.parents):
        if parent.is_symlink():
            raise ValueError('Private output parent symlink refused')
    info = runtime.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o7077 or path.parent != runtime
            or path.exists() or path.is_symlink()):
        raise ValueError('Choose a new private directory directly under runtime')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    options = parser.parse_args()
    path = destination(options.output_dir)
    executable = boot_tools.verify('pongoterm', ROOT)
    usb = subprocess.run(['ioreg', '-p', 'IOUSB', '-a'], capture_output=True, check=True, timeout=5)
    usb_ready(usb.stdout)
    output = capture([str(executable)])
    report = summary(output)
    os.umask(0o077)
    path.mkdir(mode=0o700)
    with (path / 'dt-private.txt').open('xb') as file:
        file.write(output)
    with (path / 'capture.json').open('x') as file:
        file.write(json.dumps(report, indent=2) + '\n')
    print('PONGO_N71_DT_CAPTURED_PRIVATELY; no boot, payload or MMIO command')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit('PONGO_N71_REFERENCE_REFUSED: ' + str(error)) from error
