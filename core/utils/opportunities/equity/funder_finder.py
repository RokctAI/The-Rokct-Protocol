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

# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.
import requests
from bs4 import BeautifulSoup
import re
import time
from pathlib import Path
import sys

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

# Ensure common imports
sys.path.append(str(BASE_DIR / ".rokct" / "scripts" / "equity"))
from funder_manager import FunderManager, is_junk_heading


def _get_with_retries(url, headers, attempts=3, timeout=15):
    """Bounded retries with backoff so one transient network error doesn't
    cost the whole source. Calls requests.get (not a Session) on purpose:
    equity_sync.py monkeypatches requests.get to serve file:// URLs in
    local runs, and that hook must keep working."""
    last_err = None
    for attempt in range(attempts):
        try:
            return requests.get(url, timeout=timeout, headers=headers)
        except requests.RequestException as e:
            last_err = e
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
    raise last_err


def find_candidates(url):
    manager = FunderManager(registry_path=str(BASE_DIR / "01_equity"))
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "X-Trace-Id": "duckduckgo-query",
        }
        response = _get_with_retries(url, headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        candidates = []

        # 1. Failory pattern (<h2>1. <a ...>Name</a></h2>)
        if "failory.com" in url:
            for h2 in soup.find_all(["h2", "h3"]):
                text = h2.get_text().strip()
                match = re.search(r"^\d+\.\s+(.*)", text)
                if match:
                    candidates.append(match.group(1).strip())

        # 2. Eqvista table pattern
        elif "eqvista.com" in url:
            table = soup.find("table")
            if table:
                for row in table.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if len(cols) > 1:
                        name = cols[1].get_text().strip()
                        candidates.append(name)

        # 3. Visible.vc pattern (often in <h3> or <h4>)
        elif "visible.vc" in url:
            for h in soup.find_all(["h2", "h3", "h4"]):
                text = h.get_text().strip()
                match = re.search(r"^\d+\.\s+(.*)", text)
                if match:
                    candidates.append(match.group(1).strip())
                elif re.match(
                    r"^[A-Z][a-zA-Z\s]+(Investimentos|Capital|Ventures|Partners)$", text
                ):
                    candidates.append(text)

        # 4. BaseTemplates pattern
        elif "basetemplates.com" in url:
            for item in soup.find_all(["h3", "strong"]):
                text = item.get_text().strip()
                if 2 < len(text) < 40 and not any(
                    x in text.lower() for x in ["menu", "login"]
                ):
                    candidates.append(text)

        # 5. Shizune pattern
        elif "shizune.co" in url:
            for item in soup.find_all(["h3", "strong"]):
                text = item.get_text().strip()
                match = re.search(r"^\d+\.\s+(.*)", text)
                if match:
                    candidates.append(match.group(1).strip())
                elif 3 < len(text) < 40 and re.match(r"^[A-Z][a-zA-Z\s0-9]+$", text):
                    candidates.append(text)

        # Generic fallback
        else:
            for h3 in soup.find_all(["h2", "h3"]):
                text = h3.get_text().strip()
                if 3 < len(text) < 50 and not any(
                    x in text.lower() for x in ["menu", "login", "search"]
                ):
                    candidates.append(text)

        unique_new = []
        for name in list(set(candidates)):
            name = name.split("|")[0].strip()  # Clean up pipe suffixes
            if not (len(name) > 2 and len(name) < 60):
                continue
            # Navigation/FAQ/promo headings ("Contents", "See also",
            # "What is a venture capital firm?", "60% off") are not funders;
            # the consumer repo's denylist blocks known junk slugs for good.
            if is_junk_heading(name) or manager.is_denylisted(name):
                print(f"Skipping non-funder heading from {url}: {name!r}")
                continue
            if not manager.is_duplicate(name):
                unique_new.append(name)

        return unique_new
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []
