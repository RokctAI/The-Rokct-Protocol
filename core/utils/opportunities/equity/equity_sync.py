# Copyright (c) 2026 RokctAI
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Licensed under the MIT License.
# Copyright 2024 RokctAI
# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.

import sys
import re
import logging
import requests
from pathlib import Path

# Identify project root
BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / ".rokct").exists():
    if BASE_DIR.parent == BASE_DIR:
        # No .rokct anywhere up the tree (misconfigured checkout) - fall
        # back to CWD, which CI sets to the repo root, instead of spinning
        # forever at the filesystem root.
        BASE_DIR = Path.cwd()
        break
    BASE_DIR = BASE_DIR.parent

# Ensure the equity scripts directory is in path so we can import funder_manager/finder
sys.path.append(str(Path(__file__).resolve().parent))

from funder_manager import FunderManager
from funder_finder import find_candidates

# Setup Logging
LOG_DIR = BASE_DIR / ".rokct" / "agent" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("equity_sync")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(LOG_DIR / "equity_sync.log")
fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(fh)


class LocalFileAdapter(requests.adapters.BaseAdapter):
    def send(self, request, **kwargs):
        from requests import Response
        from urllib.request import url2pathname

        path = url2pathname(request.url[7:])
        resp = Response()
        resp.status_code = 200
        try:
            with open(path, "rb") as f:
                resp._content = f.read()
        except Exception as e:
            resp.status_code = 404
            resp._content = str(e).encode()
        resp.url = request.url
        return resp

    def close(self):
        pass


def get_active_sources():
    sources = []
    sources_dir = BASE_DIR / "01_equity" / "sources"
    if not sources_dir.exists():
        logger.warning("No 01_equity/sources directory found.")
        return sources

    for f in sources_dir.glob("*.md"):
        # Per-file isolation: one unreadable/mis-encoded source card must
        # not abort the scan of the remaining sources.
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            logger.error(f"Unreadable source card {f.name}: {e}")
            continue
        status_match = re.search(r"Status\*\*:\s*(ACTIVE)", content, re.I)
        url_match = re.search(r"URL\*\*:\s*((?:https?|file)://[^\s\n]+)", content)
        if status_match and url_match:
            sources.append({"url": url_match.group(1).strip(), "filename": f.name})
    return sources


def run():
    manager = FunderManager(registry_path=str(BASE_DIR / "01_equity"))
    active_sources = get_active_sources()

    if not active_sources:
        logger.info("No active equity sources found.")
        return

    # Monkeypatch requests for local testing support if file:// is used
    session = requests.Session()
    session.mount("file://", LocalFileAdapter())

    import funder_finder

    original_get = requests.get

    def patched_get(url, **kwargs):
        headers = kwargs.get("headers", {})
        headers["X-Trace-Id"] = "equity-sync-get"
        kwargs["headers"] = headers
        if url.startswith("file://"):
            return session.get(url, **kwargs)
        return original_get(url, **kwargs)

    requests.get = patched_get

    try:
        for source in active_sources:
            url = source["url"]
            logger.info(f"Processing source: {url}")
            try:
                candidates = find_candidates(url)
                logger.info(f"Found {len(candidates)} candidates from {url}")

                new_count = 0
                for name in candidates:
                    if not manager.is_duplicate(name):
                        data = {
                            "Organization": name,
                            "Funder Type": "VC / Accelerator",
                            "Funding Type": "Seed / Series A",
                            "Industry": "Tech",
                            "Territory": "Global",
                            "Country": "Unspecified",
                            "Website": "Unspecified",
                            "Contact Person": "Unspecified",
                            "LinkedIn": "Unspecified",
                            "Phone": "",
                            "Source": url,
                            "Verification Status": "UNVERIFIED",
                            "Notes": f"Discovered via equity sync from {source['filename']}",
                        }
                        try:
                            filepath = manager.create_funder_file(data)
                            logger.info(f"Created new funder card: {filepath}")
                            new_count += 1
                        except Exception as e:
                            logger.error(
                                f"Failed to create funder file for {name}: {e}"
                            )

                logger.info(f"Added {new_count} new funders from {url}")
            except Exception as e:
                logger.error(f"Error processing source {url}: {e}")
    finally:
        requests.get = original_get


if __name__ == "__main__":
    run()
