"""Real held continuation retains getter observations and refuses other history."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_n71_held_session as fixture

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71_held_history.py'
SPEC = importlib.util.spec_from_file_location('held_history_under_test',
                                            os.environ.get('N71_HELD_HISTORY_SCRIPT', SOURCE))
HISTORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HISTORY)


class HeldHistoryTests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.HeldSessionTests('test_acquire_then_release_preserves_owners_until_explicit_same_boot_cleanup')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        replacement = patch.object(fixture.HELD, 'n71_held_history', HISTORY)
        replacement.start()
        self.addCleanup(replacement.stop)
        code, self.session, self.source = self.case.execute('acquire')
        self.assertEqual(code, 0)

    def refused(self, name):
        before = len(self.case.phone.calls)
        code, session, _ = self.case.execute(name, self.source)
        self.assertEqual(code, 1)
        self.assertIn('held_error', session.result)
        self.assertEqual(self.case.phone.cleanup_calls, 0)
        self.assertTrue(self.case.phone.reg and self.case.phone.pcie and self.case.phone.held)
        self.assertTrue(all('printf "cleanup' not in command and 'rmmod' not in command
                            for _, command in self.case.phone.calls[before:]))

    def test_extra_getter_reads_are_preserved_in_proof_and_checkpoint(self):
        # Mutation captured: reject benign getter events between same-boot continuations.
        self.case.phone.snapshot(self.session)
        self.case.phone.snapshot(self.session)
        code, session, output = self.case.execute('release', self.source)
        self.assertEqual(code, 0)
        self.assertTrue(session.result['cleanup_verified'])
        self.assertEqual(self.case.phone.cleanup_calls, 1)
        journal = json.loads((output / 'held-state-private.json').read_text())
        proof = (output / 'pcie-cleanup-proof-private.log').read_text()
        checkpoint = (output / journal['checkpoint']['name']).read_text()
        self.assertEqual(proof.count('N71_REG_ON_READ '), 5)
        self.assertEqual(checkpoint.count('N71_REG_ON_READ '), 5)

    def test_failed_invalid_or_different_reads_refuse_before_cleanup(self):
        # Mutations captured: admit read errors, invalid values, a changed latch or a foreign event.
        history = self.case.phone.history
        for index, event in enumerate(('N71_REG_ON_READ error=-5 value_valid=1 value=81',
                                       'N71_REG_ON_READ error=0 value_valid=0 value=81',
                                       'N71_REG_ON_READ error=0 value_valid=1 value=80',
                                       'N71_PCIE_FOREIGN operation')):
            with self.subTest(event=event):
                self.case.phone.history = history + fixture.timestamp(event, 180)
                self.refused('invalid-' + str(index))

    def test_read_record_suffix_is_not_accepted_as_a_complete_observation(self):
        # Mutation captured: prefix regex match hides trailing operation text.
        self.case.phone.history += fixture.timestamp('N71_REG_ON_READ error=0 value_valid=1 value=81 trailing', 180)
        self.refused('trailing')

    def test_changed_history_prefix_refuses_even_with_a_valid_fresh_getter(self):
        # Mutation captured: discard the checkpoint history while keeping its fresh suffix.
        self.case.phone.history = self.case.phone.history.replace('N71_TEST_BASELINE', 'N71_TEST_CHANGED')
        self.refused('prefix')

    def test_missing_getter_event_refuses_before_cleanup(self):
        # Mutation captured: accept a snapshot that failed to capture its getter event.
        self.case.phone.overrides['held-resume-live'] = lambda phone, session, text: (
            0, text.replace(fixture.timestamp('N71_REG_ON_READ error=0 value_valid=1 value=81\n',
                                              160 + phone.reg_reads), ''))
        self.refused('missing')

    def test_new_read_after_reg_unload_refuses_completed_release(self):
        # Mutation captured: admit unaccounted history when no REG_ON getter can have run.
        code, _, released = self.case.execute('release', self.source)
        self.assertEqual(code, 0)
        self.case.phone.history += fixture.timestamp('N71_REG_ON_READ error=0 value_valid=1 value=80', 190)
        code, session, _ = self.case.execute('absent', released)
        self.assertEqual(code, 1)
        self.assertIn('held_error', session.result)
        self.assertEqual(self.case.phone.cleanup_calls, 1)

    @unittest.skipIf(os.environ.get('N71_HELD_HISTORY_MUTATION_CHILD'), 'mutation child')
    def test_mutations_fail_behavioral_assertions(self):
        source = SOURCE.read_text()
        variants = {
            'history-prefix': ('after[:len(before)] == before', 'True'),
            'history-extra': ('extra and all(', 'True or all('),
            'history-read-error': ('error=0 value_valid', r'error=-?\d+ value_valid'),
            'history-read-valid': ('value_valid=1', 'value_valid=[01]'),
            'history-read-value': (' + values[0]', " + '[0-9a-f]{2}'"),
            'history-complete-record': ('re.fullmatch(pattern, line)', 're.match(pattern, line)'),
            'history-reg-absent': ('require(not extra,', 'require(True,'),
        }
        with tempfile.TemporaryDirectory(prefix='n71-held-history-mutations-') as folder:
            for name, (before, after) in variants.items():
                with self.subTest(name=name):
                    self.assertEqual(source.count(before), 1)
                    path = Path(folder) / (name + '.py')
                    path.write_text(source.replace(before, after))
                    compile(path.read_text(), str(path), 'exec')
                    env = dict(os.environ, N71_HELD_HISTORY_SCRIPT=str(path), N71_HELD_HISTORY_MUTATION_CHILD='1')
                    process = subprocess.run([sys.executable, '-B', str(Path(__file__))], env=env,
                                             capture_output=True, text=True, timeout=30)
                    output = process.stdout + process.stderr
                    self.assertNotEqual(process.returncode, 0, name)
                    self.assertIn('AssertionError', output, name)
                    self.assertNotIn('ERROR:', output, name)
                    print('N71_HELD_HISTORY_MUTATION', name, 'AssertionError', flush=True)


if __name__ == '__main__':
    unittest.main()
