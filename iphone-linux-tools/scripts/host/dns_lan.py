"""Foreground UDP/TCP DNS proxy through a dedicated trusted SSH forward."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import os
import selectors
import signal
import socket
import struct
import subprocess
import tempfile
import threading
import time
import device_profile
import dns_activation
import dns_transport as wire
import lan

WORKERS = 8
MAX_REQUESTS = 16
READY = b'IPHONE_DNS_TUNNEL_READY\n'


def tunnel_command(options):
    return lan.ssh_options() + ['-T', '-o', 'ExitOnForwardFailure=yes',
                                '-L', f'127.0.0.1:{options.tunnel_port}:{lan.PHONE}:5353',
                                f'root@{lan.PHONE}',
                                "printf 'IPHONE_DNS_TUNNEL_READY\\n'; exec /bin/cat >/dev/null"]


def stop_tunnel(process):
    if process.stdin:
        process.stdin.close()
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
    if process.stdout:
        process.stdout.close()


def await_tunnel(process):
    deadline = time.monotonic() + 10
    received = b''
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while time.monotonic() < deadline and process.poll() is None:
            if not selector.select(0.2):
                continue
            piece = os.read(process.stdout.fileno(), len(READY) + 1)
            if not piece:
                break
            received += piece
            if received == READY:
                return
            if len(received) >= len(READY) or not READY.startswith(received):
                break
    raise RuntimeError('SSH não confirmou o túnel DNS próprio; nenhum proxy publicado.')


def udp_reply(options):
    message, peer, listener, endpoint = options
    try:
        listener.sendto(wire.exchange(message, endpoint), peer)
    except (OSError, EOFError, ValueError):
        pass


def tcp_replies(options):
    connection, endpoint, stopped = options
    with connection:
        try:
            for _ in range(MAX_REQUESTS):
                if stopped.is_set():
                    break
                message = wire.receive_frame(connection)
                answer = wire.exchange(message, endpoint)
                connection.settimeout(wire.TIMEOUT)
                connection.sendall(struct.pack('!H', len(answer)) + answer)
        except (OSError, EOFError, ValueError):
            pass


def serve(options):
    if options.port == options.tunnel_port:
        raise ValueError('Portas DNS e túnel devem ser distintas.')
    if options.port == 53 and (os.getuid() <= 0 or os.getuid() != os.geteuid() or os.getgid() <= 0):
        raise ValueError('Runtime DNS padrão deve ser usuário não root; não use sudo no proxy.')
    profile = device_profile.load(lan.ROOT)
    if not profile['client_key'].is_file() or not profile['known_hosts'].is_file():
        raise ValueError('Identidade SSH dedicada ausente; nenhum listener iniciado.')
    allowed = frozenset(options.allow)
    stopped = threading.Event()
    slots = threading.BoundedSemaphore(WORKERS)
    endpoint = ('127.0.0.1', options.tunnel_port)
    previous = {}
    try:
        for name in (signal.SIGINT, signal.SIGTERM):
            previous[name] = signal.signal(name, lambda *_: stopped.set())
        with ExitStack() as stack:
            log = stack.enter_context(tempfile.TemporaryFile())
            process = subprocess.Popen(tunnel_command(options), stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=log)
            stack.callback(stop_tunnel, process)
            await_tunnel(process)
            if options.port == 53:
                udp, tcp = dns_activation.acquire(options.bind)
                stack.enter_context(udp)
                stack.enter_context(tcp)
            else:
                udp = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
                udp.bind((options.bind, options.port))
                tcp = stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
                tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                tcp.bind((options.bind, options.port))
            tcp.listen(WORKERS)
            udp.setblocking(False)
            tcp.setblocking(False)
            selector = stack.enter_context(selectors.DefaultSelector())
            selector.register(udp, selectors.EVENT_READ)
            selector.register(tcp, selectors.EVENT_READ)
            pool = stack.enter_context(ThreadPoolExecutor(max_workers=WORKERS))
            stack.callback(stopped.set)
            print(f'DNS UDP/TCP: {options.bind}:{options.port}; {len(allowed)} cliente(s) permitido(s).', flush=True)
            print('DNS_LAN_READY', flush=True)
            while not stopped.is_set():
                if process.poll() is not None:
                    raise RuntimeError('O túnel SSH terminou; proxy DNS encerrado.')
                for event, _ in selector.select(0.2):
                    if event.fileobj is udp:
                        message, peer = udp.recvfrom(wire.MAX_MESSAGE + 1)
                        if peer[0] not in allowed or not wire.query_valid(message):
                            continue
                        if not slots.acquire(blocking=False):
                            continue
                        future = pool.submit(udp_reply, (message, peer, udp, endpoint))
                    else:
                        connection, peer = tcp.accept()
                        if peer[0] not in allowed or not slots.acquire(blocking=False):
                            connection.close()
                            continue
                        future = pool.submit(tcp_replies, (connection, endpoint, stopped))
                    future.add_done_callback(lambda _: slots.release())
            stopped.set()
    finally:
        stopped.set()
        for name, handler in previous.items():
            signal.signal(name, handler)
