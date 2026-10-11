"""Wi-Fi bundle source binding, virtual archive paths and isolated ELF closure."""
import ast
import hashlib
import io
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import tempfile
from types import ModuleType
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/build'))
import n71_wifi_userspace as SUBJECT
SOURCE = ROOT / 'scripts/build/n71_wifi_userspace.py'
DYNAMIC = 'Dynamic section at offset 0x100\n  (NEEDED) Shared library: [libc.so.6]\n'


class WifiUserspaceTests(unittest.TestCase):
    subject = SUBJECT

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        self.packages = self.root / 'packages'; self.packages.mkdir(mode=0o700)
        (self.root / 'runtime').mkdir(mode=0o700)

    def test_host_scope_refuses_mac_and_other_architectures(self):
        # Mutation captured: accepting any host enables the Linux builder on the Mac.
        self.subject.validate_host('Linux', 'aarch64')
        for system, machine in [('Darwin', 'arm64'), ('Linux', 'x86_64')]:
            with self.assertRaises(ValueError): self.subject.validate_host(system, machine)

    def test_manifest_binds_exact_qualified_bytes(self):
        # Mutation captured: omitting the digest accepts a reformatted foreign manifest.
        raw = (ROOT / SUBJECT.PINS).read_bytes()
        self.assertEqual(len(self.subject.pins(raw)), 38)
        with self.assertRaises(ValueError): self.subject.pins(raw + b'\n')

    def test_output_is_new_and_scoped_to_runtime(self):
        # Mutation captured: removing output parent scope accepts another private directory.
        request = {'packages': self.packages, 'output': self.root / 'runtime/new'}
        self.subject.paths(self.root, request)
        outside = self.root / 'outside'; outside.mkdir(mode=0o700)
        with self.assertRaises(ValueError):
            self.subject.paths(self.root, dict(request, output=outside / 'new'))
        request['output'].mkdir(mode=0o700)
        with self.assertRaises(ValueError): self.subject.paths(self.root, request)

    def package_fixture(self):
        raw = b'authenticated package bytes'
        path = self.packages / 'fixture_1_arm64.deb'; path.write_bytes(raw); path.chmod(0o600)
        row = {'package': 'fixture', 'downloaded_filename': path.name,
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        self.assertEqual(self.subject.packages(self.packages, [row]), [('fixture', raw)])
        return path, row

    def test_package_hash_rejects_same_length_tamper(self):
        # Mutation captured: removing SHA binding accepts modified package content.
        path, row = self.package_fixture()
        path.write_bytes(b'X' + path.read_bytes()[1:])
        with self.assertRaises(ValueError): self.subject.packages(self.packages, [row])

    def test_package_size_rejects_wrong_index_length(self):
        # Mutation captured: ignoring index size accepts a coherent digest with a false length.
        _, row = self.package_fixture()
        row['bytes'] += 1
        with self.assertRaises(ValueError): self.subject.packages(self.packages, [row])

    def archive(self, name):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            entry = tarfile.TarInfo(name); entry.size = 3
            archive.addfile(entry, io.BytesIO(b'raw'))
        return stream.getvalue()

    def test_archive_selects_data_without_allowing_parent_traversal(self):
        # Mutation captured: skipping traversal checks silently accepts an escaping unused entry.
        entries = self.subject.catalog(self.archive('./usr/sbin/iw'), 'iw')
        self.assertEqual(entries, {'usr/sbin/iw': ('file', b'raw', 'iw')})
        with self.assertRaises(ValueError): self.subject.catalog(self.archive('../../escape'), 'iw')
        self.assertEqual(self.subject.catalog(self.archive('./etc/unused'), 'iw'), {})

    def test_aliases_cycles_and_conflicting_library_bodies(self):
        # Mutation captured: ignoring body collisions selects an arbitrary conflicting library.
        prefix = 'usr/lib/aarch64-linux-gnu/'
        entries = {prefix + 'real.so.1': ('file', b'one', 'owner'),
            prefix + 'alias.so.1': ('link', prefix + 'real.so.1', 'owner')}
        self.assertEqual(self.subject.resolve(entries, prefix + 'alias.so.1'), (b'one', 'owner'))
        self.assertEqual(self.subject.library(entries, 'alias.so.1'), (b'one', 'owner'))
        entries[prefix + 'cycle.so.1'] = ('link', prefix + 'cycle.so.1', 'owner')
        with self.assertRaises(ValueError): self.subject.resolve(entries, prefix + 'cycle.so.1')
        entries['lib/aarch64-linux-gnu/real.so.1'] = ('file', b'two', 'other')
        with self.assertRaises(ValueError): self.subject.library(entries, 'real.so.1')

    def test_elf_machine_and_dynamic_search_paths(self):
        # Mutation captured: removing AArch64 binding accepts a foreign executable.
        raw = bytearray(64); raw[:7] = b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HH', raw, 16, 3, 183)
        self.subject.validate_elf(raw)
        struct.pack_into('<H', raw, 18, 62)
        with self.assertRaises(ValueError): self.subject.validate_elf(raw)

    def test_rpath_and_needed_names_remain_inside_the_bundle(self):
        # Mutation captured: allowing RUNPATH or a nonlocal NEEDED name escapes the isolated closure.
        self.assertEqual(self.subject.dynamic(DYNAMIC), {'needed': ['libc.so.6'], 'interpreter': []})
        with self.assertRaises(ValueError): self.subject.dynamic(DYNAMIC + '(RUNPATH) Library runpath: [/tmp]\n')
        with self.assertRaises(ValueError): self.subject.dynamic(DYNAMIC.replace('libc.so.6', '../foreign.so'))

    @unittest.skipUnless(sys.platform == 'darwin', 'Real Mac host refusal gate')
    def test_cli_refuses_mac_without_creating_output(self):
        # Mutation captured by the host-scope mutation above; this also checks the real CLI wiring.
        target = self.root / 'runtime/mac-refused'
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build/build-n71-wifi-userspace.py'),
            '--package-dir', str(self.packages), '--output-dir', str(target)], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('dedicated Linux/aarch64 VM', result.stderr)
        self.assertFalse(target.exists())


class WifiUserspaceMutations(unittest.TestCase):
    def test_boundary_mutations_fail_by_assertion(self):
        source = SOURCE.read_text()
        mutations = [
            ('host', "system == 'Linux' and machine == 'aarch64'", 'True', 'test_host_scope_refuses_mac_and_other_architectures'),
            ('manifest', 'hashlib.sha256(raw).hexdigest() == PINS_SHA256', 'True', 'test_manifest_binds_exact_qualified_bytes'),
            ('output-scope', "output.parent == root / 'runtime'", 'True', 'test_output_is_new_and_scoped_to_runtime'),
            ('package-sha', "hashlib.sha256(raw).hexdigest() == row['sha256']", 'True', 'test_package_hash_rejects_same_length_tamper'),
            ('package-size', "path.stat().st_size == row['bytes']", 'True', 'test_package_size_rejects_wrong_index_length'),
            ('archive-traversal', "'..' not in path.parts", 'True', 'test_archive_selects_data_without_allowing_parent_traversal'),
            ('library-collision', 'len({hashlib.sha256(raw).hexdigest() for raw, _ in candidates}) == 1', 'True',
                'test_aliases_cycles_and_conflicting_library_bodies'),
            ('elf-machine', "struct.unpack_from('<H', raw, 18)[0] == 183", 'True', 'test_elf_machine_and_dynamic_search_paths'),
            ('rpath', "'(RPATH)' not in text and '(RUNPATH)' not in text", 'True', 'test_rpath_and_needed_names_remain_inside_the_bundle'),
            ('needed-name', "all(re.fullmatch('[A-Za-z0-9_.+-]+', name) for name in needed)", 'True',
                'test_rpath_and_needed_names_remain_inside_the_bundle'),
        ]
        for name, before, after, method in mutations:
            self.assertEqual(source.count(before), 1, name)
            subject = ModuleType('wifi_userspace_mutant')
            exec(compile(ast.parse(source.replace(before, after, 1)), str(SOURCE), 'exec'), subject.__dict__)
            case = type('MutatedWifiUserspaceTests', (WifiUserspaceTests,), {'subject': subject})
            result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
            self.assertEqual(result.errors, [], name)
            self.assertGreater(len(result.failures), 0, name)
            print('N71_WIFI_USERSPACE_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
