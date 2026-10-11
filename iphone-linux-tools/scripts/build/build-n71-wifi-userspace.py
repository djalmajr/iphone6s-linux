#!/usr/bin/env python3
"""Prepare private Wi-Fi tools in the dedicated Linux ARM64 VM."""
import argparse
from pathlib import Path
import subprocess
import n71_wifi_userspace as userspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    userspace.build(root, {'packages': options.package_dir.absolute(), 'output': options.output_dir.absolute()})
    print('N71_WIFI_USERSPACE_PACKAGE_READY; private receipt and package; phone actions=0')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit('N71_WIFI_USERSPACE_REFUSED: ' + str(error)) from error
