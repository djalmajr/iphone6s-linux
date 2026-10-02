#!/usr/bin/env python3
"""Open exactly UDP/TCP 53, drop privileges, hand off sockets and exit."""
import argparse
import array
from contextlib import ExitStack
import ctypes
import hmac
import ipaddress
import os
from pathlib import Path
import selectors
import socket
import stat
import struct
import sys
import time

FRAME = struct.Struct('!4sIII32s')
NETWORKS = tuple(ipaddress.ip_network(x) for x in
                 ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def supplementary_groups(primary_gid):
    if sys.platform != 'darwin':
        return os.getgroups()
    # Python macOS getgroups may query account membership instead of kernel state.
    # XNU getgroups includes the effective GID; the caller checks that separately.
    function = ctypes.CDLL(None, use_errno=True).getgroups
    function.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)]
    function.restype = ctypes.c_int
    values = (ctypes.c_uint32 * 1024)()
    count = function(len(values), values)
    if count < 0:
        raise OSError(ctypes.get_errno(), 'Kernel group query failed.')
    if count > len(values):
        raise ValueError('Kernel group count refused.')
    return [value for value in values[:count] if value != primary_gid]


def private_bind(value):
    address = ipaddress.IPv4Address(value)
    if (str(address) != value or not any(address in n for n in NETWORKS)
            or address in ipaddress.ip_network('172.16.42.0/24')):
        raise ValueError('Explicit canonical private LAN bind required.')
    return value


def private_channel(options):
    path = Path(options.channel)
    if not path.is_absolute() or len(os.fsencode(path)) > 100:
        raise ValueError('Absolute short Unix socket path required.')
    parent, leaf = path.parent.lstat(), path.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != options.uid
            or parent.st_mode & 0o077 or not stat.S_ISSOCK(leaf.st_mode)
            or leaf.st_uid != options.uid or leaf.st_mode & 0o077):
        raise ValueError('Private caller-owned directory/socket required.')


def read_nonce():
    data = b''
    deadline = time.monotonic() + 3
    with selectors.DefaultSelector() as selector:
        selector.register(0, selectors.EVENT_READ)
        while len(data) <= 32:
            left = deadline - time.monotonic()
            if left <= 0 or not selector.select(left):
                raise TimeoutError('Nonce input deadline exceeded.')
            piece = os.read(0, 33 - len(data))
            if not piece:
                break
            data += piece
    if len(data) != 32:
        raise ValueError('Exactly 32 nonce bytes required.')
    return data


def bootstrap(options):
    if (os.geteuid() != 0 or os.getuid() != 0 or options.uid <= 0 or options.gid <= 0
            or str(options.uid) != os.environ.get('SUDO_UID')
            or str(options.gid) != os.environ.get('SUDO_GID')):
        raise ValueError('Root bootstrap must match non-root original sudo identity.')
    bind = private_bind(options.bind)
    private_channel(options)
    nonce = read_nonce()
    with ExitStack() as stack:
        udp = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
        udp.bind((bind, 53))
        tcp = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcp.bind((bind, 53))
        os.setgroups([])
        os.setgid(options.gid)
        os.setuid(options.uid)
        groups = supplementary_groups(options.gid)
        if (os.getuid() != options.uid or os.geteuid() != options.uid
                or os.getgid() != options.gid or os.getegid() != options.gid
                or groups):
            raise ValueError('Privilege drop incomplete; no socket handoff.')
        private_channel(options)
        channel = stack.enter_context(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
        channel.settimeout(3)
        channel.connect(options.channel)
        payload = FRAME.pack(b'DNS1', os.geteuid(), os.getegid(), len(groups), nonce)
        descriptors = array.array('i', [udp.fileno(), tcp.fileno()])
        sent = channel.sendmsg([payload], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, descriptors)])
        if sent != len(payload):
            raise OSError('Socket handoff frame incomplete.')
        # EOF delimits the frame; retain UDP/TCP until the receiver adopts them.
        channel.shutdown(socket.SHUT_WR)
        wait_for_ack(channel, nonce)


def wait_for_ack(channel, nonce):
    data = b''
    deadline = time.monotonic() + 3
    while len(data) <= 32:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('Socket adoption acknowledgement deadline exceeded.')
        channel.settimeout(left)
        try:
            piece = channel.recv(33 - len(data))
        except socket.timeout as error:
            raise TimeoutError('Socket adoption acknowledgement deadline exceeded.') from error
        if not piece:
            break
        data += piece
    if not hmac.compare_digest(data, nonce):
        raise ValueError('Socket adoption acknowledgement refused.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True)
    parser.add_argument('--channel', required=True)
    parser.add_argument('--uid', required=True, type=int)
    parser.add_argument('--gid', required=True, type=int)
    options = parser.parse_args()
    try:
        bootstrap(options)
    except (OSError, ValueError) as error:
        print('DNS_BOOTSTRAP_REFUSED ' + type(error).__name__ + ': ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
