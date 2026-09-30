"""Run transport CLIs against synthetic profiles and an owned SSH executable."""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import unittest
import test_device_profile as fixtures

SSH_STUB = r'''import json,sys
from pathlib import Path
base = Path(__file__).resolve().parent
with (base / 'calls.jsonl').open('a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\n')
if 'tar -czf -' in sys.argv[-1]:
    sys.stdout.buffer.write((base / 'incoming.tar.gz').read_bytes())
'''


class ProfileTransportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DeviceProfileTests('test_valid_profile_and_effective_ssh_identity')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.base = self.fixture.base
        self.project = self.base / 'project'
        self.host = self.project / 'scripts/host'
        shutil.copytree(fixtures.ROOT / 'scripts/host', self.host,
                        ignore=shutil.ignore_patterns('__pycache__'))
        self.commands = self.base / 'commands'
        self.commands.mkdir()
        stub = self.commands / 'ssh'
        stub.write_text('#!' + sys.executable + '\n' + SSH_STUB)
        stub.chmod(0o700)
        with tarfile.open(self.commands / 'incoming.tar.gz', 'w:gz') as archive:
            content = b'profile selected snapshot\n'
            member = tarfile.TarInfo('srv/data/state.txt')
            member.size, member.mode = len(content), 0o640
            archive.addfile(member, io.BytesIO(content))
        self.environment = dict(self.fixture.environment,
                                PATH=str(self.commands) + os.pathsep + os.environ['PATH'])

    def run_cli(self, arguments):
        return subprocess.run([sys.executable, str(self.host / arguments[0]), *arguments[1:]],
                              env=self.environment, capture_output=True, text=True, timeout=15)

    def calls(self):
        path = self.commands / 'calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_snapshot_lan_and_dns_select_same_identity_without_default_keys(self):
        # Mutations killed: bypassing selected LAN/snapshot transport or using default DNS identity paths.
        for arguments in (['persist.py', 'backup'], ['lan.py', '--bind', '127.0.0.1'],
                          ['dns.py', 'status']):
            result = self.run_cli(arguments)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.run_cli(['dns.py', 'lan', '--bind', '127.0.0.1', '--allow', '127.0.0.1'])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('nenhum proxy publicado', result.stderr)
        self.assertNotIn('DNS_LAN_READY', result.stdout)
        calls = self.calls()
        self.assertEqual(len(calls), 5)
        for call in calls:
            self.assertIn('-i', call)
            self.assertEqual(call[call.index('-i') + 1], str(self.base / 'client'))
            self.assertIn('UserKnownHostsFile=' + str(self.base / 'known_hosts'), call)
            self.assertIn('HostKeyAlias=candidate-test', call)
            self.assertIn('GlobalKnownHostsFile=/dev/null', call)
            self.assertIn('StrictHostKeyChecking=yes', call)
            self.assertIn('ForwardAgent=no', call)
            self.assertIn('root@172.16.42.1', call)
        archives = list((self.project / 'backups').glob('*/files.tar.gz'))
        self.assertEqual(len(archives), 1)
        with tarfile.open(archives[0], 'r:gz') as archive:
            self.assertEqual(archive.extractfile('srv/data/state.txt').read(), b'profile selected snapshot\n')
            self.assertEqual(archive.getmember('srv/data/state.txt').mode, 0o640)
        self.assertFalse((self.project / 'keys').exists())

    def test_invalid_profile_aborts_before_ssh_or_snapshot_publication(self):
        # Mutation killed: treating an explicit empty profile as the default deployment.
        for selection in ('', str(self.base / 'missing.json')):
            self.environment['IPHONE_LINUX_PROFILE'] = selection
            for arguments in (['persist.py', 'backup'], ['lan.py', '--bind', '127.0.0.1'],
                              ['dns.py', 'status'], ['dns.py', 'lan', '--bind', '127.0.0.1',
                                                     '--allow', '127.0.0.1']):
                with self.subTest(selection=selection, arguments=arguments):
                    result = self.run_cli(arguments)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
                    self.assertNotIn('DNS_LAN_READY', result.stdout)
                    self.assertEqual(self.calls(), [])
                    self.assertFalse((self.project / 'backups').exists())


if __name__ == '__main__':
    unittest.main()
