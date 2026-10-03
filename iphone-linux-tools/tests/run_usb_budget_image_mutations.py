#!/usr/bin/env python3
"""Prove archive preservation, exact init selection and known-source refusal."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/build/rebuild-usb-budget.py'
MUTANTS = [
    ('overbroad-init', "str(PurePosixPath(name)) == 'init'", "name.lstrip('./') == 'init'"),
    ('missing-budget', 'BUDGET + ANCHOR', 'ANCHOR'),
    ('missing-discovery', '.replace(OLD_UDC, NEW_UDC, 1)', ''),
    ('known-source', "if init.count(ANCHOR) != 1 or init.count(OLD_UDC) != 1 or b'MaxPower' in init or b'bmAttributes' in init:", 'if False:'),
]


def suite(environment):
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                             '-s', str(ROOT / 'tests'), '-p', 'test_usb_budget_image.py', '-v'],
                            env=environment, capture_output=True, text=True, timeout=20)
    return result.returncode, result.stdout + result.stderr


def main():
    code, output = suite(os.environ)
    if code:
        raise RuntimeError('Image budget baseline failed: ' + output)
    for name, before, after in MUTANTS:
        with tempfile.TemporaryDirectory(prefix='iphone-budget-image-mutant-') as temporary:
            root = Path(temporary)
            for folder in ('scripts/build', 'scripts/host', 'phone/init'):
                (root / folder).mkdir(parents=True)
            for file in ('device_profile.py', 'profile_image.py'):
                shutil.copyfile(ROOT / 'scripts/host' / file, root / 'scripts/host' / file)
            for file in ('init', 'init-server'):
                shutil.copyfile(ROOT / 'phone/init' / file, root / 'phone/init' / file)
            source = SOURCE.read_text()
            if source.count(before) != 1:
                raise ValueError('Image mutation anchor refused: ' + name)
            script = root / 'scripts/build/rebuild-usb-budget.py'
            script.write_text(source.replace(before, after, 1))
            code, output = suite(dict(os.environ, USB_BUDGET_SCRIPT=str(script)))
            if not code or '\nFAIL:' not in output or '\nERROR:' in output:
                raise RuntimeError('Image mutation lacks assertion-only kill: ' + name + output)
            print('USB_IMAGE_MUTATION_KILLED ' + name, flush=True)
    print('USB_IMAGE_GATE_OK ' + str(len(MUTANTS)))


if __name__ == '__main__':
    main()
