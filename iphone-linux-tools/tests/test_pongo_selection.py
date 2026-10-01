"""Pin Pongo selection and verify rejection before USB or child processes."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import shutil
import time
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ.get('PONGO_SELECTION_ROOT', ROOT))
SOURCE = SOURCE_ROOT / 'scripts/boot/pongo_select.py'


class PongoSelectionTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='pongo-selection-synthetic-')
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name).resolve()
        self.boot = self.root / 'scripts/boot'
        self.boot.mkdir(parents=True)
        self.default = self.root / 'artifacts/Pongo.bin'
        self.default.parent.mkdir()
        self.candidate = self.root / 'source candidate.bin'
        self.default_bytes = b'SYNTHETIC_DEFAULT'.ljust(238096, b'D')
        self.source_bytes = b'SYNTHETIC_SOURCE'.ljust(238096, b'S')
        self.default.write_bytes(self.default_bytes)
        self.candidate.write_bytes(self.source_bytes)
        text = SOURCE.read_text().replace(
            '1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575',
            hashlib.sha256(self.default_bytes).hexdigest()).replace(
                '17d3df93213bb24f8ba73a8ad390e6bcc56351b41d87a315d47d37aa51100efd',
                hashlib.sha256(self.source_bytes).hexdigest())
        self.helper = self.boot / 'pongo_select.py'
        self.helper.write_text(text)
        self.environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        self.environment.pop('IPHONE_LINUX_PONGO', None)
        self.environment.pop('IPHONE_LINUX_PROFILE', None)

    def cli(self):
        return subprocess.run([sys.executable, str(self.helper)], env=self.environment,
                              capture_output=True, text=True, timeout=10)

    def test_default_and_explicit_candidate_choose_distinct_pinned_files(self):
        # Mutation captured: using the default hash/path for explicit source selection.
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.default))
        self.environment['IPHONE_LINUX_PONGO'] = str(self.candidate)
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.candidate))
        self.assertEqual(self.default.read_bytes(), self.default_bytes)

    def test_empty_or_invalid_selection_never_falls_back(self):
        # Mutation captured: treating an empty selector as absent or ignoring controls.
        for value in ('', str(self.root / 'missing'), str(self.candidate) + '\n'):
            with self.subTest(value=value):
                self.environment['IPHONE_LINUX_PONGO'] = value
                result = self.cli()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, '')

    def test_modified_default_and_source_are_rejected(self):
        # Mutation captured: omitting the trusted expected SHA comparison.
        for path in (self.default, self.candidate):
            with self.subTest(path=path):
                if path == self.candidate:
                    self.environment['IPHONE_LINUX_PONGO'] = str(path)
                path.write_bytes(b'X' + path.read_bytes()[1:])
                result = self.cli()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('Hash do Pongo inesperado', result.stderr)

    def test_links_and_public_writes_are_rejected(self):
        # Mutation captured: allowing file links or writable-by-others boot inputs.
        self.environment['IPHONE_LINUX_PONGO'] = str(self.candidate)
        target = self.root / 'link-target'
        target.write_bytes(self.source_bytes)
        self.candidate.unlink()
        self.candidate.symlink_to(target)
        self.assertEqual(self.cli().returncode, 1)
        self.candidate.unlink()
        os.link(target, self.candidate)
        self.assertEqual(self.cli().returncode, 1)
        self.candidate.unlink()
        self.candidate.write_bytes(self.source_bytes)
        self.candidate.chmod(0o666)
        self.assertEqual(self.cli().returncode, 1)

    def test_size_and_parent_symlinks_are_rejected(self):
        # Mutation captured: trusting file size or following parent directory aliases.
        self.environment['IPHONE_LINUX_PONGO'] = str(self.candidate)
        self.candidate.write_bytes(self.source_bytes + b'X')
        self.assertEqual(self.cli().returncode, 1)
        self.candidate.write_bytes(self.source_bytes)
        alias = self.root / 'alias'
        alias.symlink_to(self.candidate.parent, target_is_directory=True)
        self.environment['IPHONE_LINUX_PONGO'] = str(alias / self.candidate.name)
        self.assertEqual(self.cli().returncode, 1)


class PongoBootBoundaryTests(unittest.TestCase):
    # Reuse synthetic inputs without inheriting the helper's test cases.
    def setUp(self):
        PongoSelectionTests.setUp(self)
        self.host = self.root / 'scripts/host'
        self.host.mkdir(parents=True)
        shutil.copyfile(SOURCE_ROOT / 'scripts/host/iphone-linux.sh', self.host / 'iphone-linux.sh')
        for name in ('dfu_boot.py', 'dfu_state.py'):
            shutil.copyfile(SOURCE_ROOT / 'scripts/boot' / name, self.boot / name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.stub('ioreg', "(root/'usb-accessed').touch()\nprint((root/'usb-state').read_text() if (root/'usb-state').exists() else '')\n")
        self.stub('palera1n-macos-arm64', "import json,sys,time,os\n(root/'child.pid').write_text(str(os.getpid()))\n(root/'palera-args').write_text(json.dumps(sys.argv[1:]))\nwhile True: time.sleep(1)\n")
        self.stub('pongoterm', "(root/'payload-sent').touch()\n")
        self.environment['PATH'] = str(self.bin) + os.pathsep + os.environ['PATH']
        self.environment['IPHONE_LINUX_PONGO'] = str(self.candidate)

    def stub(self, name, body):
        path = self.bin / name
        path.write_text('#!' + sys.executable + '\nfrom pathlib import Path\nroot=Path('
                        + repr(str(self.root)) + ')\n' + body)
        path.chmod(0o700)

    def command(self, monitor=False):
        return ([sys.executable, str(self.boot / 'dfu_boot.py'), str(self.root / 'state.json')]
                if monitor else ['/bin/bash', str(self.host / 'iphone-linux.sh'), 'boot'])

    def untouched(self):
        for name in ('usb-accessed', 'palera-args', 'payload-sent', 'state.json', 'runtime/dfu-active'):
            self.assertFalse((self.root / name).exists(), name)

    def test_invalid_candidate_blocks_wrapper_and_direct_monitor_before_usb(self):
        # Mutation captured: removing selection preflight from wrapper or monitor.
        for value in ('', str(self.candidate)):
            self.environment['IPHONE_LINUX_PONGO'] = value
            self.candidate.write_bytes(b'X' + self.source_bytes[1:])
            for monitor in (False, True):
                with self.subTest(selector=value, monitor=monitor):
                    result = subprocess.run(self.command(monitor), env=self.environment,
                                            capture_output=True, text=True, timeout=10)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.untouched()

    def test_existing_pongo_or_linux_refuses_candidate_transfer(self):
        # Mutation captured: assuming a bootloader already on USB is the selected one.
        for state in ('PongoOS USB Device', 'iPhone 6s Linux probe'):
            (self.root / 'usb-state').write_text(state)
            for monitor in (False, True):
                with self.subTest(state=state, monitor=monitor):
                    process = subprocess.Popen(self.command(monitor), env=self.environment,
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    try:
                        deadline = time.monotonic() + 3
                        while process.poll() is None and time.monotonic() < deadline:
                            if (self.root / 'palera-args').exists():
                                break
                            time.sleep(0.05)
                    finally:
                        if process.poll() is None:
                            process.terminate()
                        _, error = process.communicate(timeout=7)
                    self.assertEqual(process.returncode, 1, error.decode())
                    expected = ('candidata selecionada' if state == 'PongoOS USB Device'
                                and not monitor else 'novo boot')
                    self.assertIn(expected, error.decode())
                    self.assertTrue((self.root / 'usb-accessed').exists())
                    self.assertFalse((self.root / 'palera-args').exists())
                    self.assertFalse((self.root / 'payload-sent').exists())
                    self.assertFalse((self.root / 'state.json').exists())
                    self.assertFalse((self.root / 'runtime/dfu-active').exists())

    def test_monitor_passes_exact_candidate_path_and_cleans_child(self):
        # Mutation captured: ignoring the validated path when invoking palera.
        import json
        process = subprocess.Popen(self.command(True), env=self.environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            marker = self.root / 'palera-args'
            while time.monotonic() < deadline and not marker.exists():
                time.sleep(0.05)
            self.assertTrue(marker.exists())
            self.assertEqual(json.loads(marker.read_text()), ['-lp', '-k', str(self.candidate)])
            self.assertEqual(self.default.read_bytes(), self.default_bytes)
        finally:
            process.terminate()
            _, error = process.communicate(timeout=7)
        self.assertEqual(process.returncode, 0, error.decode())
        pid = int((self.root / 'child.pid').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)


if __name__ == '__main__':
    unittest.main()
