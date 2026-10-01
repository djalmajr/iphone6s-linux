"""Pin Pongo selection and verify rejection before USB or child processes."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('PONGO_SELECTION_SOURCE', ROOT / 'scripts/boot/pongo_select.py'))


class PongoSelectionTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='pongo-selection-synthetic-')
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name).resolve()
        self.boot = self.root / 'scripts/boot'
        self.boot.mkdir(parents=True)
        self.default = self.root / 'artifacts/Pongo.bin'
        self.default.parent.mkdir()
        self.candidate = self.root / 'source candidate.bin'
        self.default_bytes = b'SYNTHETIC_DEFAULT'.ljust(238096, b'D')
        self.source_bytes = b'SYNTHETIC_SOURCE'.ljust(238096, b'S')
        self.default.write_bytes(self.default_bytes)
        self.candidate.write_bytes(self.source_bytes)
        text = SOURCE.read_text().replace(
            '1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575',
            hashlib.sha256(self.default_bytes).hexdigest()).replace(
                '17d3df93213bb24f8ba73a8ad390e6bcc56351b41d87a315d47d37aa51100efd',
                hashlib.sha256(self.source_bytes).hexdigest())
        self.helper = self.boot / 'pongo_select.py'
        self.helper.write_text(text)
        self.environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        self.environment.pop('IPHONE_LINUX_PONGO', None)
        self.environment.pop('IPHONE_LINUX_PROFILE', None)

    def cli(self):
        return subprocess.run([sys.executable, str(self.helper)], env=self.environment,
                              capture_output=True, text=True, timeout=10)

    def test_default_and_explicit_candidate_choose_distinct_pinned_files(self):
        # Mutation captured: using the default hash/path for explicit source selection.
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.default))
        self.environment['IPHONE_LINUX_PONGO'] = str(self.candidate)
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.candidate))
        self.assertEqual(self.default.read_bytes(), self.default_bytes)

    def test_empty_or_invalid_selection_never_falls_back(self):
        # Mutation captured: treating an empty selector as absent or ignoring controls.
        for value in ('', str(self.root / 'missing'), str(self.candidate) + '\n'):
            with self.subTest(value=value):
                self.environment['IPHONE_LINUX_PONGO'] = value
                result = self.cli()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, '')

    def test_modified_default_and_source_are_rejected(self):
        # Mutation captured: omitting the trusted expected SHA comparison.
        for path in (self.default, self.candidate):
            with self.subTest(path=path):
                if path == self.candidate:
                    self.environment['IPHONE_LINUX_PONGO'] = str(path)
                path.write_bytes(b'X' + path.read_bytes()[1:])
                result = self.cli()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('Hash do Pongo inesperado', result.stderr)

    def test_links_and_public_writes_are_rejected(self):
        # Mutation captured: allowing file links or writable-by-others boot inputs.
        self.environment['IPHONE_LINUX_PONGO'] = str(self.candidate)
        target = self.root / 'link-target'
        target.write_bytes(self.source_bytes)
        self.candidate.unlink()
        self.candidate.symlink_to(target)
        self.assertEqual(self.cli().returncode, 1)
        self.candidate.unlink()
        os.link(target, self.candidate)
        self.assertEqual(self.cli().returncode, 1)
        self.candidate.unlink()
        self.candidate.write_bytes(self.source_bytes)
        self.candidate.chmod(0o666)
        self.assertEqual(self.cli().returncode, 1)

    def test_size_and_parent_symlinks_are_rejected(self):
        # Mutation captured: trusting file size or following parent directory aliases.
        self.environment['IPHONE_LINUX_PONGO'] = str(self.candidate)
        self.candidate.write_bytes(self.source_bytes + b'X')
        self.assertEqual(self.cli().returncode, 1)
        self.candidate.write_bytes(self.source_bytes)
        alias = self.root / 'alias'
        alias.symlink_to(self.candidate.parent, target_is_directory=True)
        self.environment['IPHONE_LINUX_PONGO'] = str(alias / self.candidate.name)
        self.assertEqual(self.cli().returncode, 1)


if __name__ == '__main__':
    unittest.main()
