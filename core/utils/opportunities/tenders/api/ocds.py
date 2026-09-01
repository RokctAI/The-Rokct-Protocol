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

# Licensed under the MIT License.
# Copyright 2024 ROKCT INTELLIGENCE (PTY) LTD
# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.

# --- INGESTION TRANSPORT ---
# The OCDS *list* endpoint (GET .../OCDSReleases?dateFrom=..&PageNumber=..)
# uses unstable OFFSET pagination that silently drops rows: an identical
# 7-day window probed on 2026-08-20 returned only 63 of 344 unique releases
# at PageSize=50, with intra-run duplicates and spurious short/empty pages.
# The single-release endpoint (GET .../OCDSReleases/release/{prefix}-{N})
# is stable, and eTenders ocids embed a sequential integer, so this module
# enumerates release IDs instead:
#   1. binary-search the current max ID upward from the last synced max
#      (persisted in 03_tenders/sources/ocds_sync_state.json in the host
#      repo checkout, committed with the sync results),
#   2. fetch every new ID above the last synced max,
#   3. re-fetch a trailing window of recent IDs, because releases gain
#      awards/amendments after first publication.
# Never-published IDs return a stable `{}` (skipped); IDs that keep
# returning HTTP 5xx after the session's retry budget are recorded in the
# state file and skipped on later runs. The card OUTPUT format is unchanged:
# releases are still rendered through the caller's generate_md_fn.

import json
import os
import requests
import re
import time
from datetime import datetime
from pathlib import Path
import sys
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent / "utils"))
from tender_resolver import resolve_card_path, resolve_write_path

# eTenders South Africa's registered OCDS prefix; a source card can override
# it with `- **OCID Prefix**: ocds-xxxxxx`.
DEFAULT_OCID_PREFIX = "ocds-9t57fa"

STATE_FILENAME = "ocds_sync_state.json"

# Width of the existence-probe window used while searching for the max ID.
# A probe asks "is any of [n, n+W) published?"; ~2% of IDs are never
# published, so W=12 consecutive unpublished IDs below the true max is
# vanishingly unlikely to be mistaken for "past the end".
PROBE_WINDOW = 12

# Re-fetch this many IDs below the last synced max on every run, so recent
# releases pick up awards/amendments (roughly 90 days of publications at
# current eTenders volume). Override with OCDS_REFRESH_COUNT.
REFRESH_COUNT = int(os.environ.get("OCDS_REFRESH_COUNT", "6000"))

# Safety cap on new IDs ingested per run (a bad state file or an API burst
# must not turn one run into a full-corpus crawl). The state only advances
# past IDs that were actually fetched, so a clamped run resumes next time.
MAX_NEW_IDS = int(os.environ.get("OCDS_MAX_NEW_IDS", "25000"))

# Polite delay between single-release requests, seconds.
THROTTLE_SECONDS = float(os.environ.get("OCDS_THROTTLE_SECONDS", "0.05"))


def _build_session():
    session = requests.Session()
    # Same resilience style as before, extended to retry transient 5xx on
    # the single-release GETs; an ID that exhausts this budget is treated
    # as persistently broken and recorded in the state file.
    session.mount(
        "https://",
        HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=(500, 502, 503, 504),
                allowed_methods=("GET",),
            )
        ),
    )
    session.headers.update({"User-Agent": "Mozilla/5.0 RokctAI-Sync/1.0"})
    return session


def _load_configs(sources_dir):
    configs = []
    if not sources_dir.exists():
        return configs
    for sf in sorted(sources_dir.glob("*.md")):
        # Per-file isolation: one unreadable source card must not
        # abort the scan of the remaining sources.
        try:
            with open(sf, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError as e:
            print(f"  [Error] Unreadable source card {sf.name}: {e}")
            continue
        if (
            re.search(r"-\s+\*\*Is API\*\*:\s*true", content, re.I)
            and "OCDS" in content
        ):
            u = re.search(r"URL\*\*:\s*(https?://[^\s\n]+)", content)
            f_match = re.search(r"Flag\*\*:\s*([A-Z]{2})", content)
            p_match = re.search(r"OCID Prefix\*\*:\s*(\S+)", content)
            if u and f_match:
                configs.append(
                    {
                        "url": u.group(1).strip().rstrip("/"),
                        "flag": f_match.group(1).strip(),
                        "ref": f"sources/{sf.name}",
                        "prefix": (
                            p_match.group(1).strip() if p_match else DEFAULT_OCID_PREFIX
                        ),
                    }
                )
    return configs


def _load_state(state_path):
    """Read the per-prefix sync state; malformed or missing files start fresh."""
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state, dict):
            return state
    except (OSError, ValueError):
        pass
    return {}


def _save_state(state_path, state):
    """Atomic, deterministic (sorted keys, LF) state write."""
    tmp_path = state_path.with_name(state_path.name + f".tmp{os.getpid()}")
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp_path, state_path)


class _ReleaseFetcher:
    """Caching single-release fetcher with `{}` and persistent-5xx handling."""

    def __init__(self, session, cfg):
        self.session = session
        self.base = cfg["url"]
        self.prefix = cfg["prefix"]
        self.cache = {}
        self.requests_made = 0
        self.failed_ids = set()

    def fetch(self, num):
        """Return the release dict for ID `num`, or None (unpublished/failed).

        Failed IDs (retry budget exhausted) are added to self.failed_ids;
        never-published IDs (`{}`) are cached as None and skipped silently.
        """
        if num in self.cache:
            return self.cache[num]
        url = f"{self.base}/release/{self.prefix}-{num}"
        release = None
        try:
            self.requests_made += 1
            time.sleep(THROTTLE_SECONDS)
            resp = self.session.get(url, timeout=60)
            resp.raise_for_status()
            payload = resp.json()
            # Never-published IDs return a stable empty object; anything
            # non-dict is schema drift and treated as absent.
            if isinstance(payload, dict) and payload.get("ocid"):
                release = payload
        except requests.RequestException as e:
            self.failed_ids.add(num)
            print(f"  [Error] {self.prefix}-{num}: {e}")
        except ValueError:
            self.failed_ids.add(num)
            print(f"  [Error] {self.prefix}-{num}: invalid JSON payload")
        self.cache[num] = release
        return release

    def window_max(self, start):
        """Highest published ID in [start, start+PROBE_WINDOW), or None."""
        best = None
        for num in range(start, start + PROBE_WINDOW):
            if self.fetch(num) is not None:
                best = num
        return best


def _discover_max_id(fetcher, last_max):
    """Find the highest published release ID via exponential + binary search.

    The predicate "some ID in [n, n+PROBE_WINDOW) is published" is monotone
    (True at or below the max, False past it), so the boundary is found with
    O(log gap) probes; the fetched payloads stay in the fetcher's cache and
    are reused by the ingestion pass.
    """
    lo = max(last_max, 0)
    if fetcher.window_max(lo + 1) is None:
        # Nothing published above the last synced max.
        return last_max
    step = 64
    hi = lo + step
    while fetcher.window_max(hi + 1) is not None:
        lo = hi
        step = min(step * 2, 65536)
        hi = lo + step
    # Invariant: window at lo+1 has releases, window at hi+1 has none.
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if fetcher.window_max(mid + 1) is not None:
            lo = mid
        else:
            hi = mid
    # Walk the tail forward: never-published IDs can cluster, so the probe
    # predicate is only near-monotone; keep advancing until PROBE_WINDOW
    # consecutive IDs above the candidate are all unpublished. A small
    # undershoot is self-healing anyway - the next run restarts its search
    # from the persisted max and the trailing re-fetch window overlaps it.
    cand = fetcher.window_max(lo + 1)
    if cand is None:
        return last_max
    while True:
        nxt = fetcher.window_max(cand + 1)
        if nxt is None:
            return cand
        cand = nxt


def _write_card(tender_dir, cfg, release, generate_md_fn):
    """Render one release through generate_md_fn; returns True if updated.

    Identical card semantics to the old list-endpoint sync: VERIFIED cards
    are never touched, unchanged content is not rewritten, and writes are
    atomic so a crash mid-write can never leave a truncated card behind.
    """
    ocid = release.get("ocid")
    card_path = resolve_card_path(tender_dir, ocid)
    existing = ""
    if card_path and card_path.exists():
        with open(card_path, "r", encoding="utf-8", errors="ignore") as f:
            existing = f.read()
        if "VERIFIED" in existing:
            return False

    new_c = generate_md_fn(release, cfg["flag"], cfg["ref"], existing)
    if [line.strip() for line in existing.splitlines() if line.strip()] == [
        line.strip() for line in new_c.splitlines() if line.strip()
    ]:
        return False
    write_path = resolve_write_path(tender_dir, ocid)
    tmp_path = write_path.with_name(write_path.name + f".tmp{os.getpid()}")
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as fw:
        fw.write(new_c)
    os.replace(tmp_path, write_path)
    return True


def _sync_source(session, cfg, tender_dir, state_path, generate_md_fn):
    state = _load_state(state_path)
    src_state = state.get(cfg["prefix"], {})
    last_max = int(src_state.get("last_max_id", 0) or 0)
    known_bad = set(int(n) for n in src_state.get("known_bad_ids", []))

    fetcher = _ReleaseFetcher(session, cfg)
    current_max = _discover_max_id(fetcher, last_max)
    if last_max <= 0:
        # Bootstrap (no persisted state): don't crawl the whole corpus from
        # ID 1 - ingest only the trailing window below the discovered max,
        # exactly like an ordinary incremental run.
        print(f"  [{cfg['flag']}] Bootstrap: discovered max ID {current_max}.")
        last_max = current_max
    if current_max <= last_max:
        print(f"  [{cfg['flag']}] No new release IDs (max still {last_max}).")
        current_max = last_max

    new_lo = last_max + 1
    new_hi = current_max
    if new_hi - new_lo + 1 > MAX_NEW_IDS:
        new_hi = new_lo + MAX_NEW_IDS - 1
        print(
            f"  [{cfg['flag']}] Clamping run to {MAX_NEW_IDS} new IDs "
            f"({new_lo}..{new_hi} of {current_max}); the rest resume next run."
        )

    # Trailing window below the last synced max: recent releases gain
    # awards/amendments after first publication and must be re-fetched.
    refresh_lo = max(1, new_lo - REFRESH_COUNT)
    id_ranges = (range(refresh_lo, new_lo), range(new_lo, new_hi + 1))

    updates = 0
    published = 0
    unpublished = 0
    failures = 0
    for id_range in id_ranges:
        for num in id_range:
            if num in known_bad:
                continue
            release = fetcher.fetch(num)
            if release is None:
                if num not in fetcher.failed_ids:
                    unpublished += 1
                continue
            published += 1
            # Per-item isolation: one malformed release or unwritable card
            # logs and skips - it must never abort the rest of the sync.
            try:
                if _write_card(tender_dir, cfg, release, generate_md_fn):
                    updates += 1
            except Exception as e:
                failures += 1
                print(f"  [Error] {cfg['flag']} release {release.get('ocid')}: {e}")

    # Only advance past IDs this run actually walked (new_hi, not
    # current_max, when clamped); persistently failing IDs inside the walked
    # range are recorded so later runs skip them without re-requesting.
    # A large failure count means a systemic outage, not broken IDs (the API
    # has only ~32 persistently-500 IDs in 166k) - recording those would
    # skip them forever, so they are left for the next run's overlapping
    # refresh window instead.
    new_last_max = max(last_max, new_hi)
    if len(fetcher.failed_ids) <= 50:
        known_bad.update(n for n in fetcher.failed_ids if n <= new_last_max)
    elif fetcher.failed_ids:
        print(
            f"  [Warn] {cfg['flag']}: {len(fetcher.failed_ids)} failed fetches "
            "look systemic; not recording them as permanently bad IDs."
        )
    state[cfg["prefix"]] = {
        "last_max_id": new_last_max,
        "known_bad_ids": sorted(known_bad),
        "last_run": datetime.now().strftime("%Y-%m-%d"),
    }
    _save_state(state_path, state)

    print(
        f"  [+] {cfg['flag']}: walked IDs {refresh_lo}..{new_hi} "
        f"({fetcher.requests_made} requests): {published} published, "
        f"{unpublished} unpublished, {len(fetcher.failed_ids)} failed. "
        f"Updated {updates} files."
        + (f" {failures} card writes failed (see log above)." if failures else "")
    )


def run_sync(tender_dir, sources_dir, generate_md_fn):
    """Resilient OCDS sync via sequential release-ID enumeration."""
    print("[OCDS] Starting API Sync (release-ID enumeration)...")

    session = _build_session()
    state_path = Path(sources_dir) / STATE_FILENAME

    for cfg in _load_configs(sources_dir):
        # Per-source isolation, as before.
        try:
            _sync_source(session, cfg, tender_dir, state_path, generate_md_fn)
        except Exception as e:
            print(f"  [Error] {cfg['flag']} Sync: {e}")
