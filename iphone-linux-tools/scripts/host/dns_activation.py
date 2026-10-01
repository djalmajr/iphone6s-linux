"""Receive bound DNS sockets from a short, isolated privilege bootstrap."""
import array
from contextlib import ExitStack
import ctypes
from dataclasses import dataclass
import hmac
import os
from pathlib import Path
import secrets
import selectors
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import lan

FRAME = struct.Struct('!4sIII32s')
# XNU permits up to 512 FDs; reserve all to avoid truncated-control leaks.
MAX_FDS = 512


@dataclass(frozen=True)
class Expected:
    bind: str
    gid: int
    nonce: bytes
    port: int
    uid: int


def peer_identity(channel):
    if sys.platform == 'linux':
        credentials = channel.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
        _, uid, gid = struct.unpack('3i', credentials)
        return uid, gid
    if sys.platform == 'darwin':
        function = ctypes.CDLL(None, use_errno=True).getpeereid
        function.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
        function.restype = ctypes.c_int
        uid, gid = ctypes.c_uint(), ctypes.c_uint()
        if function(channel.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0:
            raise OSError(ctypes.get_errno(), 'Unix peer identity unavailable.')
        return uid.value, gid.value
    raise ValueError('Unix peer identity unsupported on this platform.')


def remaining(deadline):
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError('Socket activation deadline exceeded.')
    return left


def premature_tcp_state(listener):
    if sys.platform == 'darwin':
        # XNU tcp.h: TCP_CONNECTION_INFO=0x106, first byte tcpi_state.
        # tcp_fsm.h: TCPS_CLOSED=0. Read state without accepting a connection.
        info = listener.getsockopt(socket.IPPROTO_TCP, 0x106, 256)
        return not info or info[0] != 0
    return bool(listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN))


def receive_sockets(channel, expected):
    descriptors, adopted = [], []
    deadline = time.monotonic() + 3
    try:
        if peer_identity(channel) != (expected.uid, expected.gid):
            raise ValueError('Unix peer identity mismatch.')
        payload = b''
        itemsize = array.array('i').itemsize
        while len(payload) <= FRAME.size:
            channel.settimeout(remaining(deadline))
            try:
                piece, ancillary, flags, _ = channel.recvmsg(
                    FRAME.size + 1 - len(payload), socket.CMSG_SPACE(MAX_FDS * itemsize))
            except socket.timeout as error:
                raise TimeoutError('Socket activation deadline exceeded.') from error
            invalid_control = False
            for level, kind, data in ancillary:
                if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                    invalid_control = True
                    continue
                received = array.array('i')
                received.frombytes(data[:len(data) - len(data) % itemsize])
                descriptors.extend(received)
                invalid_control |= len(data) % itemsize != 0
            if (invalid_control or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC)
                    or len(descriptors) > 2):
                raise ValueError('Socket activation ancillary data refused.')
            payload += piece
            if not piece:
                break
        if len(payload) != FRAME.size or len(descriptors) != 2:
            raise ValueError('Socket activation frame/count refused.')
        magic, uid, gid, groups, nonce = FRAME.unpack(payload)
        if (magic != b'DNS1' or uid != expected.uid or gid != expected.gid or groups != 0
                or not hmac.compare_digest(nonce, expected.nonce)):
            raise ValueError('Socket activation identity/nonce refused.')
        for kind in (socket.SOCK_DGRAM, socket.SOCK_STREAM):
            descriptor = descriptors.pop(0)
            try:
                listener = socket.socket(fileno=descriptor)
            except BaseException:
                os.close(descriptor)
                raise
            adopted.append(listener)
            listener.set_inheritable(False)
            if (listener.family != socket.AF_INET
                    or listener.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != kind
                    or listener.getsockname() != (expected.bind, expected.port)
                    or (kind == socket.SOCK_STREAM
                        and premature_tcp_state(listener))
                    or listener.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
                    or listener.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT)):
                raise ValueError('Activated socket family/type/bind/state refused.')
            try:
                listener.getpeername()
            except OSError:
                pass
            else:
                raise ValueError('Activated socket is already connected.')
        return tuple(adopted)
    except BaseException:
        for listener in adopted:
            listener.close()
        for descriptor in descriptors:
            os.close(descriptor)
        raise


def stop_child(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    if process.stdin:
        process.stdin.close()


def acquire(bind):
    if os.getuid() <= 0 or os.getuid() != os.geteuid() or os.getgid() <= 0:
        raise ValueError('DNS runtime must be an ordinary non-root process.')
    bind = lan.bind_address(bind)
    if bind == '127.0.0.1':
        raise ValueError('Standard DNS port requires a private LAN bind.')
    helper = Path(__file__).with_name('dns_privileged.py')
    info = helper.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid not in (0, os.getuid())
            or info.st_mode & 0o022):
        raise ValueError('Bootstrap source ownership/type/mode refused.')
    expected = Expected(bind, os.getgid(), secrets.token_bytes(32), 53, os.getuid())
    with ExitStack() as ownership:
        with ExitStack() as resources:
            folder = resources.enter_context(tempfile.TemporaryDirectory(prefix='idns-'))
            path = str(Path(folder).resolve() / 's')
            if len(os.fsencode(path)) > 100:
                raise ValueError('Temporary Unix socket path too long.')
            directory = Path(path).parent.stat()
            if directory.st_uid != expected.uid or directory.st_mode & 0o077:
                raise ValueError('Private activation directory refused.')
            server = resources.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
            server.bind(path)
            os.chmod(path, 0o600)
            server.listen(1)
            log = resources.enter_context(tempfile.TemporaryFile())
            command = ['/usr/bin/sudo', '-n', '--', '/usr/bin/python3', '-I', '-S',
                       str(helper.resolve()), '--bind', bind, '--channel', path,
                       '--uid', str(expected.uid), '--gid', str(expected.gid)]
            process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL, stderr=log)
            resources.callback(stop_child, process)
            process.stdin.write(expected.nonce)
            process.stdin.close()
            process.stdin = None
            deadline = time.monotonic() + 10
            selector = resources.enter_context(selectors.DefaultSelector())
            selector.register(server, selectors.EVENT_READ)
            while not selector.select(min(0.1, remaining(deadline))):
                if process.poll() is not None:
                    raise ValueError('Bootstrap exited before socket handoff.')
            channel = resources.enter_context(server.accept()[0])
            sockets = receive_sockets(channel, expected)
            for listener in sockets:
                ownership.callback(listener.close)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired as error:
                raise TimeoutError('Bootstrap did not exit after handoff.') from error
            if process.returncode != 0:
                raise ValueError('Bootstrap did not finish successfully.')
            for listener in sockets:
                listener.settimeout(None)
        # Transfer ownership only after process/channel/directory cleanup succeeds.
        ownership.pop_all()
        return sockets
