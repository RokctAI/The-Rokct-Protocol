"""Atomic writes, advisory locking and history for the SSOT.

`questions.md` is the single source of truth, and Hermes mutates it from
conversational handlers. The previous implementation did read → modify →
`open(path, 'w')` with no lock and no backup, so two WhatsApp messages
arriving together could interleave and truncate a founder's profile, with the
only copy of the lost text being the one that was overwritten.
"""

import os
import shutil
import time
from datetime import datetime, timezone

HISTORY_DIRNAME = ".history"
LOCK_SUFFIX = ".lock"
LOCK_TIMEOUT_SECONDS = 15
LOCK_STALE_SECONDS = 120


class FileLock:
    """Advisory cross-process lock via exclusive file creation.

    `O_CREAT | O_EXCL` is atomic on both POSIX and Windows, which is all we
    need here — this guards a markdown file against concurrent agent handlers,
    not a database.
    """

    def __init__(self, target_path, timeout=LOCK_TIMEOUT_SECONDS):
        self.lock_path = str(target_path) + LOCK_SUFFIX
        self.timeout = timeout
        self._fd = None

    def acquire(self):
        deadline = time.monotonic() + self.timeout
        while True:
            self._break_if_stale()
            try:
                self._fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, f"{os.getpid()} {datetime.now(timezone.utc).isoformat()}".encode())
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Could not acquire lock {self.lock_path} within {self.timeout}s. "
                        "Another StartupOS process is writing this profile."
                    )
                time.sleep(0.05)

    def _break_if_stale(self):
        """Reclaim a lock left behind by a crashed process."""
        try:
            age = time.time() - os.path.getmtime(self.lock_path)
        except OSError:
            return
        if age > LOCK_STALE_SECONDS:
            try:
                os.unlink(self.lock_path)
            except OSError:
                pass

    def release(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            os.unlink(self.lock_path)
        except OSError:
            pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc_info):
        self.release()
        return False


def atomic_write(path, content, encoding="utf-8"):
    """Write via a temp file in the same directory, then `os.replace`.

    `os.replace` is atomic on the same filesystem, so a crash mid-write leaves
    the previous file intact rather than a truncated one.
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temp_path = f"{path}.{os.getpid()}.tmp"

    with open(temp_path, "w", encoding=encoding, newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())

    os.replace(temp_path, path)


def snapshot(path, keep=20):
    """Copy `path` into a sibling `.history/` directory before mutating it."""
    if not os.path.exists(path):
        return None

    directory = os.path.dirname(os.path.abspath(path))
    history_dir = os.path.join(directory, HISTORY_DIRNAME)
    os.makedirs(history_dir, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    basename = os.path.basename(path)
    destination = os.path.join(history_dir, f"{stamp}.{basename}")
    shutil.copy2(path, destination)

    _prune_history(history_dir, basename, keep)
    return destination


def _prune_history(history_dir, basename, keep):
    entries = sorted(
        entry for entry in os.listdir(history_dir) if entry.endswith(f".{basename}")
    )
    for stale in entries[:-keep] if len(entries) > keep else []:
        try:
            os.unlink(os.path.join(history_dir, stale))
        except OSError:
            pass


def update_file(path, transform, encoding="utf-8", keep_history=20):
    """Lock, snapshot, transform and atomically rewrite a file.

    `transform` receives the current content and returns the new content.
    Returning `None` aborts the write.
    """
    with FileLock(path):
        with open(path, "r", encoding=encoding) as handle:
            current = handle.read()

        updated = transform(current)
        if updated is None or updated == current:
            return False

        snapshot(path, keep=keep_history)
        atomic_write(path, updated, encoding=encoding)
        return True


def prune_directory(directory, keep_filenames, dry_run=False):
    """Remove files under `directory` that are not in `keep_filenames`.

    Names are relative to `directory` with forward slashes, matching how the
    compiler tracks nested templates such as `annexures/succession_plan.md`.

    Compiled output is derived data. Without this, a renamed or deleted
    template leaves an orphan in `output/` that looks current indefinitely.
    """
    if not os.path.isdir(directory):
        return []

    keep = set(keep_filenames)
    removed = []

    for current, subdirs, filenames in os.walk(directory, topdown=False):
        subdirs[:] = [name for name in subdirs if name != HISTORY_DIRNAME]
        for filename in sorted(filenames):
            full = os.path.join(current, filename)
            relative = os.path.relpath(full, directory).replace(os.sep, "/")
            if relative in keep or relative.split("/")[0] == HISTORY_DIRNAME:
                continue
            removed.append(relative)
            if not dry_run:
                try:
                    os.unlink(full)
                except OSError:
                    pass

        # Drop directories emptied by the pass above.
        if not dry_run and os.path.abspath(current) != os.path.abspath(directory):
            try:
                if not os.listdir(current):
                    os.rmdir(current)
            except OSError:
                pass

    return removed
