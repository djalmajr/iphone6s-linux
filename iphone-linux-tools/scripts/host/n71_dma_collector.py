"""Own and reap one bounded SSH reader; never retry a reader or driver action."""
import hashlib
import os
from pathlib import Path
import subprocess
import time
import device_profile
import n71_dma_observation as wire

READY_SECONDS = 5
TOTAL_SECONDS = 50


class Collector:
    def __init__(self, request):
        self.boot = request['boot']; wire.identity(self.boot)
        self.path = Path(request['output']) / 'dma-observer-private.log'
        device_profile.protected(self.path.parent, directory=True)
        self.process = None; self.stream = None; self.closed = False
        self.deadline = time.monotonic() + TOTAL_SECONDS
        try:
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            self.stream = os.fdopen(descriptor, 'wb')
            self.process = subprocess.Popen(request['ssh'] + [wire.command(self.boot)],
                stdout=self.stream, stderr=subprocess.STDOUT, start_new_session=False)
            ready_deadline = min(self.deadline, time.monotonic() + READY_SECONDS)
            while True:
                raw = self.read()
                if b'\n' in raw:
                    wire.ready(raw.split(b'\n', 1)[0].decode('ascii'), self.boot)
                    break
                wire.require(self.process.poll() is None and time.monotonic() < ready_deadline,
                             'DMA observer did not become ready; private output retained')
                time.sleep(0.02)
        except BaseException:
            self.close()
            raise

    def read(self):
        device_profile.protected(self.path)
        with self.path.open('rb') as stream:
            raw = stream.read(wire.LIMIT + 1)
        wire.require(len(raw) <= wire.LIMIT, 'DMA observer output exceeded its byte budget')
        return raw

    def finish(self):
        wire.require(not self.closed, 'DMA observer already closed')
        timed_out = False
        try:
            while self.process.poll() is None:
                self.read()
                if time.monotonic() >= self.deadline:
                    timed_out = True
                    break
                time.sleep(0.02)
            self.close()
            raw = self.read()
            value = wire.parse(raw, self.boot)
            return {'observation': value, 'exit': self.process.returncode, 'timed_out': timed_out,
                    'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        finally:
            self.close()

    def close(self):
        if self.closed:
            return
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process.wait()
        if self.stream is not None:
            self.stream.flush(); os.fsync(self.stream.fileno()); self.stream.close()
        self.closed = True
