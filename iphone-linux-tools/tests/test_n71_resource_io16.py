"""Retain the IO16 decision through assignment, reuse and cleanup journals."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_n71_resource_optional as optional
import test_n71_resource_result as fixture
import test_n71_resource_readback as readback
import test_n71_resource_stage as journal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71_resource_io16.py'
SPEC = importlib.util.spec_from_file_location('io16_under_test', os.environ.get('N71_IO16_RESULT_SCRIPT', SOURCE))
IO16 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IO16)
fixture.RESOURCE.n71_resource_io16 = IO16
OPTIONAL = optional.REPORT.replace('io_absent=1', 'io_absent=0').replace('pref_absent=1', 'pref_absent=0').replace('io_noops=2', 'io_noops=0').replace('pref_noops=1', 'pref_noops=0')
REPORT = 'N71_PCIE_IO16_UPPER captured=1 enabled=1 noops=1; temporary upper disable without hardware write\n'
EMPTY = REPORT.replace('captured=1', 'captured=0').replace('enabled=1', 'enabled=0').replace('noops=1', 'noops=0')
DATA = dict(captured=1, enabled=1, noops=1)


def add_reports(text, report=REPORT, window=OPTIONAL):
    result = next(row + '\n' for row in text.splitlines() if row.startswith('N71_PCIE_RESOURCE_RESULT '))
    return text.replace(result, window + report + readback.ABSENT + result)


class IO16ContractTests(unittest.TestCase):
    def invalid(self, text, **options):
        try:
            fixture.RESOURCE.event(text, **options)
        except Exception as error:
            self.assertIsInstance(error, ValueError, 'Invalid proof must return the documented error')
        else:
            self.fail('Invalid IO16 proof accepted')

    def test_success_and_cleanup_preserve_the_same_io16_decision(self):
        active, closed = map(add_reports, (fixture.OPEN, fixture.CLOSED))
        assignment = fixture.RESOURCE.outcome(active)
        self.assertEqual(assignment['event'].get('io16_upper'), DATA)
        self.assertEqual(fixture.RESOURCE.cleanup(closed, assignment)['assignment_error'], 0)
        changed = closed.replace('enabled=1 noops=1', 'enabled=0 noops=0')
        with self.assertRaises(ValueError):
            fixture.RESOURCE.cleanup(changed, assignment)

    def test_negative_capture_and_uncaptured_fields_are_distinct(self):
        active, closed = fixture.failed()
        report = REPORT.replace('noops=1', 'noops=0')
        result = fixture.RESOURCE.outcome(add_reports(active, report))
        self.assertEqual(result['event'].get('io16_upper'), dict(DATA, noops=0))
        self.assertEqual(fixture.RESOURCE.cleanup(add_reports(closed, report), result)['assignment_error'], -13)
        active, _ = fixture.failed(pending=0, claimed=0)
        active = add_reports(active, EMPTY, optional.EMPTY)
        self.assertEqual(fixture.RESOURCE.event(active).get('io16_upper'), dict(captured=0, enabled=0, noops=0))
        self.invalid(active.replace('IO16_UPPER captured=0', 'IO16_UPPER captured=1'))
        self.invalid(active.replace('enabled=0', 'enabled=1'))

    def test_required_unique_complete_known_and_ordered_report(self):
        active = add_reports(fixture.OPEN)
        self.invalid(active.replace(REPORT, ''), io16_required=True)
        self.invalid(active.replace(REPORT, REPORT * 2))
        self.invalid(active.replace(REPORT, REPORT.replace('noops=1', 'noops=')))
        self.invalid(active + 'N71_PCIE_IO16_UNKNOWN extra\n')
        self.invalid(active.replace(OPTIONAL + REPORT, REPORT + OPTIONAL))
        self.invalid(active.replace(REPORT + readback.ABSENT, readback.ABSENT + REPORT))
        self.invalid(active.replace(REPORT, '') + REPORT)

    def test_flags_and_combined_counters_cannot_invent_support_or_writes(self):
        active = add_reports(fixture.OPEN)
        self.invalid(active.replace('enabled=1', 'enabled=0'))
        self.invalid(active.replace('noops=1', 'noops=0'))
        self.invalid(active.replace('noops=1', 'noops=5'))
        unsupported = active.replace('io_absent=0', 'io_absent=1').replace('io_noops=0', 'io_noops=1')
        self.invalid(unsupported)
        combined = active.replace('pref_absent=0', 'pref_absent=1').replace('pref_noops=0', 'pref_noops=3')
        self.invalid(combined.replace('noops=1', 'noops=2'))

    def test_selected_requirement_is_exact_and_legacy_result_stays_unchanged(self):
        record = dict(module='n71-pcie-diagnostic.ko', assignment_readback=True,
                      assignment_optional_windows=True, assignment_io16_upper=True)
        selected = SimpleNamespace(modules=[(record, b'')])
        with patch.object(journal.STAGE, 'n71_resource_result', fixture.RESOURCE):
            journal.STAGE.verify_readback(selected, add_reports(fixture.OPEN))
            with self.assertRaises(ValueError):
                journal.STAGE.verify_readback(selected, add_reports(fixture.OPEN).replace(REPORT, ''))
            for value in (1, 'true'):
                record['assignment_io16_upper'] = value
                with self.assertRaises(ValueError):
                    journal.STAGE.verify_readback(selected, add_reports(fixture.OPEN))
        for value in (1, 'true'):
            self.invalid(add_reports(fixture.OPEN), io16_required=value)
        self.assertNotIn('io16_upper', fixture.RESOURCE.event(fixture.OPEN))
        self.assertNotIn('io16_upper', fixture.RESOURCE.event(optional.add_reports(fixture.OPEN)))
        self.assertIsNone(fixture.RESOURCE.event(fixture.fixture.OPEN, io16_required=True))
        self.invalid(fixture.fixture.OPEN + REPORT)


class IO16JournalTests(unittest.TestCase):
    setUp = journal.ResourceStageTests.setUp
    execute = journal.ResourceStageTests.execute
    acquired = journal.ResourceStageTests.acquired

    def reports(self, *, include_io16=True):
        record = next(r for r, _ in self.modules if r['module'] == 'n71-pcie-diagnostic.ko')
        record.update(assignment_readback=True, assignment_optional_windows=True, assignment_io16_upper=True)
        changed = patch.object(journal.STAGE, 'n71_resource_result', fixture.RESOURCE)
        changed.start(); self.addCleanup(changed.stop)

        def report(phone, session, text):
            original = next(row for row in phone.history.splitlines(keepends=True)
                            if 'N71_PCIE_RESOURCE_RESULT ' in row)
            prefix = journal.held_fixture.timestamp(OPTIONAL + (REPORT if include_io16 else '') + readback.ABSENT, 58)
            phone.history = phone.history.replace(original, prefix + original)
            return 0, text.replace(original, prefix + original)
        self.phone.overrides['held-assign'] = report

    def test_checkpoint_reuse_cleanup_keep_measured_io16_and_one_setter(self):
        self.reports()
        code, _, source = self.execute('io16-assign', self.acquired(), assign=True)
        self.assertEqual(code, 0)
        state = json.loads((source / 'held-state-private.json').read_text())
        self.assertEqual(state['result']['resource_assignment']['event'].get('io16_upper'), DATA)
        self.assertIn(REPORT, (source / (journal.STAGE.PROOF + '-proof-private.log')).read_text())
        code, reused, continuation = self.execute('io16-reuse', source, assign=True)
        self.assertEqual(code, 0); self.assertTrue(reused.result['resource_assignment_reused'])
        self.assertEqual(self.phone.assignments, 1)
        code, released, _ = self.execute('io16-release', continuation)
        self.assertEqual(code, 0); self.assertTrue(released.result['cleanup_verified'])
        self.assertEqual(released.result['resource_assignment']['event'].get('io16_upper'), DATA)

    def test_missing_io16_report_keeps_owners_and_does_not_save_proof(self):
        self.reports(include_io16=False)
        code, session, source = self.execute('io16-missing', self.acquired(), assign=True)
        self.assertEqual(code, 1); self.assertIsNone(session.resource_assignment)
        self.assertFalse((source / (journal.STAGE.PROOF + '-proof-private.log')).exists())
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)


class IO16MutationTests(unittest.TestCase):
    def test_guards_and_retained_fields_die_by_assertion(self):
        variants = (
            ('required-lost', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT', 'not required or result is None', 'True'),
            ('unknown-accepted', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT',
             "text.count('N71_PCIE_IO16_')", "text.count('N71_PCIE_IO16_UPPER ')"),
            ('optional-order-lost', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT',
             "< text.index('N71_PCIE_OPTIONAL_WINDOWS ') < row.start()", '< row.start()'),
            ('readback-order-lost', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT',
             "< text.index('N71_PCIE_ASSIGN_READBACK ') < text.index('N71_PCIE_RESOURCE_RESULT ')",
             "< text.index('N71_PCIE_RESOURCE_RESULT ')"),
            ('capture-lost', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT', "data['captured'] == result['pending']", 'True'),
            ('uncaptured-invented', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT', 'not any(data.values())', 'True'),
            ('disabled-noops', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT', "data['enabled'] or data['noops'] == 0", 'True'),
            ('absent-support', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT', "not data['enabled'] or optional['io_absent'] == 0", 'True'),
            ('combined-budget-lost', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT',
             "<= result['attempts'] - result['writes']", '<= 64'),
            ('positive-noop-lost', 'n71_resource_io16.py', 'N71_IO16_RESULT_SCRIPT', "not data['enabled'] or data['noops'] > 0", 'True'),
            ('selected-lost', 'n71_resource_stage.py', 'N71_RESOURCE_STAGE_SCRIPT',
             "io16 = records[0].get('assignment_io16_upper', False)", 'io16 = False'),
            ('saved-lost', 'n71_resource_result.py', 'N71_RESOURCE_RESULT_SCRIPT', "result['io16_upper'] = io16", 'pass'),
        )
        with tempfile.TemporaryDirectory(prefix='n71-io16-result-') as directory:
            for name, module, variable, old, new in variants:
                source = (ROOT / 'scripts/host' / module).read_text()
                self.assertEqual(source.count(old), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(old, new, 1))
                compile(path.read_text(), str(path), 'exec')
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **{variable: str(path)})
                p = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                    '-p', 'test_n71_resource_io16.py', '-k', 'IO16ContractTests'],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
                output = p.stdout + p.stderr
                self.assertNotEqual(p.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output); self.assertNotIn('ERROR:', output, name + output)
                print('N71_IO16_RESULT_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
