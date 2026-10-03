"""Exercise wrapper profile selection with synthetic USB and SSH dependencies."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
import test_device_profile as fixtures


class ProfileBootTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DeviceProfileTests('test_valid_profile_and_effective_ssh_identity')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.base = self.fixture.base
        self.project = self.base / 'project'
        self.host = self.project / 'scripts/host'
        shutil.copytree(fixtures.ROOT / 'scripts/host', self.host,
                        ignore=shutil.ignore_patterns('__pycache__'))
        self.commands = self.project / 'bin'
        self.commands.mkdir()
        self.script = self.host / 'iphone-linux.sh'
        self.stub('palera1n-macos-arm64', "raise SystemExit('Synthetic palera must not run in this test')\n")
        source = self.script.read_text()
        source = source.replace('/sbin/ifconfig', str(self.commands / 'ifconfig'))
        source = source.replace('/usr/bin/osascript', str(self.commands / 'osascript'))
        self.script.write_text(source)
        self.stub('ioreg', '''import plistlib,sys,time
(base/'usb-accessed').touch()
if '-a' in sys.argv:
    deadline=time.monotonic()+2
    while not (base/'sent.txt').exists() and not (base/'ssh-fail').exists() and time.monotonic()<deadline:
        time.sleep(0.02)
    sys.stdout.buffer.write(plistlib.dumps([{'IOObjectClass':'IOEthernetInterface','IORegistryEntryName':'en999'}]))
else:
    print('PongoOS USB Device')
''')
        self.stub('ifconfig', "print('inet 172.16.42.2 netmask 0xffffff00')\n")
        self.stub('osascript', "(base/'administrator-prompt').touch()\nraise SystemExit(99)\n")
        self.stub('curl', "(base/'http-accessed').touch()\nraise SystemExit(0)\n")
        self.stub('pongoterm', "import sys\n(base/'sent.txt').write_text(sys.stdin.read())\n")
        self.stub('ssh', '''import json,sys
with (base/'ssh.jsonl').open('a') as file:
    file.write(json.dumps(sys.argv[1:])+'\\n')
raise SystemExit(255 if (base/'ssh-fail').exists() else 0)
''')
        recovery = self.host / 'usb-shell.py'
        recovery.write_text("from pathlib import Path\nPath(" + repr(str(self.base / 'recovery-used')) + ").touch()\n")
        boot = self.project / 'scripts/boot'
        boot.mkdir(parents=True)
        image = self.project / 'artifacts/Pongo.bin'
        image.parent.mkdir()
        image.write_bytes(b'SYNTHETIC_DEFAULT_PONGO')
        helper = (fixtures.ROOT / 'scripts/boot/pongo_select.py').read_text()
        helper = helper.replace('1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575',
                                hashlib.sha256(image.read_bytes()).hexdigest())
        helper = helper.replace('IMAGE_BYTES = 238096', 'IMAGE_BYTES = ' + str(image.stat().st_size))
        (boot / 'pongo_select.py').write_text(helper)
        tool_check = (fixtures.ROOT / 'scripts/boot/boot_tools.py').read_text()
        for name, pin in (
                ('palera1n-macos-arm64', (4874592, '950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9')),
                ('pongoterm', (53608, 'ad4d66f1e2908090cc52a07ce5a58076b5ae877bb3d50b2a8d8e267b63113a56'))):
            path = self.commands / name
            tool_check = tool_check.replace(repr(pin), repr((path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())))
        (boot / 'boot_tools.py').write_text(tool_check)
        self.environment = dict(self.fixture.environment,
                                PATH=str(self.commands) + os.pathsep + os.environ['PATH'])

    def stub(self, name, body):
        path = self.commands / name
        path.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nbase=Path('
                        + repr(str(self.base)) + ')\n' + body)
        path.chmod(0o700)

    def run_cli(self, arguments):
        return subprocess.run(['/bin/bash', str(self.script), *arguments], env=self.environment,
                              capture_output=True, text=True, timeout=15)

    def untouched(self):
        for name in ('usb-accessed', 'sent.txt', 'administrator-prompt', 'recovery-used'):
            self.assertFalse((self.base / name).exists(), name)
        self.assertFalse((self.project / 'runtime/dfu-active').exists())

    def test_valid_profile_sends_selected_payload_and_uses_selected_ssh_identity(self):
        # Mutation killed: replacing the selected wrapper host key alias.
        result = self.run_cli(['boot'])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PROFILE_IMAGE_IDENTITIES_OK', result.stdout)
        self.assertEqual((self.base / 'sent.txt').read_text(),
                         '/send ' + str(self.base / 'payload.bin') + '\nbootm\n')
        calls = [json.loads(line) for line in (self.base / 'ssh.jsonl').read_text().splitlines()]
        self.assertGreaterEqual(len(calls), 3)
        for call in calls:
            self.assertIn('HostKeyAlias=candidate-test', call)
            self.assertIn('UserKnownHostsFile=' + str(self.base / 'known_hosts'), call)
            self.assertIn('StrictHostKeyChecking=yes', call)
            self.assertIn('ForwardAgent=no', call)
            self.assertEqual(call[call.index('-i') + 1], str(self.base / 'client'))
        self.assertFalse((self.project / 'keys').exists())
        self.assertFalse((self.base / 'administrator-prompt').exists())

    def test_invalid_selector_and_incompatible_commands_abort_before_usb(self):
        # Mutation killed: skipping explicit profile selection at wrapper startup.
        for selector in ('', str(self.base / 'absent.json')):
            self.environment['IPHONE_LINUX_PROFILE'] = selector
            for command in ('boot', 'status', 'shell', 'backup', 'lan', 'dns'):
                result = self.run_cli([command])
                self.assertEqual(result.returncode, 1, result.stderr)
                self.untouched()
        self.environment = dict(self.fixture.environment,
                                PATH=str(self.commands) + os.pathsep + os.environ['PATH'])
        for command in ('boot-probe', 'install-terminal'):
            result = self.run_cli([command])
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn('comando incompatível recusado', result.stderr)
            self.untouched()

    def test_image_or_identity_mismatch_aborts_before_usb(self):
        # Mutation killed: dropping candidate preflight before any USB access.
        path = self.base / 'payload.bin'
        original = path.read_bytes()
        path.write_bytes(b'X' + original[1:])
        result = self.run_cli(['boot'])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('Hash da imagem', result.stderr)
        self.untouched()
        path.write_bytes(original)
        self.fixture.data['client_key'] = 'other'
        self.fixture.save()
        result = self.run_cli(['boot'])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('Chave cliente não corresponde', result.stderr)
        self.untouched()
        self.fixture.data['client_key'] = 'client'
        self.fixture.save()
        self.fixture.write_pin((self.base / 'client.pub').read_text().split()[:2])
        result = self.run_cli(['boot'])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('Pin do servidor não corresponde', result.stderr)
        self.untouched()

    def test_profile_ssh_failure_refuses_recovery_but_default_probe_keeps_it(self):
        # Mutation killed: allowing recovery fallback after selected SSH authentication fails.
        (self.base / 'ssh-fail').touch()
        command = ['/bin/bash', '-c', 'source "$0" connect; printf "echo test\\n" | remote', str(self.script)]
        result = subprocess.run(command, env=self.environment, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('terminal de recuperação não será usado', result.stderr)
        self.assertFalse((self.base / 'recovery-used').exists())
        keys = self.project / 'keys'
        keys.mkdir(mode=0o700)
        shutil.copy(self.base / 'client', keys / 'iphone_ed25519')
        self.environment.pop('IPHONE_LINUX_PROFILE')
        result = subprocess.run(command, env=self.environment, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.base / 'recovery-used').is_file())

    def test_profile_ssh_failure_refuses_untrusted_http(self):
        # Mutation killed: accepting HTTP success before authenticating the selected SSH identity.
        (self.base / 'ssh-fail').touch()
        result = self.run_cli(['serve'])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('HTTP não comprova a identidade', result.stderr)
        self.assertFalse((self.base / 'http-accessed').exists())


if __name__ == '__main__':
    unittest.main()
