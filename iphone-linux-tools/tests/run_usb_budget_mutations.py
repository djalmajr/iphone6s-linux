#!/usr/bin/env python3
"""Exercise missing and late power-budget declarations in actual init snippets."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def suite(root):
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover',
                             '-s', str(root / 'tests'), '-p', 'test_usb_budget.py', '-v'],
                            capture_output=True, text=True, timeout=15)
    return result.returncode, result.stdout + result.stderr


def main():
    code, output = suite(ROOT)
    if code:
        raise RuntimeError('Budget baseline failed: ' + output)
    count = 0
    for template in ('init', 'init-server'):
        for mutation in ('missing-current', 'missing-attribute', 'late-budget'):
            with tempfile.TemporaryDirectory(prefix='iphone-budget-mutant-') as temporary:
                root = Path(temporary)
                (root / 'tests').mkdir()
                (root / 'phone/init').mkdir(parents=True)
                shutil.copyfile(ROOT / 'tests/test_usb_budget.py', root / 'tests/test_usb_budget.py')
                for name in ('init', 'init-server'):
                    shutil.copyfile(ROOT / 'phone/init' / name, root / 'phone/init' / name)
                file = root / 'phone/init' / template
                source = file.read_text()
                current = 'echo 500 > "$gadget/configs/c.1/MaxPower"\n'
                attribute = 'echo 0x80 > "$gadget/configs/c.1/bmAttributes"\n'
                if source.count(current) != 1 or source.count(attribute) != 1:
                    raise ValueError('Budget mutation anchors refused.')
                if mutation == 'missing-current':
                    source = source.replace(current, '', 1)
                elif mutation == 'missing-attribute':
                    source = source.replace(attribute, '', 1)
                else:
                    source = source.replace(current, '', 1).replace(attribute, '', 1)
                    source = source.replace('echo "UDC: $udc"\n', 'echo "UDC: $udc"\n' + current + attribute, 1)
                file.write_text(source)
                code, output = suite(root)
                if not code or '\nFAIL:' not in output or '\nERROR:' in output:
                    raise RuntimeError('Budget mutation lacks assertion kill: ' + mutation + output)
                count += 1
                print('USB_BUDGET_MUTATION_KILLED ' + template + '/' + mutation, flush=True)
    print('USB_BUDGET_GATE_OK ' + str(count))


if __name__ == '__main__':
    main()
