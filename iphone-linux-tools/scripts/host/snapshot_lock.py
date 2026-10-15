"""Non-blocking process lock for a local snapshot store."""

import contextlib
import errno
import fcntl
import os
from pathlib import Path
import stat


LOCK_NAME = '.snapshot.lock'


def _check_metadata(info, directory=False):
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if (not valid_type or info.st_uid != os.geteuid() or info.st_mode & 0o7000
            or (not directory and info.st_nlink != 1)):
        raise ValueError('Caminho local de snapshot/journal inválido; links não são permitidos.')


def check_local_path(path, directory=False):
    path = Path(path)
    _check_metadata(path.lstat(), directory)
    return path


def _ensure_store(store):
    store = Path(store)
    try:
        store.lstat()
    except FileNotFoundError:
        store.mkdir(mode=0o700)
    check_local_path(store, directory=True)
    store.chmod(0o700)
    return store


def _open_lock(path):
    flags = os.O_RDWR | os.O_NONBLOCK | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        fd = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _check_metadata(os.fstat(fd))
    except ValueError:
        os.close(fd)
        raise
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
