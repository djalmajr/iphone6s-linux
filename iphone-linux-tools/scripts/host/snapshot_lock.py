"""Non-blocking process lock for a local snapshot store."""

import contextlib
import errno
import fcntl
import os
from pathlib import Path
import stat


LOCK_NAME = '.snapshot.lock'


def _ensure_store(store):
    store = Path(store)
    try:
        info = store.lstat()
    except FileNotFoundError:
        store.mkdir(mode=0o700)
        info = store.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ValueError('Diretório de snapshots inválido.')
    store.chmod(0o700)
    return store


def _open_lock(path):
    flags = os.O_RDWR | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        fd = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise ValueError('Arquivo de lock inválido.')
    os.fchmod(fd, 0o600)
    return fd


@contextlib.contextmanager
def lock(store):
    """Acquire an exclusive, non-blocking lock without removing its inode."""

    store = _ensure_store(store)
    fd = _open_lock(store / LOCK_NAME)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN):
                raise BlockingIOError(error.errno, 'Store de snapshots já está bloqueado.') from error
            raise
        yield store
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
