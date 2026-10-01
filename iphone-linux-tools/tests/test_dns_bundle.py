"""Reject manifest-driven tar scope expansion before any SSH operation."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('DNS_BUNDLE_SOURCE_ROOT', ROOT))
PREFIX = 'srv/data/dns/runtime/'


class DnsBundleTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='dns-bundle-synthetic-')
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name).resolve()
        self.host = self.root / 'scripts/host'
        self.host.mkdir(parents=True)
        for name in ('dns.py', 'lan.py', 'device_profile.py'):
            shutil.copyfile(SOURCE / 'scripts/host' / name, self.host / name)
        (self.root / 'phone/dns').mkdir(parents=True)
        (self.root / 'phone/dns/manage-dns.sh').write_text('SYNTHETIC_MANAGER_NOT_EXECUTED')
        (self.root / 'runtime').mkdir()
        self.archive = self.root / 'runtime/iphone6s-dns-runtime.tar.gz'
        self.manifest = self.root / 'runtime/dns-provenance.json'
        self.commands = self.root / 'commands'
        self.commands.mkdir()
        ssh = self.commands / 'ssh'
        ssh.write_text('#!' + sys.executable + '\nimport sys\nfrom pathlib import Path\nroot=Path('
                       + repr(str(self.root)) + ")\n(root/'ssh-started').touch()\n(root/'received').write_bytes(sys.stdin.buffer.read())\n")
        ssh.chmod(0o700)
        self.environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                PATH=str(self.commands) + os.pathsep + os.environ['PATH'])
        self.environment.pop('IPHONE_LINUX_PROFILE', None)

    def bundle(self, options):
        names = options.get('names', ['libc.so.6'])
        records = options.get('records', [{'name': name, 'sha256': '0' * 64} for name in names])
        members = options.get('members', [PREFIX + 'bin/dnsmasq', PREFIX + 'COPYRIGHT',
                                           PREFIX + 'provenance.json'] + [PREFIX + 'lib/' + name for name in names])
        with tarfile.open(self.archive, 'w:gz') as tar:
            for name in members:
                item = tarfile.TarInfo(name)
                item.mode, item.size = 0o755, 9
                tar.addfile(item, io.BytesIO(b'SYNTHETIC'))
        raw = self.archive.read_bytes()
        report = {'libraries': records, 'bundle_bytes': len(raw),
                  'bundle_sha256': hashlib.sha256(raw).hexdigest()}
        self.manifest.write_text(json.dumps(report))
        return raw

    def cli(self, manifest=None):
        arguments = ['install']
        if manifest is not None:
            arguments += ['--manifest', str(manifest)]
        return subprocess.run([sys.executable, str(self.host / 'dns.py'), *arguments],
                              env=self.environment, capture_output=True, text=True, timeout=5)

    def refused(self, expected):
        result = self.cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(expected, result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.root / 'ssh-started').exists())

    def test_valid_basenames_and_explicit_manifest_transfer_only_verified_bundle(self):
        # Mutation captured: selecting the default manifest instead of the explicit one.
        raw = self.bundle({'names': ['ld-linux-aarch64.so.1', 'libdbus-1.so.3', 'libc.so.6']})
        selected = self.root / 'selected.json'
        shutil.copyfile(self.manifest, selected)
        wrong = json.loads(self.manifest.read_text())
        wrong['bundle_sha256'] = '0' * 64
        self.manifest.write_text(json.dumps(wrong))
        result = self.cli(selected)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'received').read_bytes(), raw)
        self.assertEqual(self.archive.read_bytes(), raw)

    def test_traversal_absolute_nested_alias_and_control_names_refused_before_ssh(self):
        # Mutation captured: trusting manifest names expands the allowed tar path set.
        for name in ('../../../../../../../../root/.ssh/authorized_keys', '/tmp/other',
                     'nested/libc.so.6', './libc.so.6', '..', '.', '', 'libc\n.so.6',
                     'libc\x7f.so.6', 'libc;touch-other', 'libc with-space.so.6'):
            with self.subTest(name=name):
                self.bundle({'names': [name]})
                self.refused('Nome de biblioteca DNS inválido')

    def test_invalid_manifest_list_and_records_have_clear_errors_before_ssh(self):
        # Mutation captured: removing shape checks leaks lookup/type failures instead of a refusal.
        for report in (None, [], {'libraries': None}, {'libraries': 'libc.so.6'},
                       {'libraries': [None]}, {'libraries': ['libc.so.6']},
                       {'libraries': [{}]}, {'libraries': [{'name': 7}]}):
            with self.subTest(report=report):
                self.bundle({})
                self.manifest.write_text(json.dumps(report))
                expected = ('Lista de bibliotecas DNS inválida' if not isinstance(report, dict)
                            or not isinstance(report.get('libraries'), list)
                            else 'Nome de biblioteca DNS inválido')
                self.refused(expected)

    def test_duplicate_library_records_do_not_collapse_into_an_accepted_scope(self):
        # Mutation captured: accepting duplicate records silently narrows the manifest's identity set.
        self.bundle({'records': [{'name': 'libc.so.6'}, {'name': 'libc.so.6'}]})
        self.refused('Nome de biblioteca DNS inválido ou duplicado')

    def test_tar_names_cannot_exceed_the_validated_library_set(self):
        # Mutation captured: dropping the existing archive scope guard accepts undeclared files.
        members = [PREFIX + 'bin/dnsmasq', PREFIX + 'COPYRIGHT', PREFIX + 'provenance.json',
                   PREFIX + 'lib/libc.so.6', PREFIX + 'lib/extra.so.1']
        self.bundle({'members': members})
        self.refused('Escopo/tipo de arquivos do bundle DNS inesperado')

    def test_valid_names_do_not_bypass_bundle_digest(self):
        # Mutation captured: ignoring the bundle hash sends changed bytes to SSH.
        raw = bytearray(self.bundle({}))
        raw[4] ^= 1
        self.archive.write_bytes(raw)
        self.refused('Hash/tamanho do bundle DNS inesperado')


if __name__ == '__main__':
    unittest.main()
