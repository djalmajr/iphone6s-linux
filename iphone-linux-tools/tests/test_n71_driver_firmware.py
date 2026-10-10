"""Private data selection binds exact files to inspected source/certificate pins."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
SOURCE = ROOT / 'scripts/host/n71_driver_firmware.py'
SPEC = importlib.util.spec_from_file_location('firmware_selection', SOURCE)


class FirmwareTests(unittest.TestCase):
    def setUp(self):
        self.subject = getattr(self, 'subject', importlib.util.module_from_spec(SPEC))
        if not hasattr(self.subject, 'select'): SPEC.loader.exec_module(self.subject)
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve(); runtime = self.root / 'runtime'; runtime.mkdir(mode=0o700)
        self.folder = runtime / 'firmware'; self.folder.mkdir(mode=0o700); (self.folder / 'brcm').mkdir(mode=0o700)
        self.values = {name: ('synthetic-' + name).encode() for name, _, _ in self.subject.CATALOG}
        self.catalog = tuple((name, len(data), hashlib.sha256(data).hexdigest()) for name, data in self.values.items())
        self.subject.CATALOG = self.catalog
        for name, data in self.values.items():
            p = self.folder / name; p.write_bytes(data); p.chmod(0o600)
        directory = self.root / 'docs/evidence'; directory.mkdir(parents=True)
        self.fw = json.loads((ROOT / 'docs/evidence/n71-wlan-firmware-origin.json').read_text())
        name, size, sha = self.catalog[0]; self.fw['files'][name].update({'bytes': size, 'sha256': sha})
        self.reg = json.loads((ROOT / 'docs/evidence/n71-regdb-calibration-source-audit.json').read_text())
        for name, size, sha in self.catalog[1:]: self.reg['regdb']['files'][name] = {'bytes': size, 'sha256': sha}
        self.save()
        self.request = {'directory': self.folder, 'release': self.subject.RELEASE}

    def save(self):
        directory = self.root / 'docs/evidence'
        (directory / 'n71-wlan-firmware-origin.json').write_text(json.dumps(self.fw))
        (directory / 'n71-regdb-calibration-source-audit.json').write_text(json.dumps(self.reg))

    def test_exact_order_owned_records_immutable_bytes_and_no_effects(self):
        # Mutation caught: altered hash acceptance or mutable/aliased returned records.
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        pairs = self.subject.select(self.root, self.request)
        self.assertEqual(pairs, [({'path': n, 'bytes': size, 'sha256': sha}, self.values[n]) for n, size, sha in self.catalog])
        self.assertTrue(all(isinstance(blob, bytes) for _, blob in pairs))
        pairs[0][0]['path'] = 'foreign'; self.assertEqual(self.subject.select(self.root, self.request)[0][0]['path'], self.catalog[0][0])
        self.assertEqual({str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)

    def test_source_and_certificate_refusals(self):
        # Mutation caught: bypassing inspected origin, source record, kernel or CMS guards.
        baseline_fw = json.loads(json.dumps(self.fw)); baseline_reg = json.loads(json.dumps(self.reg))
        cases = [('fw', 'commit', '0' * 40), ('fw', 'license_and_whence_inspected', False),
            ('fw', 'firmware_executed', True), ('reg', 'kernel_source_commit', '0' * 40)]
        for target, key, value in cases:
            (self.fw if target == 'fw' else self.reg)[key] = value; self.save()
            with self.assertRaises(ValueError): self.subject.select(self.root, self.request)
            self.fw = json.loads(json.dumps(baseline_fw)); self.reg = json.loads(json.dumps(baseline_reg))
        for key, value in [('kernel_certificate_der_sha256', '0' * 64), ('altered_content_refused', False),
            ('internal_signer_certificate_not_used', False), ('cms_signature_against_explicit_kernel_certificate', False)]:
            self.reg['regdb'][key] = value; self.save()
            with self.assertRaises(ValueError): self.subject.select(self.root, self.request)
            self.reg = json.loads(json.dumps(baseline_reg))
        self.fw['files'][self.catalog[0][0]]['git_blob_id'] = '0' * 40; self.save()
        with self.assertRaises(ValueError): self.subject.select(self.root, self.request)
        self.fw = baseline_fw; self.reg['regdb']['files']['regulatory.db']['sha256'] = '0' * 64; self.save()
        with self.assertRaises(ValueError): self.subject.select(self.root, self.request)

    def test_changed_missing_extra_and_foreign_files_refuse(self):
        # Mutation caught: allowing an unexpected vendor file or ignoring a data hash.
        path = self.folder / self.catalog[0][0]; original = path.read_bytes(); path.write_bytes(b'x' * len(original))
        with self.assertRaises(ValueError): self.subject.select(self.root, self.request)
        path.write_bytes(original); extra = self.folder / 'brcm/foreign.bin'; extra.write_bytes(b'foreign'); extra.chmod(0o600)
        with self.assertRaises(ValueError): self.subject.select(self.root, self.request)
        extra.unlink(); extra = self.folder / 'extra'; extra.write_bytes(b'owned')
        with self.assertRaises(ValueError): self.subject.select(self.root, self.request)
        extra.unlink(); path.unlink()
        with self.assertRaises(ValueError): self.subject.select(self.root, self.request)

    def test_schema_release_paths_links_and_permissions_refuse(self):
        # Mutation caught: disregarding request release or direct runtime scope.
        for request in [dict(self.request, release='foreign'), dict(self.request, extra=True), {},
            dict(self.request, directory=self.root), dict(self.request, directory=self.folder / '..' / 'firmware')]:
            with self.assertRaises(ValueError): self.subject.select(self.root, request)
        outside = self.root / 'outside'; self.folder.rename(outside)
        try:
            with self.assertRaises(ValueError): self.subject.select(self.root, dict(self.request, directory=outside))
        finally:
            outside.rename(self.folder)
        p = self.folder / 'regulatory.db'; p.chmod(0o644)
        with self.assertRaises(ValueError): self.subject.select(self.root, self.request)
        p.chmod(0o600); data = p.read_bytes(); p.unlink(); p.symlink_to(self.folder / 'regulatory.db.p7s')
        with self.assertRaises(ValueError): self.subject.select(self.root, self.request)
        p.unlink(); p.write_bytes(data); p.chmod(0o600)
        link = self.root / 'runtime/linked'; link.symlink_to(self.folder)
        with self.assertRaises(ValueError): self.subject.select(self.root, dict(self.request, directory=link))


class FirmwareMutationProof(unittest.TestCase):
    def test_real_source_mutations(self):
        baseline = unittest.TestResult(); unittest.defaultTestLoader.loadTestsFromTestCase(FirmwareTests).run(baseline)
        self.assertFalse(baseline.errors or baseline.failures)
        cases = [('Official inspected firmware origin required', 'test_source_and_certificate_refusals'),
            ('Pinned firmware source record differs', 'test_source_and_certificate_refusals'),
            ('Regdb kernel binding differs', 'test_source_and_certificate_refusals'),
            ('Explicit kernel-certificate regdb qualification required', 'test_source_and_certificate_refusals'),
            ('Pinned regdb source record differs', 'test_source_and_certificate_refusals'),
            ('Exact firmware selection request required', 'test_schema_release_paths_links_and_permissions_refuse'),
            ('Firmware directory must be private and directly under runtime', 'test_schema_release_paths_links_and_permissions_refuse'),
            ('Exact three-file firmware package required', 'test_changed_missing_extra_and_foreign_files_refuse'),
            ('Foreign firmware refused', 'test_changed_missing_extra_and_foreign_files_refuse'),
            ('Firmware file SHA differs', 'test_changed_missing_extra_and_foreign_files_refuse')]
        for message, method in cases:
            tree = ast.parse(SOURCE.read_text()); matches = []
            for n in ast.walk(tree):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'require'
                        and len(n.args) == 2 and isinstance(n.args[1], ast.Constant) and n.args[1].value == message):
                    n.args[0] = ast.Constant(True); matches.append(n)
            self.assertEqual(len(matches), 1, message)
            module = importlib.util.module_from_spec(SPEC); exec(compile(ast.fix_missing_locations(tree), str(SOURCE), 'exec'), module.__dict__)
            case = FirmwareTests(method); case.subject = module; result = unittest.TestResult(); case.run(result)
            self.assertFalse(result.errors, 'Infrastructure error is not a kill: ' + message)
            self.assertTrue(result.failures and all('AssertionError' in text for _, text in result.failures), message)
        print('N71_FIRMWARE_ASSERTION_MUTATIONS_OK 10/10')


if __name__ == '__main__': unittest.main()
