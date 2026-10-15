"""Retain optional-window decisions in assignment, reuse and cleanup proofs."""
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
import test_n71_resource_result as fixture
import test_n71_resource_readback as readback
import test_n71_resource_stage as journal

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71_resource_optional.py'
SPEC = importlib.util.spec_from_file_location('optional_under_test', os.environ.get('N71_OPTIONAL_RESULT_SCRIPT', SOURCE))
OPTIONAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OPTIONAL)
fixture.RESOURCE.n71_resource_optional = OPTIONAL
REPORT = ('N71_PCIE_OPTIONAL_WINDOWS captured=1 io_absent=1 pref_absent=1 io_noops=2 pref_noops=1; '
          'absent ranges are emulated without hardware writes\n')
EMPTY = REPORT.replace('captured=1', 'captured=0').replace('io_absent=1', 'io_absent=0').replace('pref_absent=1', 'pref_absent=0').replace('io_noops=2', 'io_noops=0').replace('pref_noops=1', 'pref_noops=0')
DATA = dict(captured=1, io_absent=1, pref_absent=1, io_noops=2, pref_noops=1)


def add_reports(text, report=REPORT):
    result = next(row + '\n' for row in text.splitlines() if row.startswith('N71_PCIE_RESOURCE_RESULT '))
    return text.replace(result, report + readback.ABSENT + result)


class OptionalContractTests(unittest.TestCase):
    def test_optional_decision_survives_success_and_cleanup(self):
        active, closed = map(add_reports, (fixture.OPEN, fixture.CLOSED))
        assignment = fixture.RESOURCE.outcome(active)
        self.assertEqual(assignment['event'].get('optional_windows'), DATA)
        self.assertEqual(fixture.RESOURCE.cleanup(closed, assignment)['assignment_error'], 0)
        for report in (REPORT.replace('io_noops=2', 'io_noops=1'), EMPTY):
            with self.assertRaises(ValueError):
                fixture.RESOURCE.cleanup(closed.replace(REPORT, report), assignment)

    def test_negative_and_uncaptured_ranges_keep_distinct_proofs(self):
        for pending, claimed in ((1, 1), (1, 0), (0, 0)):
            active, closed = fixture.failed(pending=pending, claimed=claimed)
            report = REPORT.replace('io_noops=2', 'io_noops=0').replace('pref_noops=1', 'pref_noops=0') if pending else EMPTY
            active, closed = (add_reports(t, report) for t in (active, closed))
            result = fixture.RESOURCE.outcome(active)
            self.assertEqual(result['event'].get('optional_windows', {}).get('captured'), pending)
            self.assertEqual(fixture.RESOURCE.cleanup(closed, result)['assignment_error'], -13)
            if not pending:
                with self.assertRaises(ValueError):
                    fixture.RESOURCE.event(active.replace('captured=0', 'captured=1'))
                with self.assertRaises(ValueError):
                    fixture.RESOURCE.event(active.replace('io_absent=0', 'io_absent=1'))

    def test_records_are_unique_complete_and_ordered(self):
        active = add_reports(fixture.OPEN)
        for text in (active + REPORT, active.replace(REPORT, REPORT.rstrip() + ' garbage\n'),
                     active.replace('N71_PCIE_OPTIONAL_WINDOWS', 'N71_PCIE_OPTIONAL_UNKNOWN'),
                     REPORT + active.replace(REPORT, ''), active.replace(REPORT, '') + REPORT,
                     active.replace(REPORT + readback.ABSENT, readback.ABSENT + REPORT),
                     active.replace(readback.ABSENT, '')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                fixture.RESOURCE.event(text)
        with self.assertRaises(ValueError):
            fixture.RESOURCE.event(REPORT)

    def test_flags_and_counters_are_bounded_by_the_actual_attempts(self):
        active = add_reports(fixture.OPEN)
        for old, new in (('captured=1', 'captured=0'), ('io_absent=1', 'io_absent=0'),
                         ('pref_absent=1', 'pref_absent=0'), ('io_noops=2', 'io_noops=4'),
                         ('io_noops=2', 'io_noops=0'), ('pref_noops=1', 'pref_noops=0')):
            with self.subTest(old=old, new=new), self.assertRaises(ValueError):
                fixture.RESOURCE.event(active.replace(old, new))

    def test_selected_contract_requires_the_report_and_legacy_stays_unchanged(self):
        selected = SimpleNamespace(modules=[({'module': 'n71-pcie-diagnostic.ko',
                         'assignment_readback': True, 'assignment_optional_windows': True}, b'')])
        with patch.object(journal.STAGE, 'n71_resource_result', fixture.RESOURCE):
            journal.STAGE.verify_readback(selected, add_reports(fixture.OPEN))
            with self.assertRaises(ValueError):
                journal.STAGE.verify_readback(selected, add_reports(fixture.OPEN).replace(REPORT, ''))
        self.assertNotIn('optional_windows', fixture.RESOURCE.event(fixture.OPEN))
        for value in (1, 'true'):
            with self.assertRaises(ValueError):
                fixture.RESOURCE.event(add_reports(fixture.OPEN), optional_required=value)
        with self.assertRaises(ValueError):
            fixture.RESOURCE.event(fixture.OPEN, optional_required=True)


class OptionalJournalTests(unittest.TestCase):
    setUp = journal.ResourceStageTests.setUp
    execute = journal.ResourceStageTests.execute
    acquired = journal.ResourceStageTests.acquired

    def reports(self, *, include_optional=True):
        record = next(r for r, _ in self.modules if r['module'] == 'n71-pcie-diagnostic.ko')
        record.update(assignment_readback=True, assignment_optional_windows=True)
        changed = patch.object(journal.STAGE, 'n71_resource_result', fixture.RESOURCE)
        changed.start(); self.addCleanup(changed.stop)

        def report(phone, session, text):
            original = next(row for row in phone.history.splitlines(keepends=True)
                            if 'N71_PCIE_RESOURCE_RESULT ' in row)
            prefix = journal.held_fixture.timestamp((REPORT if include_optional else '') + readback.ABSENT, 58)
            phone.history = phone.history.replace(original, prefix + original)
            return 0, text.replace(original, prefix + original)
        self.phone.overrides['held-assign'] = report

    def test_checkpoint_reuse_and_cleanup_keep_the_optional_fields(self):
        self.reports()
        code, assigned, source = self.execute('optional-assign', self.acquired(), assign=True)
        self.assertEqual(code, 0)
        state = json.loads((source / 'held-state-private.json').read_text())
        measured = state['result']['resource_assignment']['event'].get('optional_windows')
        self.assertEqual(measured, DATA)
        self.assertIn(REPORT, (source / (journal.STAGE.PROOF + '-proof-private.log')).read_text())
        code, reused, continuation = self.execute('optional-reuse', source, assign=True)
        self.assertEqual(code, 0); self.assertTrue(reused.result['resource_assignment_reused'])
        self.assertEqual(self.phone.assignments, 1)
        code, released, _ = self.execute('optional-release', continuation)
        self.assertEqual(code, 0); self.assertTrue(released.result['cleanup_verified'])
        self.assertEqual(released.result['resource_assignment']['event'].get('optional_windows'), DATA)

    def test_missing_optional_report_cannot_save_a_proof(self):
        self.reports(include_optional=False)
        code, session, source = self.execute('optional-missing', self.acquired(), assign=True)
        self.assertEqual(code, 1); self.assertIsNone(session.resource_assignment)
        self.assertFalse((source / (journal.STAGE.PROOF + '-proof-private.log')).exists())
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)


class OptionalMutationTests(unittest.TestCase):
    def test_guards_and_saved_fields_fail_by_assertion(self):
        variants = (
            ('required-lost', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT',
             'not required or result is None', 'True'),
            ('unknown-accepted', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT',
             "text.count('N71_PCIE_OPTIONAL_')", "text.count('N71_PCIE_OPTIONAL_WINDOWS ')"),
            ('order-lost', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT',
             "< text.index('N71_PCIE_ASSIGN_READBACK ') < text.index('N71_PCIE_RESOURCE_RESULT ')",
             "< text.index('N71_PCIE_RESOURCE_RESULT ')"),
            ('capture-lost', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT',
             "data['captured'] == result['pending']", 'True'),
            ('uncaptured-invented', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT', 'not any(data.values())', 'True'),
            ('io-support-lost', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT',
             "data['io_absent'] or data['io_noops'] == 0", 'True'),
            ('pref-support-lost', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT',
             "data['pref_absent'] or data['pref_noops'] == 0", 'True'),
            ('budget-lost', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT',
             "data['io_noops'] + data['pref_noops'] <= result['attempts'] - result['writes']", 'True'),
            ('io-disable-lost', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT',
             "not data['io_absent'] or data['io_noops'] > 0", 'True'),
            ('pref-disable-lost', 'n71_resource_optional.py', 'N71_OPTIONAL_RESULT_SCRIPT',
             "not data['pref_absent'] or data['pref_noops'] > 0", 'True'),
            ('selected-lost', 'n71_resource_stage.py', 'N71_RESOURCE_STAGE_SCRIPT',
             "optional = records[0].get('assignment_optional_windows', False)", 'optional = False'),
            ('saved-lost', 'n71_resource_result.py', 'N71_RESOURCE_RESULT_SCRIPT',
             "result['optional_windows'] = optional", 'pass'),
        )
        with tempfile.TemporaryDirectory(prefix='n71-optional-result-') as directory:
            for name, module, variable, old, new in variants:
                source = (ROOT / 'scripts/host' / module).read_text()
                self.assertEqual(source.count(old), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(old, new, 1))
                compile(path.read_text(), str(path), 'exec')
                env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **{variable: str(path)})
                p = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                    '-p', 'test_n71_resource_optional.py', '-k', 'OptionalContractTests'],
                                   cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
                output = p.stdout + p.stderr
                self.assertNotEqual(p.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output); self.assertNotIn('ERROR:', output, name + output)
                print('N71_OPTIONAL_RESULT_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
