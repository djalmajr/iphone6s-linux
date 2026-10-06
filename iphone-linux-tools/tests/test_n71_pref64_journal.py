"""Keep typed PREF proof and original failure through assignment and cleanup."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_n71_resource_io16 as io16
import test_n71_resource_pref64 as parser

ROOT = Path(__file__).resolve().parents[1]
journal = io16.journal
fixture = io16.fixture
fixture.RESOURCE.n71_resource_pref64 = parser.PREF64
fixture.RESOURCE.n71_resource_readback = parser.READBACK
DATA = dict(captured=1, enabled=1, writes=1)


class Pref64JournalTests(unittest.TestCase):
    setUp = journal.ResourceStageTests.setUp
    execute = journal.ResourceStageTests.execute
    acquired = journal.ResourceStageTests.acquired

    def reports(self, *, include_pref64=True, negative=False):
        record = next(r for r, _ in self.modules if r['module'] == 'n71-pcie-diagnostic.ko')
        record.update(assignment_readback=True, assignment_optional_windows=True,
                      assignment_io16_upper=True, assignment_pref64_disable=True)
        changed = patch.object(journal.STAGE, 'n71_resource_result', fixture.RESOURCE)
        changed.start(); self.addCleanup(changed.stop)
        if negative:
            self.phone.assignment_error = -5

        def report(phone, session, text):
            original = next(row for row in phone.history.splitlines(keepends=True)
                            if 'N71_PCIE_RESOURCE_RESULT ' in row)
            prefix = io16.OPTIONAL + io16.REPORT
            if include_pref64:
                prefix += parser.REPORT.replace('writes=1;', 'writes=0;' if negative else 'writes=1;')
            if negative:
                failed, _ = parser.failed()
                refusal = next(row + '\n' for row in failed.splitlines() if row.startswith('N71_PCIE_SCAN_WRITE_REFUSED '))
                readback = next(row + '\n' for row in failed.splitlines() if row.startswith('N71_PCIE_ASSIGN_READBACK '))
                prefix = refusal + prefix + readback
            else:
                prefix += io16.readback.ABSENT
            prefix = journal.held_fixture.timestamp(prefix, 58)
            phone.history = phone.history.replace(original, prefix + original)
            return int(negative), text.replace(original, prefix + original)
        self.phone.overrides['held-assign'] = report

    def test_positive_checkpoint_reuse_cleanup_preserve_one_typed_write_and_setter(self):
        self.reports()
        code, session, source = self.execute('pref64-assign', self.acquired(), assign=True)
        self.assertEqual(code, 0)
        self.assertEqual(session.result['resource_assignment']['event'].get('pref64_disable'), DATA)
        saved = json.loads((source / 'held-state-private.json').read_text())
        self.assertEqual(saved['result']['resource_assignment']['event'].get('pref64_disable'), DATA)
        self.assertIn(parser.REPORT, (source / (journal.STAGE.PROOF + '-proof-private.log')).read_text())
        code, reused, continuation = self.execute('pref64-reuse', source, assign=True)
        self.assertEqual(code, 0); self.assertTrue(reused.result['resource_assignment_reused'])
        self.assertEqual(self.phone.assignments, 1)
        code, released, _ = self.execute('pref64-release', continuation)
        self.assertEqual(code, 0); self.assertTrue(released.result['cleanup_verified'])
        self.assertEqual(released.result['resource_assignment']['event'].get('pref64_disable'), DATA)

    def test_missing_selected_report_keeps_owners_without_saving_proof(self):
        self.reports(include_pref64=False)
        code, session, source = self.execute('pref64-missing', self.acquired(), assign=True)
        self.assertEqual(code, 1); self.assertIsNone(session.resource_assignment)
        self.assertFalse((source / (journal.STAGE.PROOF + '-proof-private.log')).exists())
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)

    def test_negative_readback_and_cleanup_retry_keep_original_error_and_expectation(self):
        self.reports(negative=True)
        code, session, source = self.execute('pref64-negative', self.acquired(), assign=True)
        self.assertEqual(code, 1)
        assignment = session.result.get('resource_assignment')
        self.assertIsInstance(assignment, dict)
        event = assignment['event']
        self.assertEqual(event.get('pref64_disable'), dict(DATA, writes=0))
        self.assertEqual(event['write_readback']['expected'], 0x1fff1)
        self.assertEqual(event['write_readback']['value'], 0xfff0)
        self.phone.failure = 'extra-once'
        code, pending, continuation = self.execute('pref64-pending', source)
        self.assertEqual(code, 1); self.assertFalse(pending.result['cleanup_verified'])
        code, released, _ = self.execute('pref64-cleanup-retry', continuation)
        self.assertEqual(code, 1); self.assertTrue(released.result['cleanup_verified'])
        self.assertEqual(released.result['resource_assignment']['error'], -5)
        self.assertEqual(released.result['resource_assignment']['event'], event)
        self.assertEqual(self.phone.assignments, 1)

    def test_dispatch_and_selected_requirement_reject_aliases_and_changed_proof(self):
        active = io16.add_reports(fixture.OPEN).replace(io16.REPORT, io16.REPORT + parser.REPORT)
        selected = SimpleNamespace(modules=[(dict(module='n71-pcie-diagnostic.ko', assignment_readback=True,
                                   assignment_optional_windows=True, assignment_io16_upper=True,
                                   assignment_pref64_disable=True), b'')])
        with patch.object(journal.STAGE, 'n71_resource_result', fixture.RESOURCE):
            journal.STAGE.verify_readback(selected, active)
            with self.assertRaises(ValueError):
                journal.STAGE.verify_readback(selected, active.replace(parser.REPORT, ''))
            for value in (1, 'true'):
                selected.modules[0][0]['assignment_pref64_disable'] = value
                with self.assertRaises(ValueError):
                    journal.STAGE.verify_readback(selected, active)
        for value in (1, 'true'):
            with self.assertRaises(ValueError):
                fixture.RESOURCE.event(active, pref64_required=value)
        typed, _ = parser.failed()
        try:
            event = fixture.RESOURCE.event(typed, pref64_required=True)
        except ValueError as error:
            self.fail('Complete typed readback rejected: ' + str(error))
        self.assertEqual(event.get('pref64_disable'), dict(DATA, writes=0))
        self.assertEqual(event['write_readback']['expected'], 0x1fff1)


class Pref64JournalMutationsTests(unittest.TestCase):
    def test_journal_mutations_fail_by_assertion(self):
        variants = (
            ('selected-requirement', 'n71_resource_stage.py', 'N71_RESOURCE_STAGE_SCRIPT',
             "pref64 = records[0].get('assignment_pref64_disable', False)", 'pref64 = False'),
            ('selected-forwarding', 'n71_resource_stage.py', 'N71_RESOURCE_STAGE_SCRIPT',
             'pref64_required=pref64', 'pref64_required=False'),
            ('saved-pref-proof', 'n71_resource_result.py', 'N71_RESOURCE_RESULT_SCRIPT',
             "result['pref64_disable'] = pref64", 'pass'),
            ('readback-context', 'n71_resource_result.py', 'N71_RESOURCE_RESULT_SCRIPT',
             "proof['pref64_disable'] = pref64", 'pass'),
        )
        with tempfile.TemporaryDirectory(prefix='n71-pref64-journal-') as directory:
            for name, module, variable, before, after in variants:
                source = (ROOT / 'scripts/host' / module).read_text()
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
                environment.pop('N71_RESOURCE_STAGE_SCRIPT', None); environment.pop('N71_RESOURCE_RESULT_SCRIPT', None)
                environment[variable] = str(path)
                p = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                    '-p', 'test_n71_pref64_journal.py', '-k', 'Pref64JournalTests'],
                                   cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                output = p.stdout + p.stderr
                self.assertNotEqual(p.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_PREF64_JOURNAL_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
