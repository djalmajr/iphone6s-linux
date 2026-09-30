"""LAN validation and opt-in real OpenSSH/Dropbear forwarding proof."""
import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/lan.py'
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location('lan', SOURCE)
lan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lan)


class LanTests(unittest.TestCase):
    def test_invalid_bind_and_ports_fail_before_keys_or_network(self):
        # Mutation captured: allowing public/wildcard/USB binds widens exposure.
        cases = [['--bind', value] for value in
                 ('0.0.0.0', '*', '::1', '8.8.8.8', '169.254.1.1', '172.16.42.2', '127.0.0.2', 'not-an-ip')]
        cases += [['--bind', '127.0.0.1', '--ssh-port', value] for value in ('22', '65536', '0')]
        cases += [['--bind', '127.0.0.1', '--ssh-port', '8086'], []]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = subprocess.run([sys.executable, str(SOURCE)] + arguments, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn('usage:', result.stderr)
                self.assertNotIn('Identidade SSH dedicada ausente', result.stderr)

    def test_real_openssh_config_has_only_explicit_forwarding_and_strict_identity(self):
        # Mutation captured: dropping strict checking, bind or fail-on-listen changes effective security policy.
        options = argparse.Namespace(bind='192.168.12.34', ssh_port=2222, http_port=8086)
        command = lan.forward_command(options)
        result = subprocess.run([command[0], '-G'] + command[1:], capture_output=True, text=True, check=True, timeout=5)
        records = {}
        for line in result.stdout.splitlines():
            key, value = line.split(' ', 1)
            records.setdefault(key, []).append(value)
        self.assertIn(records['stricthostkeychecking'][0], ('true', 'yes'))
        for key in ('batchmode', 'identitiesonly', 'exitonforwardfailure'):
            self.assertIn(records[key][0], ('true', 'yes'))
        for key in ('forwardagent', 'forwardx11'):
            self.assertIn(records[key][0], ('false', 'no'))
        self.assertEqual([value.replace('[', '').replace(']', '') for value in records['localforward']], ['192.168.12.34:2222 172.16.42.1:22', '192.168.12.34:8086 172.16.42.1:8080'])
        self.assertNotIn('remoteforward', records)
        self.assertNotIn('dynamicforward', records)
        self.assertEqual(records['serveraliveinterval'], ['5'])
        self.assertEqual(records['serveralivecountmax'], ['3'])


def wait_socket(address, process):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError('Fixture process exited before listener was ready')
        try:
            with socket.create_connection(address, timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError('Fixture listener did not become ready')


def assert_closed(address):
    try:
        connection = socket.create_connection(address, timeout=0.5)
    except OSError:
        return
    connection.close()
    raise AssertionError('Unexpected listener at ' + repr(address))


def copy_binary(binary, root):
    names = {binary}
    libraries = subprocess.check_output(['ldd', binary], text=True)
    names.update(re.findall(r'/[^\s()]+', libraries))
    for name in names:
        target = root / name.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(name, target)


def namespace_case():
    # Mutation captured: removing explicit bind or ExitOnForwardFailure widens/leaves listeners; disabling strict trust accepts a wrong host.
    with tempfile.TemporaryDirectory(prefix='iphone-lan-test-') as temporary:
        base = Path(temporary)
        root = base / 'phone'
        project = base / 'project'
        host = project / 'scripts/host'
        keys = project / 'keys'
        host.mkdir(parents=True)
        keys.mkdir(mode=0o700)
        shutil.copy(SOURCE, host / 'lan.py')
        shutil.copy(SOURCE.parent / 'device_profile.py', host / 'device_profile.py')
        processes = []
        output = (base / 'fixture.log').open('w+')
        try:
            subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
            for address in ('172.16.42.1/32', '10.240.0.1/32', '10.240.0.2/32'):
                subprocess.run(['ip', 'addr', 'add', address, 'dev', 'lo'], check=True)
            for directory in ('bin', 'etc/dropbear', 'root/.ssh', 'dev', 'srv/iphone', 'var/run', 'tmp'):
                (root / directory).mkdir(parents=True, exist_ok=True)
            shutil.copy('/usr/bin/busybox', root / 'bin/busybox')
            (root / 'bin/sh').symlink_to('busybox')
            copy_binary('/usr/sbin/dropbear', root)
            shell = root / 'bin/fixture-shell'
            shell.write_text('#!/bin/sh\nprintf "%s\\n" command >> /var/run/ssh-command-events\nexec /bin/sh "$@"\n')
            shell.chmod(0o755)
            (root / 'etc/passwd').write_text('root:x:0:0:fixture:/root:/bin/fixture-shell\n')
            (root / 'etc/shells').write_text('/bin/sh\n/bin/fixture-shell\n')
            (root / 'etc/group').write_text('root:x:0:\n')
            (root / 'etc/shadow').write_text('root:*:20000:0:99999:7:::\n')
            os.mknod(root / 'dev/null', 0o20666, os.makedev(1, 3))
            key = keys / 'iphone_ed25519'
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'synthetic-lan-test', '-f', str(key)], check=True)
            authorized = root / 'root/.ssh/authorized_keys'
            authorized.write_bytes(key.with_suffix('.pub').read_bytes())
            authorized.chmod(0o600)
            (root / 'root').chmod(0o700)
            (root / 'root/.ssh').chmod(0o700)
            hostkey = root / 'etc/dropbear/key'
            subprocess.run(['dropbearkey', '-t', 'ed25519', '-f', str(hostkey)], check=True, stdout=output, stderr=output)
            public = subprocess.check_output(['dropbearkey', '-y', '-f', str(hostkey)], text=True)
            line = next(line for line in public.splitlines() if line.startswith('ssh-ed25519 '))
            known = keys / 'known_hosts'
            alias = '172.16.42.1'
            environment = dict(os.environ)
            environment.pop('IPHONE_LINUX_PROFILE', None)
            if os.environ.get('IPHONE_LAN_PROFILE_CASE') == '1':
                alias = 'candidate-vm-test'
                selected = keys / 'profile-client'
                key.rename(selected)
                key.with_suffix('.pub').rename(selected.with_suffix('.pub'))
                key = selected
                data = b'SYNTHETIC_TRANSPORT_ONLY_NOT_BOOTABLE'
                for name in ('payload.bin', 'initramfs.gz'):
                    path = keys / name
                    path.write_bytes(data)
                    path.chmod(0o600)
                profile = keys / 'deployment.json'
                profile.write_text(json.dumps({'format': 1, 'payload': 'payload.bin',
                    'sha256': hashlib.sha256(data).hexdigest(), 'initramfs': 'initramfs.gz',
                    'initramfs_sha256': hashlib.sha256(data).hexdigest(),
                    'client_key': 'profile-client', 'known_hosts': 'known_hosts',
                    'host_key_alias': alias}))
                profile.chmod(0o600)
                environment['IPHONE_LINUX_PROFILE'] = str(profile)
            known.write_text(alias + ' ' + line + '\n')
            known.chmod(0o600)
            (root / 'srv/iphone/proof').write_text('VM_FORWARD_HTTP_OK\n')
            server = subprocess.Popen(['chroot', str(root), '/usr/sbin/dropbear', '-F', '-E', '-s', '-p', '172.16.42.1:22', '-r', '/etc/dropbear/key'], stdout=output, stderr=output)
            processes.append(server)
            http = subprocess.Popen(['chroot', str(root), '/bin/busybox', 'httpd', '-f', '-p', '172.16.42.1:8080', '-h', '/srv/iphone'], stdout=output, stderr=output)
            processes.append(http)
            wait_socket(('172.16.42.1', 22), server)
            wait_socket(('172.16.42.1', 8080), http)
            command = [sys.executable, str(host / 'lan.py'), '--bind', '10.240.0.1']
            forward = subprocess.Popen(command, env=environment, stdout=output, stderr=output)
            processes.append(forward)
            wait_socket(('10.240.0.1', 8086), forward)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open('http://10.240.0.1:8086/proof', timeout=5) as response:
                assert response.read() == b'VM_FORWARD_HTTP_OK\n'
            client = ['ssh', '-4', '-F', '/dev/null', '-i', str(key), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(known), '-o', 'HostKeyAlias=' + alias, '-p', '2222', 'root@10.240.0.1']
            result = subprocess.run(client + ['printf VM_FORWARD_SSH_OK'], capture_output=True, text=True, timeout=5)
            assert result.returncode == 0 and result.stdout == 'VM_FORWARD_SSH_OK', result.stderr
            for address in ('127.0.0.1', '10.240.0.2'):
                for port in (2222, 8086):
                    assert_closed((address, port))
            forward.terminate()
            forward.wait(timeout=5)
            for port in (2222, 8086):
                assert_closed(('10.240.0.1', port))
            with socket.socket() as occupied:
                occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                occupied.bind(('10.240.0.1', 8086))
                occupied.listen()
                conflict = subprocess.Popen(command, env=environment, stdout=output, stderr=output)
                processes.append(conflict)
                assert conflict.wait(timeout=5) != 0
                assert_closed(('10.240.0.1', 2222))
                assert occupied.getsockname() == ('10.240.0.1', 8086)
            # Wrong host key must be refused by the production preflight, not silently replaced.
            events = root / 'var/run/ssh-command-events'
            before = events.read_bytes()
            known.write_text(alias + ' ' + key.with_suffix('.pub').read_text())
            refused = subprocess.Popen(command, env=environment, stdout=output, stderr=output)
            processes.append(refused)
            try:
                code = refused.wait(timeout=5)
            except subprocess.TimeoutExpired:
                raise AssertionError('Untrusted SSH session stayed active') from None
            assert code != 0
            assert events.read_bytes() == before, 'Untrusted host executed a remote command'
            for port in (2222, 8086):
                assert_closed(('10.240.0.1', port))
            print('VM_FORWARD_HTTP_OK VM_FORWARD_SSH_OK; explicit bind, conflict, strict trust and cleanup passed')
        except BaseException:
            output.flush()
            output.seek(0)
            print(output.read(), file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            output.close()


@unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0
                     and os.environ.get('IPHONE_LAN_VM_TESTS') == '1',
                     'requires explicit disposable Linux VM/root opt-in')
class LanVmTests(unittest.TestCase):
    def test_real_forwarding_security_and_cleanup_in_owned_namespace(self):
        result = subprocess.run(['unshare', '--net', sys.executable, str(Path(__file__).resolve()), '--namespace-case'], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('VM_FORWARD_HTTP_OK VM_FORWARD_SSH_OK', result.stdout)

    def test_real_profile_forwarding_uses_selected_alias_and_client(self):
        # Mutation killed in the VM: replacing the selected alias prevents authenticated forwarding.
        environment = dict(os.environ, IPHONE_LAN_PROFILE_CASE='1')
        result = subprocess.run(['unshare', '--net', sys.executable, str(Path(__file__).resolve()), '--namespace-case'],
                                env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('VM_FORWARD_HTTP_OK VM_FORWARD_SSH_OK', result.stdout)


if __name__ == '__main__':
    if sys.argv[1:] == ['--namespace-case']:
        namespace_case()
    else:
        unittest.main()
