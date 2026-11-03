from __future__ import annotations

import sys

from src.ai_handler import _ensure_utf8_stdio


class _FakeStream:
    def __init__(self) -> None:
        self.reconfigure_calls: list[dict] = []
        self.detached = False

    def reconfigure(self, **kwargs) -> None:
        self.reconfigure_calls.append(kwargs)

    def detach(self):
        self.detached = True
        raise AssertionError("stdio streams must not be detached")


def test_ensure_utf8_stdio_keeps_stream_objects(monkeypatch):
    stdout = _FakeStream()
    stderr = _FakeStream()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    _ensure_utf8_stdio()

    expected = {"encoding": "utf-8", "errors": "replace"}
    assert stdout.reconfigure_calls == [expected]
    assert stderr.reconfigure_calls == [expected]
    assert stdout.detached is False
    assert stderr.detached is False


def test_ensure_utf8_stdio_ignores_streams_without_reconfigure(monkeypatch):
    monkeypatch.setattr(sys, "stdout", object())
    monkeypatch.setattr(sys, "stderr", object())

    _ensure_utf8_stdio()
