"""Publication boundary tests using real disposable Git indexes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKER = Path(__file__).resolve().parents[1] / 'scripts/ci/check-public.py'


class PublicTreeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.environment = dict(os.environ, GIT_CONFIG_NOSYSTEM='1',
                                GIT_CONFIG_GLOBAL=os.devnull)
        self.git('init', '-q')

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.repo), *arguments],
                              env=self.environment, check=True, capture_output=True)

    def stage(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.git('add', '--', name)
        return path

    def check(self):
        return subprocess.run([sys.executable, str(CHECKER), '--repo', str(self.repo)],
                              env=self.environment, capture_output=True, text=True, timeout=15)

    def test_public_sources_and_untracked_private_files_are_accepted(self):
        self.stage('docs/example.md', b'Public reproduction instructions.\n')
        self.stage('scripts/example.py', b'print("example")\n')
        private = self.repo / 'runtime/secret.txt'
        private.parent.mkdir()
        private.write_text('Untracked fixture, not read by guard.')
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PUBLIC_TREE_OK', result.stdout)
        self.assertNotIn('fixture', result.stdout + result.stderr)

    def test_forced_private_paths_and_links_are_rejected(self):
        # Mutation killed: accepting private paths and symlinks in the index.
        for name in ('runtime/data.json', 'keys/client', 'backups/file.txt',
                     'iphone-linux-tools/artifacts/payload.bin'):
            with self.subTest(name=name):
                self.stage(name, b'Synthetic private fixture')
                result = self.check()
                self.assertEqual(result.returncode, 1)
                self.assertIn('PUBLIC_TREE_REJECTED', result.stderr)
                self.git('rm', '-f', '--', name)
        link = self.repo / 'public-link'
        link.symlink_to('outside-secret')
        self.git('add', '--', 'public-link')
        self.assertEqual(self.check().returncode, 1)

    def test_staged_private_key_is_rejected_without_printing_contents(self):
        # Mutations killed: removing key validation or reading only the working tree.
        header = b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----\n'
        sentinel = b'PRIVATE_FIXTURE_MUST_NOT_BE_PRINTED'
        path = self.stage('docs/innocent.md', header + sentinel + b'\n')
        path.write_text('Working tree was cleaned after staging.\n')
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn('private key material', result.stderr)
        self.assertNotIn(sentinel.decode(), result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
