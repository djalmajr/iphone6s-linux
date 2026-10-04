"""A prior successful cleanup never substitutes for fresh same-boot evidence."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_session_history as history

ROWS = ('[ 10.123456] dev N71_PCIE_RESET_RESTORED asserted=1 readback=1\n'
        '[ 10.234567] dev N71_PCIE_POWER_RELEASED powered=0 attached=0\n'
        '[ 11.123456] dev N71_REG_ON_REMOVE error=0 restore_pending=0\n')
BOOT = '12345678-1234-1234-1234-123456789abc'


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'runtime').mkdir(mode=0o700)
        self.directory = self.root / 'runtime/prior'
        self.directory.mkdir(mode=0o700)
        self.result = {'cleanup_verified': True, 'cleanup_errors': [],
                       'kernel_release': 'selected', 'endpoint_id': '43a314e4'}
        self.write('result-private.json', json.dumps(self.result))
        self.write('pcie-cleanup-private.log', ROWS)
        self.write('reg-unload-private.log', 'N71_REG_UNLOADED\n' + ROWS + '\nSTDERR\nwarning')

    def write(self, name, text):
        path = self.directory / name
        path.write_text(text)
        path.chmod(0o600)

    def load(self):
        return history.History(self.directory, self.root, 'selected')

    def test_exact_order_timestamp_and_optional_boot_identity(self):
        prior = self.load()
        prior.verify_live('selected\nN71_BOOT_ID ' + BOOT + '\n' + ROWS)
        # Removing the exact-history gate accepts another boot or a partial ring.
        for text in (ROWS.replace('10.123456', '20.123456'), ROWS + ROWS,
                     '\n'.join(reversed(ROWS.splitlines())), ROWS.splitlines()[0], ''):
            with self.subTest(text=text), self.assertRaises(ValueError):
                prior.verify_live(text)
        self.result['boot_id'] = BOOT
        self.write('result-private.json', json.dumps(self.result))
        prior = self.load()
        with self.assertRaises(ValueError):
            prior.verify_live('N71_BOOT_ID ' + BOOT.replace('abc', 'def') + '\n' + ROWS)

    def test_only_exact_historical_lines_are_filtered(self):
        prior = self.load()
        fresh = ROWS.replace('10.123456', '12.123456').splitlines()[0]
        self.assertEqual(prior.fresh(ROWS + fresh + '\nbound=1\n'), fresh + '\nbound=1\n')

    def test_failed_cleanup_or_endpoint_is_refused(self):
        for name, value in (('cleanup_verified', False), ('cleanup_errors', ['failed']),
                            ('kernel_release', 'other'), ('endpoint_id', '43b114e4')):
            result = dict(self.result, **{name: value})
            self.write('result-private.json', json.dumps(result))
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.load()

    def test_evidence_paths_permissions_and_missing_unload_are_refused(self):
        path = self.directory / 'reg-unload-private.log'
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            self.load()
        path.chmod(0o600)
        self.write('reg-unload-private.log', ROWS.replace('error=0', 'error=-5'))
        with self.assertRaises(ValueError):
            self.load()
        path.unlink()
        os.symlink(self.directory / 'pcie-cleanup-private.log', path)
        with self.assertRaises(ValueError):
            self.load()

    def test_history_gate_mutations_fail_assertions(self):
        source = Path(history.__file__).read_text()
        mutations = (
            ('kernel_lines(text) == self.lines', 'kernel_lines(text) == kernel_lines(text)',
             'test_exact_order_timestamp_and_optional_boot_identity'),
            ("result.get('cleanup_verified') is True", "result.get('cleanup_verified') is not None",
             'test_failed_cleanup_or_endpoint_is_refused'),
            ('line not in self.known', "'N71_' not in line", 'test_only_exact_historical_lines_are_filtered'),
            ('device_profile.protected(path)', 'path.stat()',
             'test_evidence_paths_permissions_and_missing_unload_are_refused'),
        )
        for before, after, method in mutations:
            self.assertEqual(source.count(before), 1)
            namespace = {}
            exec(compile(source.replace(before, after, 1), 'mutant-history.py', 'exec'), namespace)
            with patch.dict(globals(), {'history': SimpleNamespace(**namespace)}):
                case = HistoryTests(method)
                case.setUp()
                try:
                    with self.assertRaises(AssertionError):
                        getattr(case, method)()
                finally:
                    case.doCleanups()


if __name__ == '__main__':
    unittest.main()
