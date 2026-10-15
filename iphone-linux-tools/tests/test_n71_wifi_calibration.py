"""Private calibration extraction and shared Pongo property contracts."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from test_n71_runtime_tunables import node, capture as tunable_capture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/research'))
import n71_wifi_calibration as SUBJECT

PARSER = ROOT / 'scripts/research/n71_runtime_tunables.py'
EXTRACTOR = ROOT / 'scripts/research/n71_wifi_calibration.py'
BLOB = bytes(range(256)) * 4


def fixture(blob=BLOB, port='uart4', duplicate=False):
    properties = [(SUBJECT.PROPERTY, blob)] * (2 if duplicate else 1)
    blocks = [node(0, 'device-tree'), node(1, 'arm-io'), node(2, port), node(3, 'wlan', properties)]
    return (('\n' + ('-' * 128 + '\n').join(blocks)) + 'pongoOS> ').encode()


class N71WiFiCalibration(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.prior_root = SUBJECT.capture.ROOT
        SUBJECT.capture.ROOT = self.root
        self.runtime = self.root / 'runtime'; self.runtime.mkdir(mode=0o700)
        self.source = self.runtime / 'capture.txt'; self.source.write_bytes(fixture()); self.source.chmod(0o600)
        self.output = self.runtime / 'candidate'

    def tearDown(self):
        SUBJECT.capture.ROOT = self.prior_root
        self.temporary.cleanup()

    def extract(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            SUBJECT.extract(self.source, self.output)
        return stream.getvalue()

    def test_exact_private_files_and_unchanged_source(self):
        # Mutation captured: wrong bytes, leaked provenance, or missing umask restoration.
        before = self.source.read_bytes(); previous = os.umask(0o027)
        try:
            text = self.extract(); observed = os.umask(0o027)
            self.assertEqual(observed, 0o027)
        finally:
            os.umask(previous)
        self.assertEqual(text, 'N71_WIFI_CALIBRATION_EXTRACTED; private candidate; no hardware action\n')
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual({p.name for p in self.output.iterdir()}, {'calibration-private.bin', 'provenance-private.json'})
        self.assertEqual((self.output / 'calibration-private.bin').read_bytes(), BLOB)
        report = json.loads((self.output / 'provenance-private.json').read_text())
        self.assertEqual(report, {'format': 1, 'board': 'N71/S8000', 'path': SUBJECT.NODE, 'property': SUBJECT.PROPERTY,
            'capture_sha256': hashlib.sha256(before).hexdigest(), 'bytes': 1024,
            'sha256': hashlib.sha256(BLOB).hexdigest(), 'hardware_writes': False,
            'firmware_executed': False, 'physical_acceptance': False})
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.output.iterdir()))

    def test_shared_selection_and_immutable_result(self):
        # Mutation captured: missing selection/type/budget checks or mutable byte arrays.
        selection = {(SUBJECT.NODE, SUBJECT.PROPERTY): ('calibration', 1024)}
        data = bytearray(fixture()); result = SUBJECT.capture.properties_capture(data, selection)
        self.assertEqual(result, {'calibration': BLOB}); self.assertIsInstance(result['calibration'], bytes)
        data[:] = b'changed'; self.assertEqual(result['calibration'], BLOB)
        invalid = [None, {}, {('bad', SUBJECT.PROPERTY): ('calibration', 1024)},
            {(SUBJECT.NODE, SUBJECT.PROPERTY): ('calibration', True)},
            {(SUBJECT.NODE, SUBJECT.PROPERTY): ('calibration', 131073)},
            {(SUBJECT.NODE, SUBJECT.PROPERTY): ('calibration', 1023)},
            {(SUBJECT.NODE, SUBJECT.PROPERTY): ('calibration', 1024), ('/device-tree/other', 'other'): ('calibration', 1024)}]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(ValueError):
                SUBJECT.capture.properties_capture(fixture(), request)
        tables = SUBJECT.capture.parse_capture(tunable_capture())
        self.assertEqual(tables['common']['records'], [{'offset': 0x100, 'mask': 0xff, 'value': 0x25}] * 2)
        self.assertEqual(tables['config1']['path'], '/device-tree/arm-io/apcie/pci-bridge1')

    def test_capture_framing_and_node_scope(self):
        # Mutation captured: omitted prompt, missing property, duplicate rows or wrong node selection.
        invalid = [fixture().split(b'pongoOS>', 1)[0].rstrip(), fixture(port='uart3'), fixture(duplicate=True),
            fixture().replace(b'wifi-calibration-msf', b'wifi-calibration-old'),
            fixture().replace(b'00 01 02', b'gg 01 02', 1),
            fixture().replace(b'    name', b'     name', 1), b'x' * (SUBJECT.capture.MAX_CAPTURE + 1)]
        for raw in invalid:
            with self.subTest(bytes=len(raw)), self.assertRaises(ValueError):
                SUBJECT.capture.properties_capture(raw, {(SUBJECT.NODE, SUBJECT.PROPERTY): ('calibration', 1024)})
        self.assertFalse(self.output.exists())

    def test_wrong_size_refused_before_output(self):
        # Mutation captured: removing the exact 1024-byte gate writes a shortened candidate.
        for blob in [BLOB[:-1], BLOB + b'x']:
            self.source.write_bytes(fixture(blob))
            with self.assertRaises(ValueError):
                self.extract()
            self.assertFalse(self.output.exists())

    def test_public_source_refused_before_output(self):
        # Mutation captured: bypassing private_path accepts a world-readable source.
        self.source.chmod(0o644)
        with self.assertRaises(ValueError):
            self.extract()
        self.assertFalse(self.output.exists())

    def test_write_failure_restores_umask(self):
        # Mutation captured: omitting finally restoration leaks the private umask after an I/O failure.
        previous = os.umask(0o027)
        self.runtime.chmod(0o500)
        try:
            with self.assertRaises(OSError):
                self.extract()
            observed = os.umask(0o027)
            self.assertEqual(observed, 0o027)
            self.assertFalse(self.output.exists())
        finally:
            self.runtime.chmod(0o700)
            os.umask(previous)

    def test_output_scope_and_links_preserve_existing_files(self):
        # Mutation captured: removing the direct runtime parent check creates a foreign output.
        self.output = self.root / 'foreign'
        with self.assertRaises(ValueError):
            self.extract()
        self.assertFalse(self.output.exists())
        self.output = self.runtime / 'existing'; self.output.mkdir(mode=0o700)
        sentinel = self.output / 'sentinel'; sentinel.write_bytes(b'owned')
        with self.assertRaises(ValueError):
            self.extract()
        self.assertEqual(sentinel.read_bytes(), b'owned')
        self.output = self.runtime / 'dangling'; self.output.symlink_to(self.runtime / 'absent')
        with self.assertRaises(ValueError):
            self.extract()
        self.assertFalse((self.runtime / 'absent').exists())
        link = self.runtime / 'linked'; link.symlink_to(self.source); self.source = link
        self.output = self.runtime / 'new'
        with self.assertRaises(ValueError):
            self.extract()
        self.assertFalse(self.output.exists())

    def test_real_entrypoint_refuses_without_writes(self):
        # Mutation captured: the CLI must dispatch the protected extractor, not write before parsing.
        self.source.write_bytes(fixture(port='uart3'))
        previous = sys.argv
        try:
            sys.argv = [str(EXTRACTOR), '--input', str(self.source), '--output-dir', str(self.output)]
            with self.assertRaises(ValueError):
                SUBJECT.main()
        finally:
            sys.argv = previous
        self.assertFalse(self.output.exists())


def changed(path, before, after):
    text = path.read_text()
    if text.count(before) != 1:
        raise ValueError('Unique mutation anchor required')
    module = types.ModuleType('calibration_mutant'); module.__file__ = str(path)
    exec(compile(text.replace(before, after, 1), str(path), 'exec'), module.__dict__)
    return module


class CalibrationMutationProof(unittest.TestCase):
    def test_source_mutations(self):
        # Real source mutations; exceptions/import errors are never accepted as kills.
        global SUBJECT
        original = SUBJECT
        baseline = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(N71WiFiCalibration).run(baseline)
        self.assertFalse(baseline.errors or baseline.failures, 'Complete functional baseline required')
        cases = [
            (PARSER, 'or not selections', 'or False', 'test_shared_selection_and_immutable_result'),
            (PARSER, "or not data.rstrip().endswith(b'pongoOS>')", 'or False', 'test_capture_framing_and_node_scope'),
            (PARSER, 'if node == path', 'if True', 'test_capture_framing_and_node_scope'),
            (PARSER, 'if key in chunks or not line.startswith(indent + key):', 'if False:', 'test_capture_framing_and_node_scope'),
            (PARSER, 'if len(chunks[current]) > wanted[current][1]:', 'if False:', 'test_shared_selection_and_immutable_result'),
            (PARSER, 'selected[label] = bytes(raw)', 'selected[label] = raw', 'test_shared_selection_and_immutable_result'),
            (PARSER, 'if set(selected) != labels:', 'if False:', 'test_capture_framing_and_node_scope'),
            (EXTRACTOR, 'source = capture.private_path(source)', 'source = source.absolute()', 'test_public_source_refused_before_output'),
            (EXTRACTOR, 'output.parent != runtime', 'False', 'test_output_scope_and_links_preserve_existing_files'),
            (EXTRACTOR, 'if len(blob) != SIZE:', 'if False:', 'test_wrong_size_refused_before_output'),
            (EXTRACTOR, 'os.umask(previous)', 'pass', 'test_exact_private_files_and_unchanged_source'),
            (EXTRACTOR, 'os.umask(previous)', 'pass', 'test_write_failure_restores_umask'),
            (EXTRACTOR, "print('N71_WIFI_CALIBRATION_EXTRACTED; private candidate; no hardware action', flush=True)",
             'print(report, flush=True)', 'test_exact_private_files_and_unchanged_source'),
            (EXTRACTOR, 'extract(options.input, options.output_dir)', 'pass', 'test_real_entrypoint_refuses_without_writes')]
        for path, before, after, test in cases:
            try:
                SUBJECT = changed(EXTRACTOR, 'SIZE = 1024', 'SIZE = 1024') if path == PARSER else changed(path, before, after)
                if path == PARSER:
                    SUBJECT.capture = changed(path, before, after)
                result = unittest.TestResult(); N71WiFiCalibration(test).run(result)
                self.assertFalse(result.errors, f'Invalid mutation proof: {before}')
                self.assertTrue(result.failures and all('AssertionError' in detail for _, detail in result.failures), before)
            finally:
                SUBJECT = original
        print('N71_CALIBRATION_ASSERTION_MUTATIONS_OK 14/14')


if __name__ == '__main__':
    unittest.main()
