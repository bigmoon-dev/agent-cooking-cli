from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def workspace_lock(
    lock_path: Path,
    *,
    timeout_s: float = 5.0,
    poll_interval_s: float = 0.05,
    stale_after_s: float = 60.0,
) -> Iterator[None]:
    """A tiny cross-process lock using an exclusive lock file.

    Uses O_CREAT|O_EXCL so only one writer can hold the lock.
    """

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_s
    fd = None

    def _maybe_reap_stale_lock() -> None:
        try:
            raw = lock_path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            raw = ""

        pid = None
        if raw.isdigit():
            try:
                pid = int(raw)
            except ValueError:
                pid = None

        if pid is None:
            try:
                lock_path.unlink()
            except OSError:
                pass
            return

        if os.name == "posix":
            try:
                os.kill(pid, 0)
                return
            except ProcessLookupError:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                return
            except PermissionError:
                return
            except OSError:
                return

        # Non-posix: fall back to mtime-based stale detection.
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            return
        if age >= stale_after_s:
            try:
                lock_path.unlink()
            except OSError:
                pass
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            _maybe_reap_stale_lock()
            if time.time() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for lock: {lock_path}. "
                    "A previous process may have crashed and left a stale lock file."
                )
            time.sleep(poll_interval_s)

    try:
        # Store pid for debugging; ignore errors.
        try:
            os.write(fd, str(os.getpid()).encode("ascii", errors="ignore"))
        except OSError:
            pass
        yield
    finally:
        try:
            if fd is not None:
                os.close(fd)
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
