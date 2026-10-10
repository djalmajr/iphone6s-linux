"""Opt-in PCI OF calibration composition preserves private source identities."""
import contextlib
import ast
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import test_n71_driver_runtime_cli as fixture

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/build/compose-n71-calibration.py'
SPEC = importlib.util.spec_from_file_location('calibration_profile', SOURCE)
SUBJECT = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(SUBJECT)
BLOB = bytes(range(256)) * 4


class CalibrationProfileTests(unittest.TestCase):
    subject = SUBJECT

    def setUp(self):
        data = fixture.RuntimeCliTests('test_real_entry_and_local_check_preserve_files_without_handler_or_output')
        data.setUp(); self.addCleanup(data.doCleanups); self.data = data; self.root = data.root
        self.folder = data.folder; self.profile = data.profile
        self.directory = self.root / 'runtime/calibration'; self.directory.mkdir(mode=0o700)
        self.report = {'format': 1, 'board': 'N71/S8000', 'path': '/device-tree/arm-io/uart4/wlan',
            'property': 'wifi-calibration-msf', 'capture_sha256': self.subject.DIAGNOSTIC.DIAGNOSTIC.CAPTURE_SHA,
            'bytes': 1024, 'sha256': hashlib.sha256(BLOB).hexdigest(), 'hardware_writes': False,
            'firmware_executed': False, 'physical_acceptance': False}
        (self.directory / 'calibration-private.bin').write_bytes(BLOB)
        self.save_report()
        for p in self.directory.iterdir(): p.chmod(0o600)
        self.output = self.root / 'runtime/calibrated'; self.identity_reads = 0; self.fail_candidate = False
        hook = patch.object(self.subject.runtime.device_profile, 'verify', self.identity)
        hook.start(); self.addCleanup(hook.stop)
        link = self.subject.runtime.link_module(self.root)
        self.prefix = link.aspm_payload({'payload': self.folder / 'payload.bin'}, data.metadata)
        payload = (self.folder / 'payload.bin').read_bytes()
        self.length = struct.unpack_from('>I', payload, self.prefix + 4)[0]
        self.original_dtb = payload[self.prefix:self.prefix + self.length]

    def identity(self):
        self.identity_reads += 1
        path = Path(os.environ['IPHONE_LINUX_PROFILE']); folder = path.parent
        if self.fail_candidate and folder != self.folder: raise OSError('Synthetic identity read failure')
        data = json.loads(path.read_text())
        return {'payload': folder / data['payload'], 'initramfs': folder / data['initramfs'],
            'client_key': folder / data['client_key'], 'known_hosts': folder / data['known_hosts'],
            'sha256': data['sha256'], 'initramfs_sha256': data['initramfs_sha256'], 'host_key_alias': data['host_key_alias']}

    def save_report(self):
        (self.directory / 'provenance-private.json').write_text(json.dumps(self.report))

    def invoke(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.subject.compose(self.root, {'source': self.profile, 'calibration': self.directory, 'output': self.output})

    def test_profile_delta_and_real_local_gates_preserve_source(self):
        # Mutations caught: wrong PCI devfn or dropped kernel/initramfs suffix.
        before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        environment = os.environ.get('IPHONE_LINUX_PROFILE'); mask = os.umask(0o027)
        try:
            self.invoke(); observed = os.umask(0o027); self.assertEqual(observed, 0o027)
        finally: os.umask(mask)
        self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'), environment)
        self.assertEqual({p.name: p.read_bytes() for p in self.folder.iterdir()}, before)
        after = {p.name: p.read_bytes() for p in self.output.iterdir()}
        self.assertEqual(set(after), set(before) | {'calibration-private.bin'}); self.assertEqual(after['calibration-private.bin'], BLOB)
        for name in set(before) - {'payload.bin', 'deployment.json', 'provenance.json'}:
            self.assertEqual(after[name], before[name])
        raw = after['payload.bin']; length = struct.unpack_from('>I', raw, self.prefix + 4)[0]
        self.assertEqual(raw[:self.prefix], before['payload.bin'][:self.prefix])
        self.assertEqual(raw[self.prefix + length:], before['payload.bin'][self.prefix + self.length:])
        dtb = raw[self.prefix:self.prefix + length]; nodes = self.subject.DIAGNOSTIC.TOPOLOGY.parse_dtb(dtb)
        self.assertEqual((int.from_bytes(nodes[self.subject.PORT]['reg'][:4], 'big') >> 8) & 255, 8)
        self.assertEqual(nodes[self.subject.WIFI]['reg'], b'\0' * 20)
        self.assertEqual(nodes[self.subject.PCIE]['#address-cells'], struct.pack('>I', 3))
        self.assertEqual(nodes[self.subject.WIFI]['brcm,cal-blob'], BLOB)
        self.subject.validate_dtb(self.original_dtb, dtb, BLOB)
        old = json.loads(before['deployment.json']); new = json.loads(after['deployment.json'])
        old['sha256'] = hashlib.sha256(raw).hexdigest(); self.assertEqual(old, new)
        metadata = json.loads(after['provenance.json'])
        self.assertIs(metadata['pcie_calibration'], True); self.assertEqual(metadata['calibration_blob_sha256'], hashlib.sha256(BLOB).hexdigest())
        self.assertIs(metadata['module_automatic_load'], False); self.assertIs(metadata['default_profile_changed'], False)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.output.iterdir()))
        self.assertEqual(self.identity_reads, 2)

    def test_calibration_scope_and_bytes_refuse_before_identity_output(self):
        # Mutations caught: bypassing source/hash/size guards reaches identity I/O or output.
        for key, value in [('capture_sha256', '0' * 64), ('sha256', '0' * 64), ('physical_acceptance', True),
            ('format', True), ('bytes', '1024'), ('path', '/device-tree/arm-io/wlan')]:
            report = self.report.copy(); self.report[key] = value; self.save_report()
            with self.assertRaises(ValueError): self.invoke()
            self.assertFalse(self.output.exists()); self.assertEqual(self.identity_reads, 0)
            self.report = report
        self.report['sha256'] = hashlib.sha256(BLOB[:-1]).hexdigest()
        self.save_report(); (self.directory / 'calibration-private.bin').write_bytes(BLOB[:-1])
        with self.assertRaises(ValueError): self.invoke()
        self.assertFalse(self.output.exists()); self.assertEqual(self.identity_reads, 0)

    def test_dt_route_and_unrelated_changes_are_refused(self):
        # Mutations caught: omitted node/cell checks or preserved-node equality.
        candidate = self.subject.dtb(self.original_dtb, BLOB)
        nodes = self.subject.DIAGNOSTIC.TOPOLOGY.parse_dtb(candidate)
        for path, key, value in [(self.subject.PCIE, '#address-cells', struct.pack('>I', 2)),
            (self.subject.WIFI, 'status', b'disabled\0'), ('/soc/usb', 'status', b'disabled\0')]:
            changed = {p: dict(v) for p, v in nodes.items()}; changed[path][key] = value
            raw = self.subject.DIAGNOSTIC.DIAGNOSTIC.serialize_dtb(candidate, changed)
            with self.assertRaises(ValueError): self.subject.validate_dtb(self.original_dtb, raw, BLOB)
        self.assertFalse(self.output.exists())

    def test_source_flag_extra_file_and_snapshot_hash_refuse_before_identity(self):
        # Mutations caught: accepting calibrated sources, foreign files or wrong snapshot SHA.
        path = self.folder / 'provenance.json'; original = path.read_bytes(); data = json.loads(original)
        data['pcie_calibration'] = True; path.write_text(json.dumps(data))
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.identity_reads, 0); path.write_bytes(original)
        extra = self.folder / 'foreign'; extra.write_bytes(b'owned'); extra.chmod(0o600)
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.identity_reads, 0); extra.unlink()
        path = self.profile; original = path.read_bytes(); data = json.loads(original); data['sha256'] = '0' * 64
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(self.identity_reads, 0); self.assertFalse(self.output.exists())

    def test_source_topology_and_metadata_budget_refuse(self):
        # Mutations caught: foreign PCI binding or unbounded deployment metadata.
        nodes = self.subject.DIAGNOSTIC.TOPOLOGY.parse_dtb(self.original_dtb)
        altered = {p: dict(v) for p, v in nodes.items()}
        altered[self.subject.PCIE]['compatible'] = b'foreign\0'
        raw = self.subject.DIAGNOSTIC.DIAGNOSTIC.serialize_dtb(self.original_dtb, altered)
        with self.assertRaises(ValueError): self.subject.dtb(raw, BLOB)
        path = self.profile; path.write_bytes(path.read_bytes() + b' ' * 8193)
        with self.assertRaises(ValueError): self.invoke()
        self.assertFalse(self.output.exists()); self.assertEqual(self.identity_reads, 0)

    def test_paths_and_existing_output_preserve_files(self):
        # Mutation caught by the qualified runtime path gate; its unchanged proof is reused.
        self.output.mkdir(mode=0o700); sentinel = self.output / 'owned'; sentinel.write_bytes(b'owned')
        with self.assertRaises(ValueError): self.invoke()
        self.assertEqual(sentinel.read_bytes(), b'owned'); self.assertEqual(self.identity_reads, 0)
        self.output = self.root / 'outside'
        with self.assertRaises(ValueError): self.invoke()
        self.assertFalse(self.output.exists()); self.assertEqual(self.identity_reads, 0)

    def test_candidate_failure_keeps_source_and_restores_environment_umask(self):
        # Mutation caught: missing composition umask restoration after candidate failure.
        self.fail_candidate = True; before = {p.name: p.read_bytes() for p in self.folder.iterdir()}
        environment = os.environ.get('IPHONE_LINUX_PROFILE'); mask = os.umask(0o027)
        try:
            with self.assertRaises(OSError): self.invoke()
            observed = os.umask(0o027); self.assertEqual(observed, 0o027)
        finally: os.umask(mask)
        self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'), environment)
        self.assertEqual({p.name: p.read_bytes() for p in self.folder.iterdir()}, before)
        self.assertTrue(self.output.is_dir()); self.assertEqual(len(list(self.output.iterdir())), 14)


class CalibrationProfileMutationProof(unittest.TestCase):
    def test_source_mutations(self):
        baseline = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(CalibrationProfileTests).run(baseline)
        self.assertFalse(baseline.errors or baseline.failures, 'Complete functional baseline required')
        cases = [
            ('Calibration source or scope differs', 'test_calibration_scope_and_bytes_refuse_before_identity_output'),
            ('Calibration bytes differ from provenance', 'test_calibration_scope_and_bytes_refuse_before_identity_output'),
            ('Exact private calibration length required', 'test_calibration_scope_and_bytes_refuse_before_identity_output'),
            ('Calibration PCI node properties differ', 'test_dt_route_and_unrelated_changes_are_refused'),
            ('Calibration PCI cell counts differ', 'test_dt_route_and_unrelated_changes_are_refused'),
            ('Calibration profile changed preserved DT nodes', 'test_dt_route_and_unrelated_changes_are_refused'),
            ('Uncalibrated diagnostic PCI topology required', 'test_source_topology_and_metadata_budget_refuse'),
            ('Uncalibrated C4 source required', 'test_source_flag_extra_file_and_snapshot_hash_refuse_before_identity'),
            ('Exact thirteen source profile files required', 'test_source_flag_extra_file_and_snapshot_hash_refuse_before_identity'),
            ('Source snapshot hashes differ', 'test_source_flag_extra_file_and_snapshot_hash_refuse_before_identity'),
            ('Source deployment exceeds budget', 'test_source_topology_and_metadata_budget_refuse')]
        for message, method in cases:
            tree = ast.parse(SOURCE.read_text()); matches = []
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'require'
                        and len(node.args) == 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value == message):
                    node.args[0] = ast.Constant(True); matches.append(node)
            self.assertEqual(len(matches), 1, message)
            module = importlib.util.module_from_spec(SPEC)
            exec(compile(ast.fix_missing_locations(tree), str(SOURCE), 'exec'), module.__dict__)
            case = CalibrationProfileTests(method); case.subject = module; result = unittest.TestResult(); case.run(result)
            self.assertFalse(result.errors, 'Infrastructure error is not a kill: ' + message)
            self.assertTrue(result.failures and all('AssertionError' in detail for _, detail in result.failures), message)
        for before, after, method in [
            ('cells(0x800, 0, 0, 0, 0)', 'cells(0x900, 0, 0, 0, 0)', 'test_profile_delta_and_real_local_gates_preserve_source'),
            ('raw[:prefix] + candidate + raw[prefix + length:]', "raw[:prefix] + candidate + b''", 'test_profile_delta_and_real_local_gates_preserve_source'),
            ('os.umask(previous)', 'pass', 'test_candidate_failure_keeps_source_and_restores_environment_umask')]:
            text = SOURCE.read_text(); self.assertEqual(text.count(before), 1)
            module = importlib.util.module_from_spec(SPEC)
            exec(compile(text.replace(before, after, 1), str(SOURCE), 'exec'), module.__dict__)
            case = CalibrationProfileTests(method); case.subject = module; result = unittest.TestResult(); case.run(result)
            self.assertFalse(result.errors, 'Infrastructure error is not a kill: ' + before)
            self.assertTrue(result.failures and all('AssertionError' in detail for _, detail in result.failures), before)
        print('N71_CALIBRATION_PROFILE_ASSERTION_MUTATIONS_OK 14/14')


if __name__ == '__main__':
    unittest.main()
