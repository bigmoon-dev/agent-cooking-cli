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
) -> Iterator[None]:
    """A tiny cross-process lock using an exclusive lock file.

    Uses O_CREAT|O_EXCL so only one writer can hold the lock.
    """

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_s
    fd = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            break
        except FileExistsError:
            if time.time() >= deadline:
                raise TimeoutError(f"Timed out waiting for lock: {lock_path}")
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
