"""Observable profile CLI boundaries using temporary synthetic identities."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/device_profile.py'


def entry(options):
    name = options['name'].encode() + b'\0'
    body = options.get('body', b'')
    fields = [1, options.get('mode', 0), options.get('uid', 0), 0,
              options.get('links', 1), 0, len(body), 0, 0, 0, 0, len(name), 0]
    header = b'070701' + ''.join(f'{value:08x}' for value in fields).encode()
    result = header + name
    result += b'\0' * (-len(result) % 4)
    result += body
    result += b'\0' * (-len(result) % 4)
    return result


class DeviceProfileTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='profile-synthetic-')
        self.base = Path(self.work.name).resolve()
        self.base.chmod(0o700)
        for name in ('client', 'other'):
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '',
                            '-C', 'synthetic-profile-test', '-f', str(self.base / name)], check=True)
        self.client = (self.base / 'client.pub').read_bytes()
        self.server = (self.base / 'other.pub').read_text().split()[:2]
        public = base64.b64decode(self.server[1])[-32:]
        self.host = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 64) + b's' * 32 + public
        self.members = [
            {'name': 'root', 'mode': stat.S_IFDIR | 0o700},
            {'name': 'root/.ssh', 'mode': stat.S_IFDIR | 0o700},
            {'name': 'root/.ssh/authorized_keys', 'mode': stat.S_IFREG | 0o600, 'body': self.client},
            {'name': 'etc/dropbear/dropbear_ed25519_host_key', 'mode': stat.S_IFREG | 0o600, 'body': self.host},
            {'name': 'init', 'mode': stat.S_IFREG | 0o755, 'body': b'#!/bin/sh\nip link set lo up\n/usr/local/sbin/start-terminal\n'},
        ]
        self.data = {'format': 1, 'payload': 'payload.bin', 'sha256': '', 'initramfs': 'initramfs.gz',
                     'initramfs_sha256': '', 'client_key': 'client', 'known_hosts': 'known_hosts',
                     'host_key_alias': 'candidate-test'}
        self.write_pin(self.server)
        self.write_image()
        self.environment = dict(os.environ, IPHONE_LINUX_PROFILE=str(self.base / 'profile.json'))

    def tearDown(self):
        self.work.cleanup()

    def save(self):
        path = self.base / 'profile.json'
        path.write_text(json.dumps(self.data))
        path.chmod(0o600)

    def write_pin(self, key):
        path = self.base / 'known_hosts'
        path.write_text('candidate-test ' + ' '.join(key) + '\n')
        path.chmod(0o600)

    def write_image(self, extra=b''):
        raw = b''.join(entry(member) for member in self.members)
        raw += entry({'name': 'TRAILER!!!'}) + extra
        compressed = gzip.compress(raw)
        payload = b'SYNTHETIC_NONEXECUTABLE_PREFIX' + compressed
        for name, body in [('initramfs.gz', compressed), ('payload.bin', payload)]:
            path = self.base / name
            path.write_bytes(body)
            path.chmod(0o600)
        self.data['sha256'] = hashlib.sha256(payload).hexdigest()
        self.data['initramfs_sha256'] = hashlib.sha256(compressed).hexdigest()
        self.save()

    def run_cli(self, command='check'):
        return subprocess.run([sys.executable, str(SOURCE), command], env=self.environment,
                              capture_output=True, text=True, timeout=10)

    def refuse(self, message):
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)
        self.assertNotIn('PROFILE_IMAGE_IDENTITIES_OK', result.stdout)

    def test_valid_profile_and_effective_ssh_identity(self):
        # Mutation killed: disabling strict host pin checking.
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PROFILE_IMAGE_IDENTITIES_OK', result.stdout)
        config = self.run_cli('ssh-config')
        self.assertEqual(config.returncode, 0, config.stderr)
        values = dict(line.split(' ', 1) for line in config.stdout.splitlines())
        self.assertEqual(values['hostname'], '172.16.42.1')
        self.assertEqual(values['hostkeyalias'], 'candidate-test')
        self.assertEqual(values['identityfile'], str(self.base / 'client'))
        self.assertEqual(values['userknownhostsfile'], str(self.base / 'known_hosts'))
        self.assertEqual(values['globalknownhostsfile'], '/dev/null')
        self.assertIn(values['stricthostkeychecking'], ('true', 'yes'))
        self.assertIn(values['forwardagent'], ('false', 'no'))

    def test_explicit_invalid_selection_never_falls_back(self):
        # Mutation killed: falling back when an explicit selector is empty.
        for selection in ('', str(self.base / 'absent.json')):
            self.environment['IPHONE_LINUX_PROFILE'] = selection
            result = self.run_cli('fields')
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')

    def test_invalid_schema_paths_and_aliases_fail_closed(self):
        # Mutation killed: accepting a boolean as the profile format number.
        original = dict(self.data)
        cases = [('format', True), ('payload', '../outside'), ('payload', '.'),
                 ('payload', '/etc/passwd'), ('payload', 'payload.bin\ncommand'),
                 ('host_key_alias', '-oProxyCommand=command'), ('sha256', 'g' * 64)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self.data = dict(original, **{field: value})
                self.save()
                self.refuse('Perfil inválido:')

    def test_private_files_links_and_directory_permissions(self):
        # Mutation killed: bypassing private file and directory checks.
        for target in ('profile.json', 'client', 'known_hosts', 'payload.bin'):
            path = self.base / target
            path.chmod(0o644)
            self.refuse('arquivos próprios privados')
            path.chmod(0o600)
        self.base.chmod(0o755)
        self.refuse('arquivos próprios privados')
        self.base.chmod(0o700)
        path = self.base / 'linked'
        path.symlink_to('payload.bin')
        self.data['payload'] = 'linked'
        self.save()
        self.refuse('arquivos próprios privados')
        path.unlink()
        os.link(self.base / 'payload.bin', path)
        self.refuse('arquivos próprios privados')

    def test_changed_hash_and_mixed_payload_are_rejected(self):
        # Mutations killed: bypassing payload hashing or initramfs binding.
        path = self.base / 'payload.bin'
        original = path.read_bytes()
        path.write_bytes(b'X' + original[1:])
        self.refuse('Hash da imagem')
        path.write_bytes(original + b'changed')
        self.data['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save()
        self.refuse('Payload e initramfs')

    def test_client_and_server_identities_must_match_image(self):
        # Mutations killed: bypassing embedded client authorization or server pin binding.
        self.data['client_key'] = 'other'
        self.save()
        self.refuse('Chave cliente não corresponde')
        self.data['client_key'] = 'client'
        self.save()
        self.write_pin((self.base / 'client.pub').read_text().split()[:2])
        self.refuse('Pin do servidor não corresponde')

    def test_unsafe_embedded_permissions_and_duplicate_identity(self):
        # Mutation killed: bypassing embedded identity permission checks.
        for field, value in [('mode', stat.S_IFREG | 0o644), ('uid', 1000), ('links', 2)]:
            old = self.members[2].get(field)
            self.members[2][field] = value
            self.write_image()
            self.refuse('Permissões ou identidade inseguras')
            if old is None:
                del self.members[2][field]
            else:
                self.members[2][field] = old
        self.members.append(dict(self.members[2]))
        self.write_image()
        self.refuse('Caminho duplicado')

    def test_additional_archive_and_unsupported_init_are_rejected(self):
        # Mutations killed: accepting another archive after the trailer or allowing Telnet.
        self.write_image(extra=entry(self.members[2]))
        self.refuse('dados adicionais')
        self.members[-1]['body'] += b'telnetd\n'
        self.write_image()
        self.refuse('sem Telnet')
