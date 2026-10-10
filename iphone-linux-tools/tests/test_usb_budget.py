"""Observe the real init setup budget before its simulated USB bind."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UsbBudget(unittest.TestCase):
    def test_both_init_templates_declare_budget_before_udc_selection(self):
        for template in ('init', 'init-server'):
            with self.subTest(template=template), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary).resolve()
                gadget = work / 'gadget'
                tools = work / 'tools'
                tools.mkdir()
                source = (ROOT / 'phone/init' / template).read_text()
                start = source.index('gadget=/sys/kernel/config/usb_gadget/iphone6s')
                end = source.index('    echo "$udc" > "$gadget/UDC"', start)
                end = source.index('\n', end)
                setup = source[start:end] + '\nfi\n'
                setup = setup.replace('gadget=/sys/kernel/config/usb_gadget/iphone6s',
                                      'gadget=' + shlex.quote(str(gadget)), 1)
                observer = tools / 'find'
                observer.write_text('''#!/bin/sh
set -eu
[ "$1" = /sys/class/udc ]
[ "$(cat "$TEST_GADGET/configs/c.1/MaxPower")" = 500 ]
[ "$(cat "$TEST_GADGET/configs/c.1/bmAttributes")" = 0x80 ]
echo /sys/class/udc/fixture-udc
''')
                observer.chmod(0o755)
                env = dict(os.environ, TEST_GADGET=str(gadget), PATH=str(tools) + os.pathsep + os.environ['PATH'])
                result = subprocess.run(['/bin/sh', '-c', setup], env=env,
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue((gadget / 'UDC').exists(), result.stderr)
                self.assertEqual((gadget / 'UDC').read_text(), 'fixture-udc\n')
                self.assertEqual((gadget / 'configs/c.1/MaxPower').read_text(), '500\n')


if __name__ == '__main__':
    unittest.main()
