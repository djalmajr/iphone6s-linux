#!/usr/bin/env python3
"""Small Telnet client for the isolated USB boot probe, using only the stdlib."""

import os
import re
import select
import socket
import sys
import termios
import time
import tty
import uuid

IAC, WILL, WONT, DO, DONT, SB, SE = 255, 251, 252, 253, 254, 250, 240


class USBTerminal:
    def __init__(self):
        self.sock = socket.create_connection(("172.16.42.1", 23), timeout=10)
        self.pending = bytearray()

    def read(self):
        data = self.sock.recv(8192)
        if not data:
            return None
        self.pending.extend(data)
        output = bytearray()
        while self.pending:
            if self.pending[0] != IAC:
                output.append(self.pending.pop(0))
                continue
            if len(self.pending) < 2:
                break
            command = self.pending[1]
            if command == IAC:
                output.append(IAC)
                del self.pending[:2]
            elif command in (WILL, WONT, DO, DONT):
                if len(self.pending) < 3:
                    break
                option = self.pending[2]
                if command == DO:
                    self.sock.sendall(bytes((IAC, WONT, option)))
                elif command == WILL:
                    response = DO if option in (1, 3) else DONT
                    self.sock.sendall(bytes((IAC, response, option)))
                del self.pending[:3]
            elif command == SB:
                end = self.pending.find(bytes((IAC, SE)), 2)
                if end == -1:
                    break
                del self.pending[:end + 2]
            else:
                del self.pending[:2]
        return bytes(output)

    def prompt(self):
        output = bytearray()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            part = self.read()
            if part is None:
                raise RuntimeError("O terminal USB encerrou antes do prompt.")
            output.extend(part)
            if b"\x1b[6n" in part:
                self.sock.sendall(b"\x1b[1;1R")
            visible = re.sub(rb"\x1b\[[0-9;?]*[A-Za-z]", b"", bytes(output))
            if visible.endswith(b"# "):
                return bytes(output)
        raise TimeoutError("O terminal USB não apresentou o prompt.")

    def run(self, script):
        self.prompt()
        self.sock.sendall(b"stty -echo; export TERM=dumb\n")
        self.prompt()
        token = "USB_" + uuid.uuid4().hex
        path = "/tmp/" + token
        payload = (
            f"cat > {path} <<'{token}'\n" + script.rstrip() + "\n" + token + "\n"
            + f"/bin/sh {path}; code=$?; rm {path}; printf '\\n{token}:%s\\n' \"$code\"; exit\n"
        )
        self.sock.sendall(payload.encode())
        output = bytearray()
        marker = token.encode() + b":"
        while True:
            part = self.read()
            if part is None:
                break
            output.extend(part)
            if re.search(re.escape(marker) + rb"[0-9]+\r?\n", output):
                break
        normalized = bytes(output).replace(b"\r", b"")
        position = normalized.rfind(marker)
        if position == -1:
            raise RuntimeError("A execução encerrou sem confirmar o resultado.")
        result = normalized[position + len(marker):].split(b"\n", 1)[0]
        sys.stdout.buffer.write(normalized[:position])
        return int(result)

    def interactive(self):
        sys.stdout.buffer.write(self.prompt())
        sys.stdout.buffer.flush()
        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                readable, _, _ = select.select([fd, self.sock], [], [])
                if fd in readable:
                    data = os.read(fd, 4096)
                    if not data:
                        break
                    self.sock.sendall(data.replace(b"\xff", b"\xff\xff"))
                if self.sock in readable:
                    data = self.read()
                    if data is None:
                        break
                    os.write(sys.stdout.fileno(), data)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def main():
    terminal = USBTerminal()
    try:
        if "--script" in sys.argv:
            return terminal.run(sys.stdin.read())
        if not sys.stdin.isatty():
            raise RuntimeError("Use --script para enviar comandos pela entrada padrão.")
        terminal.interactive()
        return 0
    finally:
        terminal.sock.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Terminal USB: {error}", file=sys.stderr)
        sys.exit(1)
