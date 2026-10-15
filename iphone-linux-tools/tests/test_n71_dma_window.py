"""Private DT-only DMA composition; identity/kernel fixtures are synthetic."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import test_n71_calibration_profile as fixture

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/build/compose-n71-dma-window.py'
SPEC = importlib.util.spec_from_file_location('dma_window_profile', SOURCE)
SUBJECT = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(SUBJECT)


class DmaWindowTests(unittest.TestCase):
    subject = SUBJECT

    def setUp(self):
        data = fixture.CalibrationProfileTests('test_profile_delta_and_real_local_gates_preserve_source')
        data.setUp(); self.addCleanup(data.doCleanups); data.invoke()
        self.data = data; self.root = data.root; self.folder = data.output
        self.profile = self.folder / 'deployment.json'; self.output = self.root / 'runtime/dma-window'
        self.reference = self.root / 'docs/evidence/n71-dart-apple-stream-reference.json'
        self.reference.write_bytes((ROOT / 'docs/evidence/n71-dart-apple-stream-reference.json').read_bytes())
        self.original = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        self.prefix = data.prefix; raw = self.original['payload.bin']
        self.length = struct.unpack_from('>I', raw, self.prefix + 4)[0]
        self.original_dtb = raw[self.prefix:self.prefix + self.length]
        data.identity_reads = 0

    def invoke(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.subject.compose(self.root, {'source': self.profile, 'output': self.output})

    def test_real_profile_delta_keeps_kernel_keys_modules_and_source(self):
        # Mutation: drop the payload suffix, change the window, or lose private modes/umask.
        environment = os.environ.get('IPHONE_LINUX_PROFILE'); mask = os.umask(0o027)
        try:
            try: self.invoke()
            except ValueError as error: self.fail('Qualified profile refused: ' + str(error))
            observed = os.umask(0o027); self.assertEqual(observed, 0o027)
        finally: os.umask(mask)
        self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'), environment)
        self.assertEqual({p.name:p.read_bytes() for p in self.folder.iterdir()}, self.original)
        after = {p.name:p.read_bytes() for p in self.output.iterdir()}
        self.assertEqual(set(after), set(self.original))
        for name in set(after) - {'payload.bin', 'deployment.json', 'provenance.json'}:
            self.assertEqual(after[name], self.original[name])
        raw = after['payload.bin']; length = struct.unpack_from('>I', raw, self.prefix + 4)[0]
        self.assertEqual(raw[:self.prefix], self.original['payload.bin'][:self.prefix])
        self.assertEqual(raw[self.prefix + length:], self.original['payload.bin'][self.prefix + self.length:])
        nodes = self.subject.CAL.DIAGNOSTIC.TOPOLOGY.parse_dtb(raw[self.prefix:self.prefix + length])
        self.assertEqual(nodes[self.subject.DART][self.subject.PROPERTY], struct.pack('>QQ', 0x80000000, 0x3ffff000))
        self.assertEqual(nodes[self.subject.DART]['status'], b'disabled\0')
        window = json.loads(after['provenance.json'])['dart_dma_window']
        self.assertEqual((window['start'], window['length'], window['end_exclusive']),
                         (0x80000000, 0x3ffff000, 0xbffff000))
        self.assertIs(window['physical_acceptance'], False)
        self.assertIs(json.loads(after['provenance.json'])['physical_boot_tested'], False)
        self.assertEqual(json.loads(after['deployment.json'])['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.output.iterdir()))
        self.assertEqual(self.data.identity_reads, 2)

    def test_reference_source_and_private_inputs_refuse_before_output(self):
        # Mutation: bypass board reference, source scope, hash, file catalog or identity-path guards.
        cases = [(self.reference, self.reference.read_bytes() + b' ')]
        for filename, key, value in [('provenance.json', 'pcie_calibration', False),
            ('provenance.json', 'dart_dma_window', {}), ('provenance.json', 'calibration_blob_sha256', '0' * 64),
            ('deployment.json', 'sha256', '0' * 64), ('deployment.json', 'client_key', 'foreign')]:
            path = self.folder / filename; data = json.loads(path.read_bytes()); data[key] = value
            cases.append((path, json.dumps(data).encode()))
        cases += [(self.profile, self.profile.read_bytes() + b' ' * 8193)]
        for path, changed in cases:
            original = path.read_bytes(); path.write_bytes(changed)
            try:
                with self.subTest(path=path.name), self.assertRaises(ValueError): self.invoke()
                self.assertFalse(self.output.exists())
            finally: path.write_bytes(original)
        path = self.folder / 'foreign'; path.write_bytes(b'owned'); path.chmod(0o600)
        try:
            with self.assertRaises(ValueError): self.invoke()
            self.assertFalse(self.output.exists())
        finally: path.unlink()
        self.assertEqual(self.data.identity_reads, 0)

    def test_dt_scope_and_only_one_big_endian_property(self):
        # Mutation: accept foreign/active DART, altered nodes or noncanonical aperture bytes.
        window = struct.pack('>QQ', 0x80000000, 0x3ffff000)
        nodes = self.subject.CAL.DIAGNOSTIC.TOPOLOGY.parse_dtb(self.original_dtb)
        serialize = self.subject.CAL.DIAGNOSTIC.DIAGNOSTIC.serialize_dtb
        for key, value in [('status', b'okay\0'), ('reg', struct.pack('>QQ', 0x602004000, 0x4000)),
            ('interrupts', struct.pack('>III', 0, 247, 4)), (self.subject.PROPERTY, window)]:
            altered = {p:dict(v) for p,v in nodes.items()}; altered[self.subject.DART][key] = value
            with self.assertRaises(ValueError): self.subject.dtb(serialize(self.original_dtb, altered), window)
        candidate = self.subject.dtb(self.original_dtb, window)
        after = self.subject.CAL.DIAGNOSTIC.TOPOLOGY.parse_dtb(candidate)
        for wrong in [struct.pack('<QQ', 0x80000000, 0x3ffff000), struct.pack('>QQ', 0x80000000, 0x40000000)]:
            with self.assertRaises(ValueError): self.subject.dtb(self.original_dtb, wrong)
        for path, key, value in [(self.subject.DART, 'extra', b'1'), ('/soc/usb', 'status', b'disabled\0')]:
            altered = {p:dict(v) for p,v in after.items()}; altered[path][key] = value
            with self.assertRaises(ValueError): self.subject.validate_dtb(self.original_dtb, serialize(candidate, altered), window)
        altered = {p:dict(v) for p,v in after.items()}; altered['/foreign'] = {}
        with self.assertRaises(ValueError): self.subject.validate_dtb(self.original_dtb, serialize(candidate, altered), window)
        altered = {p:dict(v) for p,v in after.items()}; altered[self.subject.DART][self.subject.PROPERTY] = b'0' * 16
        with self.assertRaises(ValueError): self.subject.validate_dtb(self.original_dtb, serialize(candidate, altered), window)

    def test_paths_existing_output_and_partial_failure_preserve_source(self):
        # Mutation: overwrite another output or fail to restore umask/environment on candidate refusal.
        self.output.mkdir(mode=0o700); p = self.output / 'sentinel'; p.write_bytes(b'owned')
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(p.read_bytes(), b'owned')
        self.output = self.root / 'outside'
        with self.assertRaises(ValueError): self.invoke()
        self.assertFalse(self.output.exists())
        self.output = self.root / 'runtime/partial'
        def identity():
            if Path(os.environ['IPHONE_LINUX_PROFILE']).parent == self.output:
                raise OSError('Synthetic candidate identity failure')
            return self.data.identity()
        environment = os.environ.get('IPHONE_LINUX_PROFILE'); mask = os.umask(0o027)
        try:
            with patch.object(self.subject.runtime.device_profile, 'verify', identity):
                with self.assertRaises(OSError): self.invoke()
            observed = os.umask(0o027); self.assertEqual(observed, 0o027)
        finally: os.umask(mask)
        self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'), environment)
        self.assertEqual({p.name:p.read_bytes() for p in self.folder.iterdir()}, self.original)
        self.assertEqual(len(list(self.output.iterdir())), 14)


class DmaWindowMutationProof(unittest.TestCase):
    def test_assertion_mutations(self):
        baseline = unittest.TestResult(); unittest.defaultTestLoader.loadTestsFromTestCase(DmaWindowTests).run(baseline)
        self.assertFalse(baseline.errors or baseline.failures, str(baseline.errors + baseline.failures))
        cases = [
            ('Board reference digest differs', 'test_reference_source_and_private_inputs_refuse_before_output'),
            ('Calibrated source without DMA override required', 'test_reference_source_and_private_inputs_refuse_before_output'),
            ('Exact fourteen source profile files required', 'test_reference_source_and_private_inputs_refuse_before_output'),
            ('Canonical source identity paths required', 'test_reference_source_and_private_inputs_refuse_before_output'),
            ('DMA source snapshot hashes differ', 'test_reference_source_and_private_inputs_refuse_before_output'),
            ('DMA source deployment exceeds budget', 'test_reference_source_and_private_inputs_refuse_before_output'),
            ('Source calibration bytes differ', 'test_reference_source_and_private_inputs_refuse_before_output'),
            ('Unmodified disabled N71 DART required', 'test_dt_scope_and_only_one_big_endian_property'),
            ('Canonical big-endian DMA cells required', 'test_dt_scope_and_only_one_big_endian_property'),
            ('DMA window bytes differ', 'test_dt_scope_and_only_one_big_endian_property'),
            ('DMA candidate changed preserved DT data', 'test_dt_scope_and_only_one_big_endian_property')]
        for message, method in cases:
            tree = ast.parse(SOURCE.read_text()); matches = []
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'require'
                    and len(node.args) == 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == message):
                    node.args[0] = ast.Constant(True); matches.append(node)
            self.assertEqual(len(matches), 1, message)
            self.check_mutant(tree, method, message)
        source = SOURCE.read_text()
        for before, after, method in [
            ("return struct.pack('>QQ', START, LENGTH)", "return struct.pack('<QQ', START, LENGTH)", 'test_real_profile_delta_keeps_kernel_keys_modules_and_source'),
            ('raw[:prefix] + candidate + raw[prefix + length:]', "raw[:prefix] + candidate + b''", 'test_real_profile_delta_keeps_kernel_keys_modules_and_source'),
            ('os.umask(previous)', 'pass', 'test_paths_existing_output_and_partial_failure_preserve_source')]:
            self.assertEqual(source.count(before), 1)
            self.check_mutant(ast.parse(source.replace(before, after, 1)), method, before)

    def check_mutant(self, tree, method, name):
        module = importlib.util.module_from_spec(SPEC)
        exec(compile(ast.fix_missing_locations(tree), str(SOURCE), 'exec'), module.__dict__)
        case = DmaWindowTests(method); case.subject = module; result = unittest.TestResult(); case.run(result)
        self.assertFalse(result.errors, 'Infrastructure error is not proof: ' + name + str(result.errors))
        self.assertTrue(result.failures and all('AssertionError' in detail for _, detail in result.failures), name)
        print('N71_DMA_WINDOW_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
