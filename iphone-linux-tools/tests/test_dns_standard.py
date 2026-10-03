"""Standard port is an explicit CLI choice, with early scope/runtime refusals."""
import argparse
from contextlib import redirect_stderr
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import dns as cli  # noqa: E402
import dns_lan as proxy  # noqa: E402


class StandardCliTests(unittest.TestCase):
    def arguments(self, extra):
        return ['dns', 'lan', '--bind', '10.1.2.3', '--allow', '10.1.2.4'] + extra

    def test_default_high_port_and_explicit_standard_port(self):
        for extra, expected in (([], 1053), (['--port', '15953'], 15953),
                                (['--standard-port'], 53)):
            with self.subTest(extra=extra):
                with patch.object(sys, 'argv', self.arguments(extra)):
                    with patch.object(proxy, 'serve') as serve:
                        cli.main()
                serve.assert_called_once()
                options = serve.call_args.args[0]
                self.assertEqual(options.port, expected)
                self.assertEqual(options.tunnel_port, 1054)
                self.assertEqual(options.bind, '10.1.2.3')
                self.assertEqual(options.allow, ['10.1.2.4'])

    def test_unsafe_or_ambiguous_standard_cli_refused_before_proxy(self):
        cases = [['--standard-port', '--port', '1053'], ['--port', '53'],
                 ['--standard-port', '--bind', '127.0.0.1'],
                 ['--standard-port', '--bind', '0.0.0.0'],
                 ['--standard-port', '--allow', '172.16.42.2'],
                 ['--standard-port', '--allow', '8.8.8.8']]
        for extra in cases:
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()):
                with patch.object(sys, 'argv', self.arguments(extra)):
                    with patch.object(proxy, 'serve') as serve:
                        with self.assertRaises(SystemExit) as error:
                            cli.main()
                        self.assertEqual(error.exception.code, 2)
                        serve.assert_not_called()

    def test_standard_runtime_root_refused_before_profile_or_activation(self):
        options = argparse.Namespace(port=53, tunnel_port=1054)
        with patch.object(proxy.os, 'getuid', return_value=0):
            with patch.object(proxy.device_profile, 'load') as load:
                with patch.object(proxy.dns_activation, 'acquire') as acquire:
                    with self.assertRaisesRegex(ValueError, 'não root'):
                        proxy.serve(options)
                    load.assert_not_called()
                    acquire.assert_not_called()


if __name__ == '__main__':
    unittest.main()
