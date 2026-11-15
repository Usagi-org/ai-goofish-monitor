"""Thread and process locking on a separate file."""
import os
import threading
import time


_THREAD_LOCKS_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.Lock] = {}


def _get_thread_lock(lock_path: str) -> threading.Lock:
    key = os.path.abspath(lock_path)
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[key] = lock
        return lock


class FileLock:
    def __init__(self, lock_path: str, *, timeout: float = 30.0):
        self._lock_path = lock_path
        self._timeout = timeout
        self._thread_lock = _get_thread_lock(lock_path)
        self._fh = None
        self._os_locked = False

    def __enter__(self):
        self._thread_lock.acquire()
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self._lock_path)), exist_ok=True)
            self._fh = open(self._lock_path, "a+b")
            fd = self._fh.fileno()
            if os.name == "nt":
                import msvcrt

                deadline = time.monotonic() + self._timeout
                while True:
                    os.lseek(fd, 0, os.SEEK_SET)
                    try:
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                        self._os_locked = True
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(0.01)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX)
                self._os_locked = True
            return self
        except BaseException:
            if self._fh is not None:
                try:
                    self._fh.close()
                except OSError:
                    pass
                self._fh = None
            self._thread_lock.release()
            raise

    def __exit__(self, exc_type, exc, tb):
        try:
            if self._fh is not None:
                try:
                    if self._os_locked:
                        fd = self._fh.fileno()
                        if os.name == "nt":
                            import msvcrt

                            os.lseek(fd, 0, os.SEEK_SET)
                            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl

                            fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                finally:
                    self._os_locked = False
                    try:
                        self._fh.close()
                    finally:
                        self._fh = None
        finally:
            self._thread_lock.release()
        return False
