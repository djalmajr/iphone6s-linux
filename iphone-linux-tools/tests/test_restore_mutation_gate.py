"""Restore proof CLI contract with synthetic external process reports."""
import contextlib
import io
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'Ran 2 tests in 0.1s\n\nOK\n'
FIRST = 'test_interrupted_extraction_and_cleanup_error_allow_explicit_recovery'
SECOND = 'test_full_tmpfs_allows_explicit_recovery'


def result(code, report):
    return subprocess.CompletedProcess([], code, '', report)


def failure(case=FIRST, reason='88 != 255'):
    return (f'FAIL: {case} (test_restore_failure_vm.RestoreFailureTests.{case})\n'
            f'AssertionError: {reason}\nRan 1 test in 0.1s\nFAILED (failures=1)\n')


class RestoreMutationGateTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='restore-proof-policy-')
        self.addCleanup(self.work.cleanup)
        self.project = Path(self.work.name).resolve()
        self.script = self.project / 'tests/run_restore_mutations.py'
        self.script.parent.mkdir()
        shutil.copyfile(ROOT / 'tests/run_restore_mutations.py', self.script)
        shutil.copytree(ROOT / 'scripts/host', self.project / 'scripts/host',
                        ignore=shutil.ignore_patterns('__pycache__'))
        (self.script.parent / 'test_restore_failure_vm.py').write_text('# External fixture is simulated.\n')

    def execute(self, replies, options=None):
        settings = options or {}
        output = io.StringIO()
        code, error = 0, ''
        with mock.patch.object(sys, 'platform', settings.get('platform', 'linux')), \
                mock.patch.object(os, 'geteuid', return_value=settings.get('uid', 0)), \
                mock.patch.dict(os.environ, {'IPHONE_RESTORE_VM_TESTS': settings.get('optin', '1')}), \
                mock.patch.object(subprocess, 'run', side_effect=replies), contextlib.redirect_stdout(output):
            try:
                runpy.run_path(str(self.script), run_name='__main__')
            except SystemExit as stopped:
                code = stopped.code if isinstance(stopped.code, int) else 1
                error = str(stopped.code)
        return code, output.getvalue(), error

    def reports(self, first=None, baseline=None):
        return [baseline if baseline is not None else result(0, BASELINE),
                first if first is not None else result(1, failure()),
                result(1, failure(SECOND, 'CalledProcessError not raised'))]

    def refuse(self, report, code=1):
        status, output, error = self.execute(self.reports(result(code, report)))
        self.assertNotEqual(status, 0, output)
        self.assertIn('outside expected assertion', error)
        self.assertNotIn('Both mutations rejected', output)
        self.assertNotIn('Rejected missing-pre-upload-journal', output)

    def test_infrastructure_errors_with_old_markers_never_count_as_detection(self):
        # Mutation: accepting any nonzero result with a marker restores the #28 false positive.
        self.refuse('ERROR: fixture\nFileNotFoundError: fixture_88\nFAILED (errors=1)\n')
        reports = self.reports()
        reports[2] = result(1, 'ERROR: fixture\nRuntimeError: CalledProcessError not raised\nFAILED (errors=1)\n')
        status, output, error = self.execute(reports)
        self.assertNotEqual(status, 0, output)
        self.assertIn('outside expected assertion', error)
        self.assertNotIn('Both mutations rejected', output)
        self.assertNotIn('Rejected ignored-remote-errors', output)

    def test_mixed_error_or_skip_is_refused(self):
        # Mutation: ignoring ERROR/skip markers accepts an incomplete fixture outcome.
        for extra in ('ERROR: other fixture\n', 'skipped fixture\n'):
            with self.subTest(extra=extra):
                self.refuse(failure() + extra)

    def test_success_code_is_refused_even_with_failure_text(self):
        # Mutation: ignoring the process exit code accepts contradictory success.
        self.refuse(failure(), code=0)

    def test_assertion_text_without_fail_header_is_refused(self):
        # Mutation: dropping the named FAIL header accepts unrelated report text.
        self.refuse('AssertionError: 88 != 255\nRan 1 test in 0.1s\nFAILED (failures=1)\n')

    def test_fail_of_another_case_is_refused(self):
        # Mutation: ignoring the case header accepts another test's assertion.
        self.refuse(failure(SECOND))

    def test_exact_assertion_reason_is_required(self):
        # Mutation: ignoring the exact reason accepts arbitrary text containing 88.
        self.refuse(failure(reason='188 != 255'))

    def test_one_case_and_one_failure_summary_are_required(self):
        # Mutations: dropping execution/failure counts accepts ambiguous or empty proof.
        for report in (failure().replace('Ran 1 test', 'Ran 0 tests'),
                       failure().replace('FAILED (failures=1)', 'FAILED (failures=2)')):
            with self.subTest(report=report):
                self.refuse(report)

    def test_baseline_must_execute_two_cases_and_pass_before_mutations(self):
        # Mutations: dropping baseline exit/count/OK/error checks permits invalid baselines.
        cases = [result(1, BASELINE), result(0, BASELINE.replace('Ran 2 tests', 'Ran 1 test')),
                 result(0, 'Ran 2 tests in 0.1s\n'), result(0, BASELINE + 'ERROR: fixture\n'),
                 result(0, BASELINE + 'skipped fixture\n')]
        for baseline in cases:
            with self.subTest(report=baseline.stderr, code=baseline.returncode):
                status, output, error = self.execute(self.reports(baseline=baseline))
                self.assertNotEqual(status, 0, output)
                self.assertIn('Original restore baseline failed', error)
                self.assertNotIn('baseline passed', output)
                self.assertNotIn('Rejected', output)

    def test_valid_workflow_runs_the_corresponding_case_for_each_mutation(self):
        # Mutation: running the wrong case breaks the otherwise valid proof workflow.
        def external(command, **_options):
            if 'discover' in command:
                return result(0, BASELINE)
            if 'test_restore_failure_vm.RestoreFailureTests.' + FIRST in command:
                return result(1, failure())
            if 'test_restore_failure_vm.RestoreFailureTests.' + SECOND in command:
                return result(1, failure(SECOND, 'CalledProcessError not raised'))
            return result(1, 'ERROR: unexpected fixture command\n')
        status, output, error = self.execute(external)
        self.assertEqual(status, 0, error)
        self.assertIn('Original restore baseline passed', output)
        self.assertIn('Rejected missing-pre-upload-journal', output)
        self.assertIn('Rejected ignored-remote-errors', output)
        self.assertIn('Both mutations rejected', output)

    def test_platform_root_and_explicit_optin_remain_required(self):
        # Mutation: removing opt-in permits native fixture attempts on an unintended host.
        for options in ({'platform': 'darwin'}, {'uid': 1000}, {'optin': '0'}):
            with self.subTest(options=options):
                status, output, error = self.execute(self.reports(), options)
                self.assertNotEqual(status, 0, output)
                self.assertIn('VM/root opt-in', error)
                self.assertNotIn('baseline passed', output)
                self.assertNotIn('Rejected', output)


if __name__ == '__main__':
    unittest.main()
