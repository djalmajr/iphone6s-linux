"""Bounded DNS wire transport; no resolver or cache lives on the Mac."""
import socket
import struct
import time

MAX_MESSAGE = 4096
TIMEOUT = 3.0


def query_valid(message):
    if not 12 <= len(message) <= MAX_MESSAGE:
        return False
    flags, questions = struct.unpack('!HH', message[2:6])
    return not flags & 0xF800 and questions == 1


def receive_exact(connection, length, deadline):
    parts = []
    while length:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('DNS frame deadline exceeded')
        connection.settimeout(remaining)
        part = connection.recv(length)
        if not part:
            raise EOFError('Incomplete DNS frame')
        parts.append(part)
        length -= len(part)
    return b''.join(parts)


def receive_frame(connection):
    deadline = time.monotonic() + TIMEOUT
    length = struct.unpack('!H', receive_exact(connection, 2, deadline))[0]
    if not 12 <= length <= MAX_MESSAGE:
        raise ValueError('DNS frame size refused')
    return receive_exact(connection, length, deadline)


def exchange(message, endpoint):
    if not query_valid(message):
        raise ValueError('DNS query refused')
    deadline = time.monotonic() + TIMEOUT
    with socket.create_connection(endpoint, timeout=TIMEOUT) as connection:
        connection.settimeout(max(0.001, deadline - time.monotonic()))
        connection.sendall(struct.pack('!H', len(message)) + message)
        length = struct.unpack('!H', receive_exact(connection, 2, deadline))[0]
        if not 12 <= length <= MAX_MESSAGE:
            raise ValueError('DNS response size refused')
        answer = receive_exact(connection, length, deadline)
    if answer[:2] != message[:2] or not answer[2] & 0x80:
        raise ValueError('DNS response identity refused')
    return answer
