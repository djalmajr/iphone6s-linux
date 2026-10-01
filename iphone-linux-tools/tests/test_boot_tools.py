"""Prevent modified host boot tools from executing, using synthetic programs."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('BOOT_TOOLS_SOURCE_ROOT', ROOT))
PINS = {
    'palera1n-macos-arm64': (4874592, '950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9'),
    'pongoterm': (53608, 'ad4d66f1e2908090cc52a07ce5a58076b5ae877bb3d50b2a8d8e267b63113a56'),
}


class BootToolTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='boot-tools-synthetic-')
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name).resolve()
        self.boot = self.root / 'scripts/boot'
        self.boot.mkdir(parents=True)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.stub('palera1n-macos-arm64', "import os,time\n(root/'palera-executed').write_text(str(os.getpid()))\nwhile True: time.sleep(1)")
        self.stub('pongoterm', "(root/'pongoterm-executed').touch()")
        text = (SOURCE / 'scripts/boot/boot_tools.py').read_text()
        for name, pin in PINS.items():
            data = (self.bin / name).read_bytes()
            text = text.replace(repr(pin), repr((len(data), hashlib.sha256(data).hexdigest())))
        self.helper = self.boot / 'boot_tools.py'
        self.helper.write_text(text)
        for name in ('dfu_boot.py', 'dfu_state.py', 'pongo_select.py'):
            shutil.copyfile(SOURCE / 'scripts/boot' / name, self.boot / name)
        pongo = self.root / 'artifacts/Pongo.bin'
        pongo.parent.mkdir()
        pongo.write_bytes(b'SYNTHETIC_PONGO'.ljust(238096, b'P'))
        selector = self.boot / 'pongo_select.py'
        selector.write_text(selector.read_text().replace(
            '1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575',
            hashlib.sha256(pongo.read_bytes()).hexdigest()))
        payload = self.root / 'artifacts/m1n1-linux-iphone6s-loopback-server.bin'
        payload.write_bytes(b'SYNTHETIC_NONBOOTABLE_PAYLOAD')
        host = self.root / 'scripts/host'
        host.mkdir()
        self.wrapper = host / 'iphone-linux.sh'
        text = (SOURCE / 'scripts/host/iphone-linux.sh').read_text().replace(
            '8b1a46dd67613c63aa6608dd3a0e73a73b358aaddc1818b423ff6009b55e3f66',
            hashlib.sha256(payload.read_bytes()).hexdigest())
        text = text.replace('/sbin/ifconfig', str(self.bin / 'ifconfig'))
        text = text.replace('/usr/bin/osascript', str(self.bin / 'osascript'))
        self.wrapper.write_text(text)
        self.stub('ioreg', "import plistlib,sys\n(root/'usb-accessed').touch()\nif '-a' in sys.argv: sys.stdout.buffer.write(plistlib.dumps([{'IOObjectClass':'IOEthernetInterface','IORegistryEntryName':'en999'}]))\nelse: print('PongoOS USB Device')")
        self.stub('ifconfig', "print('inet 172.16.42.2 netmask 0xffffff00')")
        self.stub('osascript', "(root/'admin-attempted').touch()\nraise SystemExit(99)")
        self.stub('ssh', 'raise SystemExit(0)')
        self.stub('curl', 'raise SystemExit(0)')
        (self.root / 'keys').mkdir()
        (self.root / 'keys/iphone_ed25519').write_text('SYNTHETIC_NOT_A_KEY')
        self.environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        for name in ('IPHONE_LINUX_PONGO', 'IPHONE_LINUX_PROFILE'):
            self.environment.pop(name, None)
        spec = importlib.util.spec_from_file_location('synthetic_boot_tools', self.helper)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nroot=Path('
                        + repr(str(self.root)) + ')\n' + body + '\n# PINNED\n')
        path.chmod(0o700)

    def cli(self, *names):
        return subprocess.run([sys.executable, str(self.helper), *names],
                              env=self.environment, capture_output=True, text=True, timeout=10)

    def change(self, path):
        original = path.read_bytes()
        path.write_bytes(original.replace(b'# PINNED', b'# ALTERD'))
        self.assertEqual(path.stat().st_size, len(original))
        return original

    def test_valid_pinned_tools_are_read_only_and_unknown_tools_are_refused(self):
        # Mutation captured: dropping name validation exposes an unhandled lookup error.
        before = {name: (self.bin / name).read_bytes() for name in PINS}
        result = self.cli(*PINS)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {name: (self.bin / name).read_bytes() for name in PINS})
        for name in ('unknown', '../pongoterm'):
            result = self.cli(name)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Ferramenta de boot desconhecida', result.stderr)
            self.assertNotIn('Traceback', result.stderr)
        self.assertFalse((self.root / 'palera-executed').exists())
        self.assertFalse((self.root / 'pongoterm-executed').exists())

    def test_same_size_modification_and_missing_tools_are_refused(self):
        # Mutation captured: dropping digest verification accepts changed executable bytes.
        for name in PINS:
            with self.subTest(name=name):
                path = self.bin / name
                original = self.change(path)
                result = self.cli(name)
                self.assertEqual(result.returncode, 1)
                self.assertIn('Hash inesperado', result.stderr)
                path.unlink()
                self.assertEqual(self.cli(name).returncode, 1)
                path.write_bytes(original)
                path.chmod(0o700)

    def test_links_special_types_and_unsafe_modes_are_refused(self):
        # Mutation captured: admitting linked/writable/non-executable boot tools.
        path = self.bin / 'pongoterm'
        original = path.read_bytes()
        target = self.root / 'external-synthetic-tool'
        target.write_bytes(original)
        target.chmod(0o700)
        for kind in ('symlink', 'hardlink', 'fifo', 'public-write', 'special-mode', 'no-execute'):
            with self.subTest(kind=kind):
                path.unlink()
                if kind == 'symlink':
                    path.symlink_to(target)
                elif kind == 'hardlink':
                    os.link(target, path)
                elif kind == 'fifo':
                    os.mkfifo(path, 0o700)
                else:
                    path.write_bytes(original)
                    mode = {'public-write': 0o722, 'special-mode': 0o1700, 'no-execute': 0o600}[kind]
                    path.chmod(mode)
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), mode)
                self.assertEqual(self.cli('pongoterm').returncode, 1)
                self.assertEqual(target.read_bytes(), original)
        path.unlink()

    def test_linked_bin_directory_is_refused(self):
        # Mutation captured: following the tools directory alias bypasses its path contract.
        target = self.root / 'external-bin'
        self.bin.rename(target)
        self.bin.symlink_to(target, target_is_directory=True)
        self.assertEqual(self.cli('pongoterm').returncode, 1)

    def test_foreign_owner_and_inconsistent_size_pin_are_refused(self):
        # Mutation captured: ignoring inode ownership or the recorded size.
        if os.geteuid() == 0:
            path = self.root / 'foreign-owner-synthetic'
            path.write_bytes(b'SYNTHETIC')
            path.chmod(0o700)
            os.chown(path, 1, -1)
        else:
            path = Path('/usr/bin/env')
        info = path.lstat()
        self.assertTrue(stat.S_ISREG(info.st_mode))
        self.assertNotEqual(info.st_uid, os.geteuid())
        self.assertEqual(info.st_nlink, 1)
        self.assertEqual(info.st_mode & 0o7022, 0)
        pin = (info.st_size, hashlib.sha256(path.read_bytes()).hexdigest())
        with self.assertRaises(ValueError):
            self.module.verify_path(path, pin)
        path = self.bin / 'pongoterm'
        pin = self.module.PINS['pongoterm']
        with self.assertRaises(ValueError):
            self.module.verify_path(path, (pin[0] + 1, pin[1]))

    def test_direct_monitor_rejects_changed_tool_before_usb_state_or_child(self):
        # Mutation captured: omitting the direct monitor's palera preflight executes it.
        self.change(self.bin / 'palera1n-macos-arm64')
        process = subprocess.Popen([sys.executable, str(self.boot / 'dfu_boot.py'),
                                    str(self.root / 'state.json')], env=self.environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 3
            while process.poll() is None and time.monotonic() < deadline:
                if (self.root / 'palera-executed').exists():
                    break
                time.sleep(0.05)
        finally:
            if process.poll() is None:
                process.terminate()
            _, error = process.communicate(timeout=7)
        self.assertEqual(process.returncode, 1, error.decode())
        for name in ('state.json', 'usb-accessed', 'palera-executed'):
            self.assertFalse((self.root / name).exists(), name)

    def test_wrapper_refuses_changed_tools_before_execution_or_payload(self):
        # Mutation captured: removing wrapper preflight sends payload through changed pongoterm.
        for name in PINS:
            with self.subTest(name=name):
                path = self.bin / name
                original = self.change(path)
                result = subprocess.run(['/bin/bash', str(self.wrapper), 'boot'],
                                        env=self.environment, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('Hash inesperado', result.stderr)
                for marker in ('palera-executed', 'pongoterm-executed', 'admin-attempted'):
                    self.assertFalse((self.root / marker).exists(), marker)
                self.assertFalse((self.root / 'runtime/dfu-active').exists())
                path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
