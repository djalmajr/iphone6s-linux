"""Hosted Linux crash policy using only mocked sysctl/sudo, never the host kernel."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/ci/isolate-native-crashes.sh'
MUTATIONS = (
    ('ignore-github', '"${GITHUB_ACTIONS:-}" != true', '1 != 1'),
    ('ignore-linux', '"${RUNNER_OS:-}" != Linux', '1 != 1'),
    ('ignore-hosted', '"${RUNNER_ENVIRONMENT:-}" != github-hosted', '1 != 1'),
    ('ignore-arguments', '(($# != 0))', '((0))'),
    ('skip-write', 'sudo -n sysctl -q -w kernel.core_pattern=core', ':'),
    ('ignore-write-readback', '[[ "$core_handler_after" == core ]]', '[[ 1 == 1 ]]'),
    ('ignore-file-change', '[[ "$core_handler_after" == "$core_handler_before" ]]', '[[ 1 == 1 ]]'),
    ('ignore-command-error', 'set -euo pipefail', 'set -uo pipefail'),
)
MOCK = '''import json,os,sys
from pathlib import Path
root=Path(os.environ['N71_CI_FIXTURE_ROOT'])
name=Path(sys.argv[0]).name
mode=os.environ.get('N71_CI_FIXTURE_MODE','')
with (root/'calls').open('a') as stream: stream.write(json.dumps([name]+sys.argv[1:])+'\\n')
if name=='sysctl':
    assert sys.argv[1:]==['-n','kernel.core_pattern']
    if mode=='read-failure': raise SystemExit(7)
    if mode=='file-changed' and len((root/'calls').read_text().splitlines())>1:
        (root/'handler').write_text('core.other')
    print((root/'handler').read_text())
elif name=='sudo':
    assert sys.argv[1:]==['-n','sysctl','-q','-w','kernel.core_pattern=core']
    if mode=='write-failure': raise SystemExit(8)
    if mode!='no-effect': (root/'handler').write_text('core.other' if mode=='wrong-file' else 'core')
else: raise AssertionError('Unexpected mock command')
'''


class NativeCrashPolicyTests(unittest.TestCase):
    def invoke(self, script, *, pattern='|mock crash handler', mode='', overrides=None, arguments=()):
        with tempfile.TemporaryDirectory(prefix='native-crash-policy-') as directory:
            root = Path(directory)
            (root / 'handler').write_text(pattern)
            (root / 'calls').write_text('')
            for name in ('sysctl', 'sudo'):
                path = root / name
                path.write_text('#!' + sys.executable + '\n' + MOCK)
                path.chmod(0o700)
            environment = dict(os.environ, GITHUB_ACTIONS='true', RUNNER_OS='Linux',
                               RUNNER_ENVIRONMENT='github-hosted',
                               N71_CI_FIXTURE_ROOT=str(root), N71_CI_FIXTURE_MODE=mode)
            environment['PATH'] = str(root) + os.pathsep + os.environ['PATH']
            environment.update(overrides or {})
            result = subprocess.run(['bash', str(script), *arguments], env=environment,
                                    capture_output=True, text=True, timeout=10)
            calls = [json.loads(line) for line in (root / 'calls').read_text().splitlines()]
            return result, calls, (root / 'handler').read_text()

    def assert_contract(self, script):
        cases = 0
        result, calls, handler = self.invoke(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(handler, 'core')
        self.assertEqual([call[0] for call in calls], ['sysctl', 'sudo', 'sysctl'])
        self.assertIn('CI_NATIVE_CRASH_ISOLATION_OK', result.stdout)
        cases += 1
        result, calls, handler = self.invoke(script, pattern='core.%p')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(handler, 'core.%p')
        self.assertEqual([call[0] for call in calls], ['sysctl', 'sysctl'])
        cases += 1
        # Mutants must not admit local/macOS/Windows/self-hosted environments.
        for key, values in {'GITHUB_ACTIONS': ('', 'false'),
                            'RUNNER_OS': ('', 'macOS', 'Windows'),
                            'RUNNER_ENVIRONMENT': ('', 'self-hosted')}.items():
            for value in values:
                result, calls, handler = self.invoke(script, overrides={key: value})
                self.assertEqual(result.returncode, 2)
                self.assertEqual(calls, [])
                self.assertEqual(handler, '|mock crash handler')
                cases += 1
        result, calls, _ = self.invoke(script, arguments=('unexpected',))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [])
        cases += 1
        # Mutants must not report success after a failed read/write or absent effect.
        for mode in ('read-failure', 'write-failure', 'no-effect', 'wrong-file', 'file-changed'):
            pattern = 'core.%p' if mode == 'file-changed' else '|mock crash handler'
            result, calls, _ = self.invoke(script, pattern=pattern, mode=mode)
            self.assertNotEqual(result.returncode, 0, mode)
            self.assertNotIn('CI_NATIVE_CRASH_ISOLATION_OK', result.stdout)
            if mode == 'read-failure':
                self.assertEqual([call[0] for call in calls], ['sysctl'])
            elif mode == 'file-changed':
                self.assertEqual([call[0] for call in calls], ['sysctl', 'sysctl'])
            else:
                self.assertEqual(calls[1][0], 'sudo')
            cases += 1
        self.assertEqual(cases, 15)
        return cases

    def test_hosted_policy_guards_effects_and_refusals(self):
        result = subprocess.run(['bash', '-n', str(SCRIPT)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        print('CI_NATIVE_CRASH_POLICY_OK cases=' + str(self.assert_contract(SCRIPT)), flush=True)

    def test_syntax_valid_source_mutations_fail_by_assertion(self):
        source = SCRIPT.read_text()
        with tempfile.TemporaryDirectory(prefix='native-crash-mutants-') as directory:
            script = Path(directory) / 'policy.sh'
            for name, before, after in MUTATIONS:
                self.assertEqual(source.count(before), 1, name)
                script.write_text(source.replace(before, after, 1))
                compiled = subprocess.run(['bash', '-n', str(script)], capture_output=True,
                                          text=True, timeout=10)
                self.assertEqual(compiled.returncode, 0, name + compiled.stderr)
                with self.assertRaises(AssertionError, msg=name):
                    self.assert_contract(script)
                print('CI_NATIVE_CRASH_POLICY_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
