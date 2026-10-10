#!/usr/bin/env python3
"""Explicit runtime operations with a private profile and same-boot source."""
import argparse
from pathlib import Path
import struct
import n71_driver_runtime_cli as runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--action', required=True, choices=runtime.ACTIONS)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--firmware-dir', type=Path, help='Private pinned firmware/regdb package; prepared in the same boot')
    parser.add_argument('--check', action='store_true', help='Validate local profile/source only; no output, SSH or USB')
    options = parser.parse_args()
    request = {'action': options.action, 'check': options.check,
        'profile': options.profile.absolute(), 'source': options.source.absolute() if options.source else None,
        'output': options.output_dir.absolute() if options.output_dir else None}
    if options.firmware_dir is not None:
        request['firmware'] = options.firmware_dir.absolute()
    return runtime.run(Path(__file__).resolve().parents[2], request)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, struct.error) as error:
        raise SystemExit('N71_RUNTIME_REFUSED: ' + str(error)) from error
