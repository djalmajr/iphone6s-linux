"""Falsify DNS proof acceptance using disposable CLI process fixtures."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'tests/run_dns_server_mutations.py'
MUTATIONS = [
    ('any-nonzero', 'if not expected_assertion(result, name):',
     "if result.returncode == 0 or 'skipped' in result.stderr:",
     'test_infrastructure_error_never_counts_as_detection'),
    ('exit-code', 'result.returncode != 0', 'True', 'test_success_exit_never_counts_as_detection'),
    ('fail-header', "any(line.startswith('FAIL:') for line in lines)", 'True',
     'test_reason_text_without_failed_test_is_refused'),
    ('error-or-skip', "not any(line.startswith('ERROR:') or 'skipped' in line for line in lines)", 'True',
     'test_skip_or_mixed_error_is_not_mutation_evidence'),
    ('reason', "any(line.startswith('AssertionError: ' + message)\n"
     '                    for line in lines for message in EXPECTED_FAILURES[name])', 'True',
     'test_failure_of_another_rule_is_refused'),
    ('baseline-exit', 'result.returncode == 0', 'True', 'test_baseline_must_run_one_test_and_pass'),
    ('baseline-ok', "'OK' in lines", 'True', 'test_baseline_must_run_one_test_and_pass'),
    ('baseline-count', "any(line.startswith('Ran 1 test in ') for line in lines)", 'True',
     'test_baseline_must_run_one_test_and_pass'),
    ('baseline-error', "not any(line.startswith(('FAIL:', 'ERROR:')) or 'skipped' in line for line in lines)",
     'True', 'test_baseline_must_run_one_test_and_pass'),
    ('valid-result', 'result.returncode != 0', 'False',
     'test_only_corresponding_assertions_are_accepted_for_every_mutation'),
    ('opt-in', "if not (sys.platform == 'linux' and os.geteuid() == 0 and\n"
     "            os.environ.get('IPHONE_DNS_VM_TESTS') == '1'):", 'if False:',
     'test_platform_root_and_explicit_optin_remain_required'),
]


def main():
    with tempfile.TemporaryDirectory(prefix='dns-proof-mutations-') as folder:
        project = Path(folder).resolve()
        for name in (SOURCE, 'tests/test_dns_mutation_gate.py', 'phone/dns/manage-dns.sh'):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        def run(test):
            return subprocess.run([sys.executable, '-m', 'unittest', test], cwd=project / 'tests',
                                  env=environment, capture_output=True, text=True, timeout=15)
        baseline = run('test_dns_mutation_gate')
        if baseline.returncode or 'OK' not in baseline.stderr.splitlines():
            raise RuntimeError('DNS proof baseline failed:\n' + baseline.stderr)
        path = project / SOURCE
        original = path.read_text()
        for name, before, after, method in MUTATIONS:
            if original.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            try:
                path.write_text(original.replace(before, after, 1))
                result = run('test_dns_mutation_gate.DnsMutationGateTests.' + method)
                lines = result.stderr.splitlines()
                if (not result.returncode or not any(line.startswith('FAIL:') for line in lines)
                        or any(line.startswith('ERROR:') or 'skipped=' in line for line in lines)):
                    raise RuntimeError('SURVIVED_OR_INFRA_ERROR ' + name + '\n' + result.stderr)
                print('KILLED ' + name, flush=True)
            finally:
                path.write_text(original)
    print(f'DNS_PROOF_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')


if __name__ == '__main__':
    main()
