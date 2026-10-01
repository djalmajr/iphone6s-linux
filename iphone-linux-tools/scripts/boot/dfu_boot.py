#!/usr/bin/env python3
"""Monitor the manual USB DFU flow without a browser or HTTP listener."""

import json
import os
import pty
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from dfu_state import finish_output, process_output
from pongo_select import select

ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "logs/dfu-last-state.json"


def main():
    pongo = select(ROOT)
    if 'IPHONE_LINUX_PONGO' in os.environ:
        usb = subprocess.run(['ioreg', '-p', 'IOUSB', '-w0'], capture_output=True,
                             text=True, timeout=5, check=True)
        if 'PongoOS USB Device' in usb.stdout or 'iPhone 6s Linux probe' in usb.stdout:
            raise ValueError('Pongo explícito exige novo boot a partir do iOS/Recovery/DFU.')
    lock = threading.Lock()
    state = {"ready": False, "phase": "starting", "log": ""}

    def publish():
        # Only operational state is retained here; raw output goes to private log.
        temporary = STATE_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps({k: state[k] for k in ("ready", "phase")}))
        temporary.chmod(0o600)
        temporary.replace(STATE_FILE)

    def stop(_signal, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    STATE_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    publish()
    master, slave = pty.openpty()
    environment = dict(os.environ, PALERA1N_BYPASS_PASSCODE_CHECK="1")
    process = None
    reader = None
    try:
        process = subprocess.Popen(
            [str(ROOT / "bin/palera1n-macos-arm64"), "-lp", "-k", str(pongo)],
            cwd=ROOT, env=environment, stdin=slave, stdout=slave, stderr=slave,
            start_new_session=True,
        )
        os.close(slave)
        slave = None

        def read_output():
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", chunk.decode(errors="replace"))
                print(clean, end="", flush=True)
                with lock:
                    process_output(state, clean)
                    publish()
            with lock:
                finish_output(state)
                publish()

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        submitted = False
        while True:
            with lock:
                ready = state["ready"]
            if ready and not submitted:
                usb = subprocess.run(
                    ["ioreg", "-p", "IOUSB", "-w0"], capture_output=True,
                    text=True, timeout=5, check=True,
                )
                # A manual DFU may precede the tool's Enter prompt. Resume only
                # after macOS actually enumerates DFU; no timed button sequence.
                if "DFU" in usb.stdout:
                    os.write(master, b"\n")
                    submitted = True
            time.sleep(0.5)
    finally:
        if process is not None:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            if reader is not None:
                reader.join(timeout=1)
        os.close(master)
        if slave is not None:
            os.close(slave)
        STATE_FILE.with_suffix(".tmp").unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
