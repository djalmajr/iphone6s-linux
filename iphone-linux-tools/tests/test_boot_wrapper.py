import os
import hashlib
import json
import pathlib
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class BootFailureTests(unittest.TestCase):
    def test_monitor_resumes_only_after_usb_dfu_and_cleans_child(self):
        with tempfile.TemporaryDirectory() as folder:
            work = pathlib.Path(folder)
            boot = work / "scripts/boot"
            boot.mkdir(parents=True)
            for name in ("dfu_boot.py", "dfu_state.py", "pongo_select.py", "boot_tools.py"):
                shutil.copyfile(ROOT / "scripts/boot" / name, boot / name)
            image = work / "artifacts/Pongo.bin"
            image.parent.mkdir()
            image.write_bytes(b'SYNTHETIC_DEFAULT_PONGO')
            helper = boot / 'pongo_select.py'
            helper.write_text(helper.read_text().replace(
                '1e5543fd8e6dbd84c334b87d71aa473f4d347c2ba8a5e863b6e10f18461c7575',
                hashlib.sha256(image.read_bytes()).hexdigest()).replace(
                    'IMAGE_BYTES = 238096', 'IMAGE_BYTES = ' + str(image.stat().st_size)))
            binary = work / "bin/palera1n-macos-arm64"
            binary.parent.mkdir()
            binary.write_text('''#!/usr/bin/env python3
import os,pathlib,sys,time
pathlib.Path("child.pid").write_text(str(os.getpid()))
print("Press Enter when ready for DFU mode",flush=True)
sys.stdin.readline()
pathlib.Path("enter-submitted").touch()
print("Device entered DFU\\nBooting pongoOS",flush=True)
while True: time.sleep(1)
''')
            binary.chmod(0o700)
            tool_check = boot / 'boot_tools.py'
            tool_check.write_text(tool_check.read_text().replace(
                "(4874592, '950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9')",
                repr((binary.stat().st_size, hashlib.sha256(binary.read_bytes()).hexdigest()))))
            binaries = work / "bin"
            binaries.mkdir(exist_ok=True)
            usb = binaries / "ioreg"
            usb.write_text('#!/bin/sh\nif [ -f usb-dfu ]; then echo "Apple DFU Device"; fi\n')
            usb.chmod(0o700)
            state = work / "state.json"
            environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"])
            process = subprocess.Popen(
                ["python3", str(boot / "dfu_boot.py"), str(state)], cwd=work,
                env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            def wait_for(phase):
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if state.exists() and json.loads(state.read_text())["phase"] == phase:
                        return
                    time.sleep(0.05)
                self.fail("Monitor did not reach " + phase)
            try:
                wait_for("ready")
                time.sleep(0.7)
                self.assertFalse((work / "enter-submitted").exists())
                (work / "usb-dfu").touch()
                wait_for("pongo")
                self.assertTrue((work / "enter-submitted").exists())
            finally:
                process.terminate()
                _, error = process.communicate(timeout=6)
                pid_file = work / "child.pid"
                if pid_file.exists():
                    pid = int(pid_file.read_text())
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        pass
                    else:
                        os.kill(pid, signal.SIGKILL)
                        self.fail("Child survived monitor shutdown")
            self.assertEqual(process.returncode, 0, error.decode())
            self.assertFalse(state.with_suffix(".tmp").exists())

    def test_exploit_failure_stops_before_transfer_and_cleans_monitor(self):
        artifacts = ("bin/palera1n-macos-arm64", "artifacts/m1n1-linux-iphone6s-loopback-server.bin", "artifacts/Pongo.bin")
        if not all((ROOT / name).is_file() for name in artifacts):
            self.skipTest("Private boot artifacts required for wrapper integration test")
        with tempfile.TemporaryDirectory() as folder:
            work = pathlib.Path(folder)
            source = (ROOT / "scripts/host/iphone-linux.sh").read_text()
            script = work / "scripts/host/iphone-linux.sh"
            script.parent.mkdir(parents=True)
            script.write_text(source)
            for name in artifacts[:-1]:
                (work / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, work / name)
                (work / name).chmod((ROOT / name).stat().st_mode & 0o777)
            binaries = work / "bin"
            binaries.mkdir(exist_ok=True)
            for name in ("ioreg", "open"):
                command = binaries / name
                command.write_text("#!/bin/sh\nexit 0\n")
                command.chmod(0o700)
            transfer = work / "bin/pongoterm"
            transfer.write_text("#!/bin/sh\ntouch payload-sent\n")
            transfer.chmod(0o700)
            guide = work / "scripts/boot/dfu_boot.py"
            guide.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / 'scripts/boot/pongo_select.py', guide.parent / 'pongo_select.py')
            tool_check = guide.parent / 'boot_tools.py'
            tool_check.write_text((ROOT / 'scripts/boot/boot_tools.py').read_text().replace(
                "(53608, 'ad4d66f1e2908090cc52a07ce5a58076b5ae877bb3d50b2a8d8e267b63113a56')",
                repr((transfer.stat().st_size, hashlib.sha256(transfer.read_bytes()).hexdigest()))))
            shutil.copyfile(ROOT / 'artifacts/Pongo.bin', work / 'artifacts/Pongo.bin')
            guide.write_text('''import json,os,pathlib,sys,time
pathlib.Path("guide.pid").write_text(str(os.getpid()))
pathlib.Path(sys.argv[1]).write_text(json.dumps({"phase":"failed","ready":False}))
while True: time.sleep(1)
''')
            environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"])
            try:
                result = subprocess.run(
                    ["/bin/bash", str(script), "boot"], cwd=work,
                    env=environment, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("Falha na etapa DFU/exploração USB", result.stderr)
                self.assertIn("Nenhum payload Linux foi enviado", result.stderr)
                self.assertFalse((work / "payload-sent").exists())
                pid = int((work / "guide.pid").read_text())
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)
                self.assertFalse((work / "runtime/dfu-active").exists())
            finally:
                pid_file = work / "guide.pid"
                if pid_file.exists():
                    try:
                        os.kill(int(pid_file.read_text()), signal.SIGTERM)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
