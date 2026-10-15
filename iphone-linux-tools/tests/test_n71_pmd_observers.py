"""Sealed real observer sources as data; no kernel, VM or phone access."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/build/build-n71-pmd-observers.py'
spec = importlib.util.spec_from_file_location('observers_under_test', Path(os.environ.get('N71_OBSERVER_BUILDER_SCRIPT', SOURCE)))
SUBJECT = importlib.util.module_from_spec(spec); spec.loader.exec_module(SUBJECT)


def package(data):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, raw in sorted(data.items()):
            info = tarfile.TarInfo(name); info.mode = 0o644; info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
    return stream.getvalue()


class ObserverInputs(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='n71-observer-inputs-'); self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve(); self.path = self.folder / 'source.tar'
        proof = json.loads((ROOT / 'docs/evidence/n71-pmd-observer-inputs.json').read_text())
        prefix = ROOT.name + '/'
        raw = subprocess.check_output(['git', 'archive', '--format=tar', SUBJECT.SOURCE_HEAD, '--',
            *[prefix + name for name in sorted(proof['inputs'])]], cwd=ROOT.parent, timeout=30)
        self.data = {}
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            for member in archive:
                if member.isdir(): continue
                self.assertTrue(member.isfile() and member.name.startswith(prefix))
                stream = archive.extractfile(member)
                with stream: self.data[member.name.removeprefix(prefix)] = stream.read()
        self.assertEqual(set(self.data), set(proof['inputs']))
        self.raw = package(self.data); self.path.write_bytes(self.raw)

    def test_fixed_real_sources_are_accepted_without_extraction(self):
        before = self.path.read_bytes()
        with patch.object(subprocess, 'run', side_effect=AssertionError('No build permitted')):
            self.assertEqual(SUBJECT.inputs(self.path), self.data)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.folder.iterdir()), [self.path])

    def test_changed_padding_content_size_and_file_links_are_refused(self):
        for raw in (self.raw[:-1] + b'X', self.raw[:512] + bytes([self.raw[512] ^ 1]) + self.raw[513:], self.raw + b'\0'):
            self.path.write_bytes(raw)
            with self.assertRaises(ValueError): SUBJECT.inputs(self.path)
        self.path.write_bytes(self.raw)
        alias = self.folder / 'alias'; os.link(self.path, alias)
        with self.assertRaises(ValueError): SUBJECT.inputs(self.path)
        alias.unlink(); alias.symlink_to(self.path)
        with self.assertRaises(ValueError): SUBJECT.inputs(alias)

    def test_manifest_rejects_consistently_repacked_new_source(self):
        name = sorted(self.data)[0]; data = dict(self.data); data[name] = b'X' + data[name][1:]
        raw = package(data); self.path.write_bytes(raw)
        with patch.object(SUBJECT, 'TAR_SHA', hashlib.sha256(raw).hexdigest()), self.assertRaises(ValueError):
            SUBJECT.inputs(self.path)

    def test_wrong_platform_refuses_before_build_or_output(self):
        target = self.folder / 'n71-pmd-observers-output'
        with patch.object(sys, 'argv', ['builder', '--inputs', str(self.path), '--output-dir', str(target)]), \
                patch.object(sys, 'platform', 'darwin'), patch.object(SUBJECT.platform, 'machine', return_value='aarch64'), \
                patch.object(SUBJECT, 'base_builder', side_effect=AssertionError('No checker load')), \
                self.assertRaisesRegex(ValueError, 'Dedicated unprivileged ARM64'):
            SUBJECT.main()
        self.assertFalse(target.exists())


@unittest.skipIf(os.environ.get('N71_OBSERVER_BUILDER_SCRIPT'), 'Mutation child')
class ObserverMutations(unittest.TestCase):
    def test_archive_manifest_file_and_platform_guards(self):
        variants = [
            ('archive', 'hashlib.sha256(raw).hexdigest() == TAR_SHA', 'True', 'changed_padding_content_size_and_file_links_are_refused'),
            ('manifest', "separators=(',', ':')).encode()).hexdigest() == INPUTS_PIN", "separators=(',', ':')).encode()).hexdigest() != ''", 'manifest_rejects_consistently_repacked_new_source'),
            ('file-link', 'path.stat().st_nlink == 1', 'True', 'changed_padding_content_size_and_file_links_are_refused'),
            ('platform', "sys.platform == 'linux'", 'True', 'wrong_platform_refuses_before_build_or_output'),
        ]
        text = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-observer-mutations-') as directory:
            for name, before, after, method in variants:
                self.assertEqual(text.count(before), 1, name)
                body = text.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory) / (name + '.py'); path.write_text(body)
                env = dict(os.environ, N71_OBSERVER_BUILDER_SCRIPT=str(path), PYTHONPATH=str(ROOT / 'tests'), PYTHONDONTWRITEBYTECODE='1')
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                    'test_n71_pmd_observers.ObserverInputs.test_' + method], env=env,
                    capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name + result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('N71_OBSERVER_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
