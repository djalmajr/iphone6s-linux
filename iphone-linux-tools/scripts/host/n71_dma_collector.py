"""Own and reap one bounded SSH reader; never retry a reader or driver action."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from contextlib import contextmanager
import device_profile
import n71_dma_observation as wire
import n71_driver_runtime_profile as profile

READY_SECONDS = 5
TOTAL_SECONDS = 50
STAGE = 'dma-observer'


def receipt(raw, boot, *, exit, timed_out):
    wire.identity(boot)
    wire.require((exit is None or type(exit) is int and -128 <= exit <= 255)
        and type(timed_out) is bool, 'DMA process receipt differs')
    try:
        value = wire.parse(raw, boot); error = None
    except ValueError as failure:
        value = None; error = str(failure)
    return {'format': 1, 'boot_id': boot, 'observation': value, 'parse_error': error,
            'exit': exit, 'timed_out': timed_out, 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def root(session):
    output = getattr(session, 'output', None)
    wire.require(isinstance(output, Path) and output.is_absolute(), 'DMA Session output differs')
    return output.parent.parent


def proof_names(session, data):
    result = data.get('result', getattr(session, 'result', {}))
    if 'dma_observer' not in result:
        return ()
    wire.require(profile.observer_parameters(session, root(session)) != '',
                 'DMA proof requires the qualified observer Session')
    return (STAGE,)


def saved(session, data, proofs):
    names = proof_names(session, data)
    if not names:
        wire.require(STAGE not in proofs, 'DMA proof lacks its saved receipt')
        return
    result = data['result']; value = result['dma_observer']
    wire.require(isinstance(value, dict) and type(value.get('format')) is int and value['format'] == 1
        and STAGE in proofs and isinstance(proofs[STAGE], str), 'DMA saved receipt or proof missing')
    raw = proofs[STAGE].encode('utf-8')
    wire.require(len(raw) <= wire.LIMIT, 'DMA saved proof exceeds its budget')
    expected = receipt(raw, result['boot_id'], exit=value.get('exit'), timed_out=value.get('timed_out'))
    wire.require(json.dumps(value, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True),
                 'DMA saved receipt differs from its raw boot-scoped proof')


def persist(reader, journal):
    value = reader.finish()
    raw = reader.read()
    wire.require(hashlib.sha256(raw).hexdigest() == value['sha256'], 'DMA reader changed before journal persistence')
    text = raw.decode('utf-8')
    journal.session.result['dma_observer'] = value
    journal.proof(STAGE, text)


@contextmanager
def collecting(session, journal, selected_root):
    if not profile.observer_parameters(session, selected_root):
        yield
        return
    wire.require(root(session) == selected_root
        and session.ssh == device_profile.ssh_options(selected_root) + ['root@' + device_profile.PHONE],
        'DMA reader must use the selected pinned Session SSH identity')
    wire.require('dma_observer' not in session.result and STAGE not in journal.proofs,
                 'DMA observer cannot be replayed')
    reader = Collector({'boot': session.result.get('boot_id'), 'output': session.output, 'ssh': session.ssh})
    try:
        try:
            yield
        except BaseException:
            try:
                persist(reader, journal)
            except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
                session.result['dma_observer_error'] = str(error)
                try:
                    journal.save()
                except (OSError, ValueError) as failure:
                    session.result['dma_observer_journal_error'] = str(failure)
            raise
        else:
            persist(reader, journal)
    finally:
        reader.close()


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
            return receipt(raw, self.boot, exit=self.process.returncode, timed_out=timed_out)
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
