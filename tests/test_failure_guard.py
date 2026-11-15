from __future__ import annotations

import builtins
import errno
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.failure_guard import FailureGuard, _FileLock


def _install_windows_replace_guard(monkeypatch):
    real_open = builtins.open
    real_replace = os.replace
    lock = threading.Lock()
    tracked_handles: list[tuple[str, object]] = []

    def tracked_open(file, *args, **kwargs):
        fh = real_open(file, *args, **kwargs)
        if isinstance(file, (str, bytes, os.PathLike)):
            norm_path = os.path.abspath(os.fsdecode(os.fspath(file)))
            with lock:
                tracked_handles[:] = [(p, h) for p, h in tracked_handles if not getattr(h, "closed", True)]
                tracked_handles.append((norm_path, fh))
        return fh

    def checked_replace(src, dst, *args, **kwargs):
        norm_dst = os.path.abspath(os.fsdecode(os.fspath(dst)))
        norm_src = os.path.abspath(os.fsdecode(os.fspath(src)))
        with lock:
            tracked_handles[:] = [(p, h) for p, h in tracked_handles if not getattr(h, "closed", True)]
            open_for_dst = [h for p, h in tracked_handles if p == norm_dst and not getattr(h, "closed", True)]
            open_for_src = [h for p, h in tracked_handles if p == norm_src and not getattr(h, "closed", True)]
        if open_for_dst or open_for_src:
            raise PermissionError("[WinError 5] Access is denied")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracked_open)
    monkeypatch.setattr(os, "replace", checked_replace)


def test_failure_guard_opens_circuit_after_threshold_and_rate_limits(tmp_path):
    guard_path = tmp_path / "guard.json"
    cookie_path = tmp_path / "xianyu_state.json"
    cookie_path.write_text("{}", encoding="utf-8")

    guard = FailureGuard(
        path=str(guard_path),
        threshold=3,
        pause_seconds=3 * 24 * 60 * 60,
        tz_name="Asia/Shanghai",
    )

    base = datetime(2026, 3, 4, 12, 0, 0)

    r1 = guard.record_failure("task-a", "err-1", cookie_path=str(cookie_path), now=base)
    assert r1["should_notify"] is False
    assert r1["opened_circuit"] is False

    r2 = guard.record_failure("task-a", "err-2", cookie_path=str(cookie_path), now=base)
    assert r2["should_notify"] is False
    assert r2["opened_circuit"] is False

    r3 = guard.record_failure("task-a", "err-3", cookie_path=str(cookie_path), now=base)
    assert r3["should_notify"] is True
    assert r3["opened_circuit"] is True
    assert r3["paused_until"] is not None

    d0 = guard.should_skip_start("task-a", cookie_path=str(cookie_path), now=base)
    assert d0.skip is True
    assert d0.should_notify is False

    next_day = base + timedelta(days=1, minutes=1)
    d1 = guard.should_skip_start("task-a", cookie_path=str(cookie_path), now=next_day)
    assert d1.skip is True
    assert d1.should_notify is True

    d1b = guard.should_skip_start("task-a", cookie_path=str(cookie_path), now=next_day)
    assert d1b.skip is True
    assert d1b.should_notify is False


def test_failure_guard_auto_recovers_on_cookie_change(tmp_path):
    guard_path = tmp_path / "guard.json"
    cookie_path = tmp_path / "xianyu_state.json"
    cookie_path.write_text("{}", encoding="utf-8")

    guard = FailureGuard(
        path=str(guard_path),
        threshold=2,
        pause_seconds=3 * 24 * 60 * 60,
        tz_name="Asia/Shanghai",
    )

    base = datetime(2026, 3, 4, 12, 0, 0)

    guard.record_failure("task-a", "err-1", cookie_path=str(cookie_path), now=base)
    guard.record_failure("task-a", "err-2", cookie_path=str(cookie_path), now=base)

    paused = guard.should_skip_start("task-a", cookie_path=str(cookie_path), now=base)
    assert paused.skip is True

    cookie_path.write_text('{"updated": true}', encoding="utf-8")

    recovered = guard.should_skip_start(
        "task-a",
        cookie_path=str(cookie_path),
        now=base + timedelta(minutes=1),
    )
    assert recovered.skip is False


def test_failure_guard_replace_does_not_hold_open_target_handle(tmp_path, monkeypatch):
    _install_windows_replace_guard(monkeypatch)
    guard_path = tmp_path / "guard.json"
    cookie_path = tmp_path / "xianyu_state.json"
    cookie_path.write_text("{}", encoding="utf-8")

    guard = FailureGuard(
        path=str(guard_path),
        threshold=2,
        pause_seconds=3 * 24 * 60 * 60,
        tz_name="Asia/Shanghai",
    )
    base = datetime(2026, 3, 4, 12, 0, 0)

    guard.record_failure("task-a", "err-1", cookie_path=str(cookie_path), now=base)
    guard.record_failure("task-a", "err-2", cookie_path=str(cookie_path), now=base)

    next_day = base + timedelta(days=1, minutes=1)
    decision = guard.should_skip_start("task-a", cookie_path=str(cookie_path), now=next_day)
    assert decision.skip is True
    assert decision.should_notify is True

    guard.record_success("task-a", now=next_day)
    assert guard_path.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_failure_guard_cleans_up_tmp_file_when_replace_fails(tmp_path, monkeypatch):
    guard_path = tmp_path / "guard.json"
    guard = FailureGuard(path=str(guard_path), threshold=2, pause_seconds=3600)

    def fail_replace(_src, _dst, *_args, **_kwargs):
        raise PermissionError("[WinError 5] Access is denied")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(PermissionError, match="WinError 5"):
        guard.record_failure("task-a", "err-1")

    assert list(tmp_path.glob("*.tmp")) == []


def test_failure_guard_multithreaded_concurrent_writes(tmp_path, monkeypatch):
    _install_windows_replace_guard(monkeypatch)
    guard_path = tmp_path / "guard.json"
    guard = FailureGuard(path=str(guard_path), threshold=100, pause_seconds=3600)
    base = datetime(2026, 3, 4, 12, 0, 0)

    num_threads = 8
    loops_per_thread = 3
    barrier = threading.Barrier(num_threads)
    errors: list[BaseException] = []

    def worker(idx: int):
        try:
            barrier.wait(timeout=5)
            for step in range(loops_per_thread):
                guard.record_failure("shared-task", f"err-{idx}-{step}", now=base)
                guard.record_failure(f"task-{idx}", f"err-{step}", now=base)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive()

    assert errors == []
    assert list(tmp_path.glob("*.tmp")) == []

    payload = json.loads(guard_path.read_text(encoding="utf-8"))
    assert payload["tasks"]["shared-task"]["consecutive_failures"] == num_threads * loops_per_thread
    for i in range(num_threads):
        assert payload["tasks"][f"task-{i}"]["consecutive_failures"] == loops_per_thread


def test_file_lock_uses_msvcrt_locking_on_windows(tmp_path, monkeypatch):
    lock_file = str(tmp_path / "guard.json.lock")
    calls: list[tuple[int, int]] = []
    fake_msvcrt = SimpleNamespace(
        LK_NBLCK=2,
        LK_UNLCK=0,
        locking=lambda _fd, mode, nbytes: calls.append((mode, nbytes)),
    )
    monkeypatch.setitem(sys.modules, "msvcrt", fake_msvcrt)
    monkeypatch.setattr("src.failure_guard.os.name", "nt", raising=False)

    lock = _FileLock(lock_file)
    with lock:
        assert lock._fh is not None
        assert lock._fh.closed is False
        assert calls == [(2, 1)]

    assert lock._fh is None
    assert calls == [(2, 1), (0, 1)]


def test_failure_guard_concurrent_read_and_write_holds_lock_and_avoids_winerror5(
    tmp_path, monkeypatch
):
    guard_path = tmp_path / "guard.json"
    lock_path = tmp_path / "guard.json.lock"
    cookie_path = tmp_path / "state.json"
    cookie_path.write_text("{}", encoding="utf-8")

    norm_guard = os.path.abspath(str(guard_path))
    norm_lock = os.path.abspath(str(lock_path))

    real_open = builtins.open
    real_replace = os.replace
    state_lock = threading.Lock()
    tracked_handles: list[tuple[str, object, int]] = []

    def tracked_open(file, *args, **kwargs):
        tid = threading.get_ident()
        if isinstance(file, (str, bytes, os.PathLike)):
            norm_path = os.path.abspath(os.fsdecode(os.fspath(file)))
            if norm_path == norm_guard:
                with state_lock:
                    tracked_handles[:] = [
                        (p, h, owner)
                        for p, h, owner in tracked_handles
                        if not getattr(h, "closed", True)
                    ]
                    lock_open = any(
                        p == norm_lock and owner == tid
                        for p, _, owner in tracked_handles
                    )
                if not lock_open:
                    raise PermissionError("Opened target guard file without holding .lock")
        fh = real_open(file, *args, **kwargs)
        if isinstance(file, (str, bytes, os.PathLike)):
            norm_path = os.path.abspath(os.fsdecode(os.fspath(file)))
            with state_lock:
                tracked_handles[:] = [
                    (p, h, owner)
                    for p, h, owner in tracked_handles
                    if not getattr(h, "closed", True)
                ]
                tracked_handles.append((norm_path, fh, tid))
        return fh

    def checked_replace(src, dst, *args, **kwargs):
        norm_dst = os.path.abspath(os.fsdecode(os.fspath(dst)))
        norm_src = os.path.abspath(os.fsdecode(os.fspath(src)))
        with state_lock:
            tracked_handles[:] = [
                (p, h, owner)
                for p, h, owner in tracked_handles
                if not getattr(h, "closed", True)
            ]
            open_for_dst = [p for p, _, _ in tracked_handles if p == norm_dst]
            open_for_src = [p for p, _, _ in tracked_handles if p == norm_src]
        if open_for_dst or open_for_src:
            raise PermissionError("[WinError 5] Access is denied")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", tracked_open)
    monkeypatch.setattr(os, "replace", checked_replace)

    guard = FailureGuard(path=str(guard_path), threshold=2, pause_seconds=3600)
    base = datetime(2026, 3, 4, 12, 0, 0)

    barrier = threading.Barrier(6)
    errors: list[BaseException] = []

    def writer(idx: int):
        try:
            barrier.wait(timeout=5)
            for step in range(4):
                guard.record_failure(
                    "shared-task",
                    f"err-{idx}-{step}",
                    cookie_path=str(cookie_path),
                    now=base + timedelta(seconds=step),
                )
        except BaseException as exc:
            errors.append(exc)

    def reader():
        try:
            barrier.wait(timeout=5)
            for step in range(6):
                guard.should_skip_start(
                    "shared-task",
                    cookie_path=str(cookie_path),
                    now=base + timedelta(days=step % 2, seconds=step),
                )
        except BaseException as exc:
            errors.append(exc)

    threads = [
        *[threading.Thread(target=writer, args=(i,)) for i in range(3)],
        *[threading.Thread(target=reader) for _ in range(3)],
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive()

    assert errors == []
    assert list(tmp_path.glob("*.tmp")) == []


def test_corrupt_quarantine_waits_for_lock_and_preserves_concurrent_valid_write(tmp_path):
    guard_path = tmp_path / "guard.json"
    guard = FailureGuard(path=str(guard_path), threshold=2, pause_seconds=3600)
    base = datetime(2026, 3, 4, 12, 0, 0)

    # Simulate transient half-written/corrupt state while writer holds .lock
    guard_path.write_text("{corrupt", encoding="utf-8")
    decisions = []

    with _FileLock(f"{guard_path}.lock"):
        reader_thread = threading.Thread(
            target=lambda: decisions.append(guard.should_skip_start("task-a", now=base))
        )
        reader_thread.start()
        time.sleep(0.05)
        # Reader must still be waiting on .lock rather than quarantining unlocked
        assert reader_thread.is_alive()

        valid_data = {
            "version": 1,
            "tasks": {
                "task-a": {
                    "consecutive_failures": 2,
                    "paused_until": (base + timedelta(hours=1)).isoformat(),
                    "last_failure_reason": "risk",
                    "last_notified_date": base.date().isoformat(),
                }
            },
        }
        guard_path.write_text(json.dumps(valid_data), encoding="utf-8")

    reader_thread.join(timeout=5)
    assert not reader_thread.is_alive()
    assert len(decisions) == 1
    assert decisions[0].skip is True
    assert list(tmp_path.glob("*.corrupt.*")) == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX flock test")
def test_file_lock_raises_when_posix_flock_fails_and_releases_thread_lock(
    tmp_path, monkeypatch
):
    import fcntl

    guard_path = tmp_path / "guard.json"
    guard = FailureGuard(path=str(guard_path), threshold=2, pause_seconds=3600)

    def broken_flock(_fd, _op):
        raise OSError(errno.ENOTSUP, "Operation not supported")

    monkeypatch.setattr(fcntl, "flock", broken_flock)

    with pytest.raises(OSError) as exc_info:
        guard.record_failure("task-a", "err-1")
    assert exc_info.value.errno == errno.ENOTSUP

    # Restoring flock must succeed without deadlocking _thread_lock
    monkeypatch.undo()
    result = guard.record_failure("task-a", "err-1")
    assert result["consecutive_failures"] == 1


def test_read_permission_error_aborts_update_without_quarantining_or_wiping_tasks(
    tmp_path, monkeypatch
):
    guard_path = tmp_path / "guard.json"
    guard = FailureGuard(path=str(guard_path), threshold=2, pause_seconds=3600)
    base = datetime(2026, 3, 4, 12, 0, 0)

    guard.record_failure("task-a", "err-a1", now=base)
    guard.record_failure("task-a", "err-a2", now=base)
    guard.record_failure("task-b", "err-b1", now=base)
    guard.record_failure("task-b", "err-b2", now=base)
    original_bytes = guard_path.read_bytes()

    norm_guard = os.path.abspath(str(guard_path))
    real_open = builtins.open

    def deny_guard_read(file, mode="r", *args, **kwargs):
        if (
            isinstance(file, (str, bytes, os.PathLike))
            and os.path.abspath(os.fsdecode(os.fspath(file))) == norm_guard
            and "r" in mode
        ):
            raise PermissionError(errno.EACCES, "Permission denied", str(file))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", deny_guard_read)
    with pytest.raises(PermissionError):
        guard.record_failure("task-c", "err-c1", now=base + timedelta(minutes=1))
    with pytest.raises(PermissionError):
        guard.should_skip_start("task-c", now=base + timedelta(minutes=1))

    monkeypatch.undo()
    assert guard_path.exists()
    assert list(tmp_path.glob("*.corrupt.*")) == []
    assert guard_path.read_bytes() == original_bytes
    payload = json.loads(guard_path.read_text(encoding="utf-8"))
    assert set(payload["tasks"].keys()) == {"task-a", "task-b"}

    # On non-root POSIX, also verify real filesystem chmod 0o200 write-only mode
    if os.name != "nt" and getattr(os, "geteuid", lambda: 1)() != 0:
        os.chmod(guard_path, 0o200)
        try:
            with pytest.raises(PermissionError):
                guard.record_failure("task-c", "err-c2", now=base + timedelta(minutes=2))
        finally:
            os.chmod(guard_path, 0o600)
        assert list(tmp_path.glob("*.corrupt.*")) == []
        assert guard_path.read_bytes() == original_bytes
