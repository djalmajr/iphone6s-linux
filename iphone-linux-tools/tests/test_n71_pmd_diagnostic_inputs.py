"""Real archive/filesystem probes for the sealed diagnostic-source boundary."""
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
SCRIPT = Path(os.environ.get('N71_PMD_DIAGNOSTICS_SCRIPT',
                            ROOT / 'scripts/build/build-n71-pmd-diagnostics.py'))
SPEC = importlib.util.spec_from_file_location('pmd_diagnostic_inputs', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DiagnosticInputs(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='pmd-diagnostic-inputs-')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()

    def archive(self, *, count=62, first=None, link=False):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as package:
            for index in range(count):
                name = first if index == 0 and first else f'phone/kernel/probe{index}.h'
                info = tarfile.TarInfo(name)
                info.mode = 0o644
                raw = f'/* independent fixture {index} */\n'.encode()
                info.size = len(raw)
                if link and index == 0:
                    info.type = tarfile.SYMTYPE
                    info.linkname = '/outside'
                    info.size = 0
                package.addfile(info, None if link and index == 0 else io.BytesIO(raw))
        return stream.getvalue().ljust(389120, b'\0')

    def test_exact_archive_returns_member_bytes_and_padding_tamper_is_refused(self):
        # Kills ignored input hashes; tar readers otherwise ignore modified padding.
        raw = self.archive()
        path = self.folder / 'inputs.tar'
        path.write_bytes(raw)
        with patch.object(MODULE, 'INPUT_SHA', hashlib.sha256(raw).hexdigest()):
            result = MODULE.inputs(path)
            self.assertEqual(len(result), 62)
            self.assertEqual(result['phone/kernel/probe61.h'], b'/* independent fixture 61 */\n')
            path.write_bytes(raw[:-1] + b'X')
            with self.assertRaisesRegex(ValueError, 'archive differs'):
                MODULE.inputs(path)
        self.assertEqual(list(self.folder.iterdir()), [path])

    def test_aliases_are_refused_before_archive_processing(self):
        # Kills accepting symlink/hardlink aliases to a valid source archive.
        raw = self.archive()
        path = self.folder / 'inputs.tar'
        path.write_bytes(raw)
        alias = self.folder / 'alias.tar'
        alias.symlink_to(path)
        with patch.object(MODULE, 'INPUT_SHA', hashlib.sha256(raw).hexdigest()):
            with self.assertRaises(ValueError):
                MODULE.inputs(alias)
            alias.unlink()
            os.link(path, alias)
            with self.assertRaises(ValueError):
                MODULE.inputs(path)

    def test_exact_members_refuse_traversal_links_duplicates_and_missing_inputs(self):
        # Kills removing archive framing/path/count checks even with a trusted digest.
        for raw in (self.archive(first='phone/kernel/../../outside.h'),
                    self.archive(first='/phone/kernel/outside.h'),
                    self.archive(first='other/kernel/probe.h'),
                    self.archive(count=63, first='phone/kernel/probe1.h'),
                    self.archive(link=True), self.archive(count=61)):
            path = self.folder / 'inputs.tar'
            path.write_bytes(raw)
            with patch.object(MODULE, 'INPUT_SHA', hashlib.sha256(raw).hexdigest()):
                with self.assertRaises(ValueError):
                    MODULE.inputs(path)
            self.assertFalse((self.folder / 'outside.h').exists())


class BuildRecords(unittest.TestCase):
    def record(self):
        selected = {'base_commit': 'synthetic-base', 'files': {'source.c': ('before', 'after')}}
        record = {'status': 'compiled_verified', 'source': json.loads(json.dumps(selected)),
                  'installed': False, 'build': {'exit_code': 0, 'kernel_release': MODULE.RELEASE,
                  'full_image_linked': True, 'vmlinux_modpost_verified': True,
                  'serdev_stop_bits_export_verified': True, 'embedded_config_exact_match': True,
                  'source_before_equals_after': True, 'modules_prepare_executed': True}}
        return record, selected

    def test_json_roundtrip_accepts_exact_source_and_refuses_changed_blob(self):
        record, selected = self.record()
        try:
            self.assertIs(MODULE.qualified_build_record(record, selected), record['build'])
        except ValueError as error:
            self.fail('Exact serialized source refused: ' + str(error))
        record['source']['files']['source.c'][1] = 'changed'
        with self.assertRaises(ValueError):
            MODULE.qualified_build_record(record, selected)
        self.assertEqual(selected['files']['source.c'], ('before', 'after'))

    def test_missing_build_evidence_and_installed_record_are_refused(self):
        for key in ('full_image_linked', 'vmlinux_modpost_verified',
                    'serdev_stop_bits_export_verified', 'embedded_config_exact_match',
                    'source_before_equals_after', 'modules_prepare_executed'):
            record, selected = self.record()
            record['build'][key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                MODULE.qualified_build_record(record, selected)
        record, selected = self.record()
        record['installed'] = True
        with self.assertRaises(ValueError):
            MODULE.qualified_build_record(record, selected)


@unittest.skipIf(os.environ.get('N71_PMD_DIAGNOSTICS_SCRIPT'), 'Mutation child selects subject')
class InputMutations(unittest.TestCase):
    def test_weakened_boundaries_fail_by_assertion(self):
        # Kills ignored digest, alias, duplicate, traversal and count checks.
        source = SCRIPT.read_text()
        mutations = (
            ('digest', 'hashlib.sha256(raw).hexdigest() == INPUT_SHA', 'True', 'exact'),
            ('aliases', 'path == path.resolve(strict=True) and path.is_file()\n'
             '            and path.stat().st_uid == os.geteuid() and path.stat().st_nlink == 1', 'True', 'aliases'),
            ('count', "len(result) == 62", 'True', 'members'),
            ('duplicates', 'member.name not in result', 'True', 'members'),
            ('traversal', "'..' not in name.parts", 'True', 'members'),
            ('record-source', "record['source'] == expected_source", 'True', 'record'),
        )
        methods = {'exact': 'test_exact_archive_returns_member_bytes_and_padding_tamper_is_refused',
                   'aliases': 'test_aliases_are_refused_before_archive_processing',
                   'members': 'test_exact_members_refuse_traversal_links_duplicates_and_missing_inputs',
                   'record': 'test_json_roundtrip_accepts_exact_source_and_refuses_changed_blob'}
        with tempfile.TemporaryDirectory(prefix='pmd-input-mutations-') as directory:
            for name, before, after, method in mutations:
                self.assertEqual(source.count(before), 1, name)
                changed = source.replace(before, after, 1)
                compile(changed, name, 'exec')
                path = Path(directory) / (name + '.py')
                path.write_text(changed)
                environment = dict(os.environ, N71_PMD_DIAGNOSTICS_SCRIPT=str(path),
                                   PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT / 'tests'))
                case = 'BuildRecords' if method == 'record' else 'DiagnosticInputs'
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                                         'test_n71_pmd_diagnostic_inputs.' + case + '.' + methods[method]],
                                        env=environment, capture_output=True, text=True, timeout=30)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', result.stderr, name + result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('PMD_INPUT_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
