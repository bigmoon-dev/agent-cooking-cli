"""Tests for workspace_lock.py — file-based cross-process lock."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from triageflow.workspace_lock import workspace_lock


def test_basic_acquire_release(tmp_path: Path) -> None:
    """Lock file is created during context and removed after."""
    lock_path = tmp_path / "test.lock"
    assert not lock_path.exists()
    with workspace_lock(lock_path):
        assert lock_path.exists()
    assert not lock_path.exists()


def test_double_acquire_blocks(tmp_path: Path) -> None:
    """A second acquire blocks while the first is held."""
    lock_path = tmp_path / "test.lock"
    acquired = threading.Event()
    released = threading.Event()

    def _holder() -> None:
        with workspace_lock(lock_path):
            acquired.set()
            released.wait(timeout=5)

    t = threading.Thread(target=_holder, daemon=True)
    t.start()
    acquired.wait(timeout=5)

    # The lock is held — a short-timeout acquire should fail.
    with pytest.raises(TimeoutError):
        with workspace_lock(lock_path, timeout_s=0.2, poll_interval_s=0.05):
            pass  # pragma: no cover

    released.set()
    t.join(timeout=5)


def test_timeout_on_contention(tmp_path: Path) -> None:
    """Contention with very short timeout → TimeoutError."""
    lock_path = tmp_path / "test.lock"
    # Manually create the lock file to simulate a held lock.
    fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)

    with pytest.raises(TimeoutError):
        with workspace_lock(lock_path, timeout_s=0.15, poll_interval_s=0.05, stale_after_s=9999):
            pass  # pragma: no cover


def test_stale_lock_dead_pid_reaped(tmp_path: Path) -> None:
    """Lock with a dead PID is reaped and acquire succeeds."""
    lock_path = tmp_path / "test.lock"
    # Write a PID that is very unlikely to be alive.
    dead_pid = 2_000_000_000  # way above normal PID range
    lock_path.write_text(str(dead_pid), encoding="utf-8")

    with workspace_lock(lock_path, timeout_s=1.0, poll_interval_s=0.05):
        assert lock_path.exists()  # re-created by our acquisition
    assert not lock_path.exists()


def test_stale_lock_unparseable_pid_old_mtime(tmp_path: Path) -> None:
    """Lock with unparseable PID and old mtime is reaped."""
    lock_path = tmp_path / "test.lock"
    lock_path.write_text("not-a-pid", encoding="utf-8")
    # Backdate mtime to appear stale.
    old_time = time.time() - 120
    os.utime(str(lock_path), (old_time, old_time))

    with workspace_lock(lock_path, timeout_s=1.0, poll_interval_s=0.05, stale_after_s=60):
        assert lock_path.exists()
    assert not lock_path.exists()


def test_stale_lock_unparseable_pid_recent_mtime(tmp_path: Path) -> None:
    """Lock with unparseable PID but recent mtime is NOT reaped → timeout."""
    lock_path = tmp_path / "test.lock"
    lock_path.write_text("not-a-pid", encoding="utf-8")
    # mtime is fresh (just written), stale_after_s is large — should NOT reap.

    with pytest.raises(TimeoutError):
        with workspace_lock(lock_path, timeout_s=0.2, poll_interval_s=0.05, stale_after_s=9999):
            pass  # pragma: no cover


def test_exception_during_yield_cleans_up(tmp_path: Path) -> None:
    """If the body raises, the lock file is still cleaned up."""
    lock_path = tmp_path / "test.lock"

    with pytest.raises(RuntimeError, match="boom"):
        with workspace_lock(lock_path):
            assert lock_path.exists()
            raise RuntimeError("boom")

    assert not lock_path.exists()
