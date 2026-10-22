"""Khóa GPU dùng chung cả CLI và web, kể cả chạy ở hai tiến trình khác nhau."""
from contextlib import contextmanager
from functools import wraps
import os
import threading
import time
from ..settings import ROOT

_thread_lock = threading.RLock()


def process_alive(pid):
    if not pid:
        return False
    if os.name == 'nt':
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


@contextmanager
def gpu_slot():
    path = ROOT / '.cache/gpu.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock, path.open('a+b') as stream:
        stream.seek(0, 2)
        if not stream.tell():
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(.25)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def gpu_serialized(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with gpu_slot():
            return function(*args, **kwargs)
    return wrapped
