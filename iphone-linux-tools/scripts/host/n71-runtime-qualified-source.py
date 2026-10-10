#!/usr/bin/env python3
"""Create a private, explicitly selected historical Wi-Fi source snapshot."""
import argparse
from pathlib import Path
import subprocess
import n71_runtime_source_snapshot as snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    options = parser.parse_args()
    receipt = snapshot.create(Path(__file__).resolve().parents[2],
        {'commit': options.commit, 'output': options.output_dir.absolute()})
    print('N71_RUNTIME_SOURCE_ACCEPTED commit=' + receipt['commit']
        + ' inputs=' + str(receipt['input_count']) + ' phone_accessed=0')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit('N71_RUNTIME_SOURCE_REFUSED: ' + str(error)) from error
