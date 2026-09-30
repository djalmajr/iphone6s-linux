import os
import pathlib
import signal
import socket
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class BootFailureTests(unittest.TestCase):
    def test_exploit_failure_stops_before_transfer_and_cleans_guide(self):
        artifacts = ("palera1n-macos-arm64", "m1n1-linux-iphone6s-console-server.bin")
        if not all((ROOT / name).is_file() for name in artifacts):
            self.skipTest("Private boot artifacts required for wrapper integration test")
        with tempfile.TemporaryDirectory() as folder:
            work = pathlib.Path(folder)
            with socket.socket() as available:
                available.bind(("127.0.0.1", 0))
                port = available.getsockname()[1]
            source = (ROOT / "iphone-linux.sh").read_text()
            script = work / "iphone-linux.sh"
            script.write_text(source.replace("127.0.0.1:8765", f"127.0.0.1:{port}"))
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
            guide = work / "dfu_visual.py"
            guide.write_text(f'''import http.server,json,os,pathlib
pathlib.Path(__file__).with_name("guide.pid").write_text(str(os.getpid()))
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_GET(self):
        body=json.dumps({{"phase":"failed","ready":False}}).encode()
        self.send_response(200)
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
http.server.HTTPServer(("127.0.0.1",{port}),Handler).serve_forever()
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
                with self.assertRaises(OSError):
                    socket.create_connection(("127.0.0.1", port), timeout=1)
            finally:
                pid_file = work / "guide.pid"
                if pid_file.exists():
                    try:
                        os.kill(int(pid_file.read_text()), signal.SIGTERM)
                    except ProcessLookupError:
                        pass


if __name__ == "__main__":
    unittest.main()
