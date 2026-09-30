import os
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
            for name in ("dfu_boot.py", "dfu_state.py"):
                shutil.copyfile(ROOT / "scripts/boot" / name, boot / name)
            binary = work / "palera1n-macos-arm64"
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
            binaries = work / "bin"
            binaries.mkdir()
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
        artifacts = ("palera1n-macos-arm64", "m1n1-linux-iphone6s-console-server.bin")
        if not all((ROOT / name).is_file() for name in artifacts):
            self.skipTest("Private boot artifacts required for wrapper integration test")
        with tempfile.TemporaryDirectory() as folder:
            work = pathlib.Path(folder)
            source = (ROOT / "iphone-linux.sh").read_text()
            script = work / "iphone-linux.sh"
            script.write_text(source)
            for name in artifacts:
                (work / name).symlink_to(ROOT / name)
            binaries = work / "bin"
            binaries.mkdir()
            for name in ("ioreg", "open"):
                command = binaries / name
                command.write_text("#!/bin/sh\nexit 0\n")
                command.chmod(0o700)
            transfer = work / "pongoterm"
            transfer.write_text("#!/bin/sh\ntouch payload-sent\n")
            transfer.chmod(0o700)
            guide = work / "scripts/boot/dfu_boot.py"
            guide.parent.mkdir(parents=True)
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
