"""Real Git/archive ownership; fixture selector is never production proof."""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_runtime_source_snapshot as SNAPSHOT
SOURCE = ROOT / 'scripts/host/n71_runtime_source_snapshot.py'


class SourceSnapshotTests(unittest.TestCase):
    subject = SNAPSHOT

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve()
        self.root = self.repo / 'project'
        (self.root / 'runtime').mkdir(parents=True, mode=0o700)
        self.proof = json.loads((ROOT / SNAPSHOT.PROOF).read_text())
        for name in self.proof['inputs']:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = ('fixture:' + name).encode()
            path.write_bytes(raw)
            self.proof['inputs'][name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        (self.root / SNAPSHOT.PROOF).parent.mkdir(parents=True, exist_ok=True)
        (self.root / SNAPSHOT.PROOF).write_text(json.dumps(self.proof))
        script = self.root / 'scripts/host/n71_driver_runtime_build.py'
        script.parent.mkdir(parents=True)
        script.write_text("raise RuntimeError('Archived scripts must remain data')\n")
        self.git('init', '-q')
        self.git('add', 'project/phone', 'project/tests', 'project/docs', 'project/scripts')
        self.commit()
        self.output = self.root / 'runtime/snapshot'

    def git(self, *arguments):
        return subprocess.check_output(['git', *arguments], cwd=self.repo, stderr=subprocess.PIPE, text=True).strip()

    def commit(self):
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            'commit', '-qm', 'fixture')
        self.sha = self.git('rev-parse', 'HEAD')

    def create(self):
        with patch.object(SNAPSHOT.build, 'select', return_value={'diagnostics': ['fixture'], 'drivers': [], 'kernel_outputs': {}}):
            return self.subject.create(self.root, {'commit': self.sha, 'output': self.output})

    def test_git_snapshot_keeps_historical_inputs_and_private_receipt(self):
        # Mutation captured: copying working bytes instead of the explicit commit loses the original source.
        name = 'phone/kernel/n71-i2c-power-diagnostic.c'
        (self.root / name).write_text('new working version')
        with patch.dict(os.environ, {SNAPSHOT.reference.ENV: 'unrelated-receipt'}):
            receipt = self.create()
            self.assertEqual(os.environ[SNAPSHOT.reference.ENV], 'unrelated-receipt')
        self.assertEqual((self.output / 'source' / name).read_bytes(), ('fixture:' + name).encode())
        self.assertEqual(receipt['input_count'], 69)
        self.assertTrue(receipt['input_hashes_verified'])
        self.assertEqual(receipt['selected']['diagnostics'], ['fixture'])
        self.assertEqual(receipt['commit'], self.sha)
        self.assertEqual(json.loads((self.output / 'receipt.json').read_text()), receipt)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.output / 'receipt.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / name).read_text(), 'new working version')

    def test_new_output_scope_and_explicit_commit_are_required(self):
        # Mutation captured: allowing reuse of a snapshot directory silently replaces its provenance.
        self.output.mkdir(mode=0o700)
        with self.assertRaises(ValueError): self.create()
        self.output = self.repo / 'outside'
        with self.assertRaises(ValueError): self.create()
        self.output = self.root / 'runtime/new'
        self.sha = 'HEAD'
        with self.assertRaises(ValueError): self.create()
        self.sha = self.git('rev-parse', 'HEAD:project/phone/kernel/n71-i2c-power-diagnostic.c')
        with self.assertRaises(ValueError): self.create()
        self.assertFalse(self.output.exists())

    def test_archived_scripts_remain_data_and_manifest_drift_refuses(self):
        # Mutation captured: importing historical Python executes the deliberately failing archived script.
        script = self.root / 'scripts/host/n71_driver_runtime_build.py'
        raw = script.read_bytes()
        script.write_bytes(raw + b'# changed\n')
        self.assertEqual(self.create()['selected']['diagnostics'], ['fixture'])
        self.output = self.root / 'runtime/changed-proof'
        script.write_bytes(raw)
        proof = self.root / SNAPSHOT.PROOF
        proof.write_bytes(proof.read_bytes() + b'\n')
        with self.assertRaises(ValueError): self.create()
        self.assertFalse(self.output.exists())

    def test_archive_paths_and_links_are_rejected(self):
        # Mutation captured: accepting parent traversal lets a source path escape its project.
        for name, link in [('project/../escape', False), ('foreign/file', False), ('project/link', True)]:
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as archive:
                entry = tarfile.TarInfo(name)
                if link:
                    entry.type = tarfile.SYMTYPE
                    entry.linkname = '/tmp/foreign'
                    archive.addfile(entry)
                else:
                    entry.size = 1
                    archive.addfile(entry, io.BytesIO(b'x'))
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.subject.members(stream.getvalue(), 'project')


class SourceSnapshotMutations(unittest.TestCase):
    def test_boundary_mutations_fail_by_assertion(self):
        source = SOURCE.read_text()
        mutations = [
            ('historical-manifest', 'PROOF in files and files[PROOF][0] == expected', 'True',
                'test_archived_scripts_remain_data_and_manifest_drift_refuses'),
            ('archive-traversal', "'..' not in path.parts", 'True',
                'test_archive_paths_and_links_are_rejected'),
        ]
        for name, before, after, method in mutations:
            self.assertEqual(source.count(before), 1)
            subject = ModuleType('snapshot_mutant')
            exec(compile(ast.parse(source.replace(before, after, 1)), str(SOURCE), 'exec'), subject.__dict__)
            case = type('MutatedSourceSnapshotTests', (SourceSnapshotTests,), {'subject': subject})
            result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
            self.assertEqual(result.errors, [], name)
            self.assertGreater(len(result.failures), 0, name)
            print('N71_SOURCE_SNAPSHOT_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
