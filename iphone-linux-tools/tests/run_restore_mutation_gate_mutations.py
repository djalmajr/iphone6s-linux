"""Falsify restore proof acceptance in disposable synthetic CLI fixtures."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'tests/run_restore_mutations.py'
MUTATIONS = [
    ('any-nonzero', 'if not expected_failure(result, mutation):', 'if result.returncode == 0:',
     'test_infrastructure_errors_with_old_markers_never_count_as_detection'),
    ('exit-code', 'result.returncode != 0', 'True', 'test_success_code_is_refused_even_with_failure_text'),
    ('case-header', 'header in lines', 'True', 'test_fail_of_another_case_is_refused'),
    ('assertion-reason', "'AssertionError: ' + mutation['assertion'] in lines", 'True',
     'test_exact_assertion_reason_is_required'),
    ('error-or-skip', "not any(line.startswith('ERROR:') or 'skipped' in line for line in lines)", 'True',
     'test_mixed_error_or_skip_is_refused'),
    ('failure-count', "'FAILED (failures=1)' in lines", 'True',
     'test_one_case_and_one_failure_summary_are_required'),
    ('case-count', "any(line.startswith('Ran 1 test in ') for line in lines)", 'True',
     'test_one_case_and_one_failure_summary_are_required'),
    ('baseline-exit', 'result.returncode == 0', 'True',
     'test_baseline_must_execute_two_cases_and_pass_before_mutations'),
    ('baseline-ok', "'OK' in lines", 'True', 'test_baseline_must_execute_two_cases_and_pass_before_mutations'),
    ('baseline-count', "any(line.startswith('Ran 2 tests in ') for line in lines)", 'True',
     'test_baseline_must_execute_two_cases_and_pass_before_mutations'),
    ('baseline-error', "not any(line.startswith(('FAIL:', 'ERROR:')) or 'skipped' in line for line in lines)",
     'True', 'test_baseline_must_execute_two_cases_and_pass_before_mutations'),
    ('wrong-case', "command += ['test_restore_failure_vm.RestoreFailureTests.' + case, '-v']",
     "command += ['test_restore_failure_vm.RestoreFailureTests.test_full_tmpfs_allows_explicit_recovery', '-v']",
     'test_valid_workflow_runs_the_corresponding_case_for_each_mutation'),
    ('opt-in', "if not (sys.platform == 'linux' and os.geteuid() == 0\n"
     "            and os.environ.get('IPHONE_RESTORE_VM_TESTS') == '1'):", 'if False:',
     'test_platform_root_and_explicit_optin_remain_required'),
]


def main():
    with tempfile.TemporaryDirectory(prefix='restore-proof-mutations-') as folder:
        project = Path(folder).resolve()
        for name in (SOURCE, 'tests/test_restore_mutation_gate.py'):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        shutil.copytree(ROOT / 'scripts/host', project / 'scripts/host',
                        ignore=shutil.ignore_patterns('__pycache__'))
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        def run(test):
            return subprocess.run([sys.executable, '-m', 'unittest', test], cwd=project / 'tests',
                                  env=environment, capture_output=True, text=True, timeout=20)
        baseline = run('test_restore_mutation_gate')
        if baseline.returncode or 'OK' not in baseline.stderr.splitlines():
            raise RuntimeError('Restore proof baseline failed:\n' + baseline.stderr)
        path = project / SOURCE
        original = path.read_text()
        for name, before, after, method in MUTATIONS:
            if original.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            try:
                path.write_text(original.replace(before, after, 1))
                result = run('test_restore_mutation_gate.RestoreMutationGateTests.' + method)
                lines = result.stderr.splitlines()
                if (not result.returncode or not any(line.startswith('FAIL:') for line in lines)
                        or any(line.startswith('ERROR:') or 'skipped=' in line for line in lines)):
                    raise RuntimeError('SURVIVED_OR_INFRA_ERROR ' + name + '\n' + result.stderr)
                print('KILLED ' + name, flush=True)
            finally:
                path.write_text(original)
    print(f'RESTORE_PROOF_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')


if __name__ == '__main__':
    main()
