# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Watch an inbox folder and render every new or changed ad JSON.

Polling, one render at a time (the model needs most of the RAM). State is
kept in <inbox>/.watch_state.json as {filename: sha256 of last attempt}, so
restarting the watcher does not re-render finished ads, and editing a JSON
re-renders it (and thanks to the line cache, only the lines that changed).

    inbox/foo.json          picked up
    out/<id>/...            results
    failed/foo.json         moved here if validation or rendering fails
    failed/foo.error.txt    why
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
import traceback
from pathlib import Path

from .pipeline import make_ad


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable(path: Path, wait: float = 1.0) -> bool:
    """True if the file stopped changing (a copy in progress is skipped)."""
    try:
        a = path.stat()
        time.sleep(wait)
        b = path.stat()
    except FileNotFoundError:
        return False
    return (a.st_size, a.st_mtime_ns) == (b.st_size, b.st_mtime_ns) and b.st_size > 0


def watch(inbox: Path, out_root: Path, failed_dir: Path | None = None, interval: float = 3.0,
          once: bool = False, **make_kwargs) -> None:
    inbox = Path(inbox).resolve()
    inbox.mkdir(parents=True, exist_ok=True)
    out_root = Path(out_root).resolve()
    failed_dir = Path(failed_dir or inbox.parent / "failed").resolve()
    failed_dir.mkdir(parents=True, exist_ok=True)
    state_path = inbox / ".watch_state.json"
    try:
        state = json.loads(state_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    print(f"watching {inbox} -> {out_root} (failures -> {failed_dir}); Ctrl-C to stop", flush=True)
    while True:
        for path in sorted(inbox.glob("*.json")):
            if not _stable(path, 0.5):
                continue
            digest = _sha(path)
            if state.get(path.name) == digest:
                continue
            print(f"\n== {path.name}", flush=True)
            try:
                make_ad(path, out_root, **make_kwargs)
                state[path.name] = digest
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001 - report every failure
                dest = failed_dir / path.name
                shutil.move(str(path), dest)
                (failed_dir / (path.stem + ".error.txt")).write_text(
                    f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}", encoding="utf-8")
                print(f"  FAILED: {exc}\n  moved to {dest}", flush=True)
                state.pop(path.name, None)
            state_path.write_text(json.dumps(state, indent=1))
        # Forget files that were removed from the inbox.
        for name in [n for n in state if not (inbox / n).exists()]:
            del state[name]
        if once:
            return
        time.sleep(interval)
