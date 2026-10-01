"""Runner CLI proof policy with synthetic external fixture process outcomes."""
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
SOURCE = ROOT / 'tests/run_dns_server_mutations.py'
BASELINE = 'Ran 1 test in 0.1s\n\nOK\n'
REASONS = {
    'kernel-bind': 'Unexpected kernel bind: wildcard',
    'root-user': 'DNS retained root privileges',
    'external-upstream': 'Unexpected negative DNS behavior: SERVFAIL',
    'stale-pid': 'Stale start-time record signaled process',
    'foreign-executable': 'Foreign executable received signal',
}


def result(code, report):
    return subprocess.CompletedProcess([], code, '', report)


def failure(reason):
    return 'FAIL: test_real_dns\nAssertionError: ' + reason + '\nFAILED (failures=1)\n'


class DnsMutationGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='dns-runner-policy-')
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name).resolve()
        self.script = self.project / 'tests/run_dns_server_mutations.py'
        self.script.parent.mkdir()
        shutil.copyfile(SOURCE, self.script)
        (self.script.parent / 'test_dns_server_vm.py').write_text('# External fixture is simulated.\n')
        target = self.project / 'phone/dns/manage-dns.sh'
        target.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'phone/dns/manage-dns.sh', target)

    def execute(self, replies, name='kernel-bind', platform='linux', uid=0, optin='1'):
        output = io.StringIO()
        code, error = 0, ''
        with mock.patch.object(sys, 'platform', platform), mock.patch.object(os, 'geteuid', return_value=uid), \
                mock.patch.dict(os.environ, {'IPHONE_DNS_VM_TESTS': optin}), \
                mock.patch.object(sys, 'argv', [str(self.script), name]), \
                mock.patch.object(subprocess, 'run', side_effect=replies), contextlib.redirect_stdout(output):
            try:
                runpy.run_path(str(self.script), run_name='__main__')
            except SystemExit as stopped:
                code = stopped.code if isinstance(stopped.code, int) else 1
                error = str(stopped.code)
        return code, output.getvalue(), error

    def refuse(self, report, code=1):
        status, output, error = self.execute([result(0, BASELINE), result(code, report)])
        self.assertNotEqual(status, 0, output)
        self.assertIn('outside expected assertion', error)
        self.assertNotIn('Rejected', output)

    def test_infrastructure_error_never_counts_as_detection(self):
        # Mutation: accepting any nonzero fixture outcome restores the #27 false positive.
        self.refuse('ERROR: test_real_dns\nFileNotFoundError: synthetic dependency\nFAILED (errors=1)\n')

    def test_skip_or_mixed_error_is_not_mutation_evidence(self):
        # Mutation: ignoring error/skip markers accepts an incomplete fixture report.
        report = failure(REASONS['kernel-bind'])
        for extra in ('ERROR: another test\n', 'skipped fixture\n'):
            with self.subTest(extra=extra):
                self.refuse(report + extra)

    def test_success_exit_never_counts_as_detection(self):
        # Mutation: ignoring the fixture exit code accepts a contradictory success report.
        self.refuse(failure(REASONS['kernel-bind']), code=0)

    def test_failure_of_another_rule_is_refused(self):
        # Mutation: omitting reason matching accepts an unrelated assertion.
        self.refuse(failure('Start was not idempotent'))

    def test_reason_text_without_failed_test_is_refused(self):
        # Mutation: dropping FAIL header validation accepts arbitrary stderr text.
        self.refuse('AssertionError: ' + REASONS['kernel-bind'] + '\n')

    def test_baseline_must_run_one_test_and_pass(self):
        # Mutations: dropping baseline exit/summary/status checks accepts invalid baselines.
        cases = [result(1, BASELINE), result(0, 'Ran 0 tests in 0.1s\nOK\n'),
                 result(0, 'Ran 1 test in 0.1s\n'), result(0, BASELINE + 'ERROR: another test\n'),
                 result(0, BASELINE + 'skipped fixture\n')]
        for baseline in cases:
            with self.subTest(report=baseline.stderr, code=baseline.returncode):
                status, output, error = self.execute([baseline, result(1, failure(REASONS['kernel-bind']))])
                self.assertNotEqual(status, 0, output)
                self.assertIn('Original baseline failed', error)
                self.assertNotIn('baseline passed', output)
                self.assertNotIn('Rejected', output)

    def test_only_corresponding_assertions_are_accepted_for_every_mutation(self):
        # Mutation: rejecting valid nonzero expected failures breaks the proof workflow.
        for name, reason in REASONS.items():
            with self.subTest(name=name):
                status, output, error = self.execute([result(0, BASELINE), result(1, failure(reason))], name=name)
                self.assertEqual(status, 0, error)
                self.assertIn('Original DNS server baseline passed', output)
                self.assertIn('Rejected ' + name, output)

    def test_platform_root_and_explicit_optin_remain_required(self):
        # Mutation: dropping the opt-in gate permits fixture attempts on the Mac.
        for options in ({'platform': 'darwin'}, {'uid': 1000}, {'optin': '0'}):
            with self.subTest(options=options):
                status, output, error = self.execute(
                    [result(0, BASELINE), result(1, failure(REASONS['kernel-bind']))], **options)
                self.assertNotEqual(status, 0, output)
                self.assertIn('VM/root opt-in required', error)
                self.assertNotIn('baseline passed', output)
                self.assertNotIn('Rejected', output)


if __name__ == '__main__':
    unittest.main()
