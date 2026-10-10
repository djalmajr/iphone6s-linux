#!/usr/bin/env python3
"""Extract a private N71 calibration candidate from an existing Pongo capture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import n71_runtime_tunables as capture

NODE = '/device-tree/arm-io/uart4/wlan'
PROPERTY = 'wifi-calibration-msf'
SIZE = 1024


def extract(source, output):
    source = capture.private_path(source)
    if source.stat().st_size > capture.MAX_CAPTURE:
        raise ValueError('Capture input bound refused')
    output = output.absolute()
    runtime = capture.private_path(capture.ROOT / 'runtime', directory=True)
    if output.parent != runtime or output.exists() or output.is_symlink():
        raise ValueError('Choose a new private output directly under runtime')
    raw = source.read_bytes()
    blob = capture.properties_capture(raw, {(NODE, PROPERTY): ('calibration', SIZE)})['calibration']
    if len(blob) != SIZE:
        raise ValueError('Exact N71 calibration candidate size required')
    report = {'format': 1, 'board': 'N71/S8000', 'path': NODE, 'property': PROPERTY,
              'capture_sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(blob),
              'sha256': hashlib.sha256(blob).hexdigest(), 'hardware_writes': False,
              'firmware_executed': False, 'physical_acceptance': False}
    previous = os.umask(0o077)
    try:
        output.mkdir(mode=0o700)
        with (output / 'calibration-private.bin').open('xb') as file:
            file.write(blob)
        with (output / 'provenance-private.json').open('x') as file:
            file.write(json.dumps(report, indent=2) + '\n')
    finally:
        os.umask(previous)
    print('N71_WIFI_CALIBRATION_EXTRACTED; private candidate; no hardware action', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    options = parser.parse_args()
    extract(options.input, options.output_dir)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit('N71_WIFI_CALIBRATION_REFUSED: ' + str(error)) from error
