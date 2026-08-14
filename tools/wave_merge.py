#!/usr/bin/env python3
# Licensed under the MIT License.
# Copyright 2026 RokctAI
"""Wave-merge every open non-draft PR across the RokctAI org in one command.

Org convention: an OPEN non-draft PR is the instruction to merge it; a DRAFT
PR means "don't touch". CI in this org is expected to be red (license-check /
checklist-check are always failing, and private-repo Actions runs die from
minutes exhaustion), so merging deliberately does NOT wait for or require
green checks — the REST merge endpoint merges regardless of check status
unless branch protection blocks it.

Usage:

  export MONOREPO_PAT=ghp_...          # or GITHUB_TOKEN
  python tools/wave_merge.py           # dry-run: list what WOULD merge
  python tools/wave_merge.py --merge   # one y/N confirmation, then merge

Skipped automatically (always listed with the reason):
  - draft PRs
  - PRs authored by bots (any login ending in "[bot]": dependabot[bot],
    rokctbot[bot], claude[bot], google-labs-jules[bot], ...)

Exit codes: 0 = clean (dry-run, or every merge succeeded); 1 = at least one
merge failed (conflict, protection, ...); 2 = usage/auth error.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
DEFAULT_ORG = "RokctAI"
# Extra author logins to skip even without a "[bot]" suffix.
KNOWN_BOT_AUTHORS = {"dependabot", "google-labs-jules", "jules"}


def token():
    for var in ("MONOREPO_PAT", "GITHUB_TOKEN"):
        val = os.environ.get(var)
        if val:
            return val
    sys.exit("error: set MONOREPO_PAT or GITHUB_TOKEN")


def request(method, url, tok, body=None):
    """One API call. Returns (status, parsed-json); never raises on HTTP errors."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "rokct-wave-merge",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            payload = json.load(e)
        except Exception:
            payload = {"message": str(e)}
        return e.code, payload


def paginate(url, tok):
    """Yield items from a paginated list endpoint."""
    page = 1
    while True:
        sep = "&" if "?" in url else "?"
        status, items = request("GET", f"{url}{sep}per_page=100&page={page}", tok)
        if status != 200:
            sys.exit(f"error: GET {url} page {page} -> HTTP {status}: "
                     f"{items.get('message', items)}")
        if not items:
            return
        yield from items
        if len(items) < 100:
            return
        page += 1


def org_repos(org, tok, only=None):
    """Repo names to scan: the whole org, or an explicit --repos subset."""
    if only:
        return [r.strip() for r in only.split(",") if r.strip()]
    return [r["name"] for r in paginate(f"{API}/orgs/{org}/repos?type=all", tok)
            if not r.get("archived")]


def is_bot(login):
    return login.endswith("[bot]") or login.lower() in KNOWN_BOT_AUTHORS


def collect(org, repos, tok):
    """Split every open PR into (candidates, skipped-with-reason)."""
    candidates, skipped = [], []
    for repo in repos:
        for pr in paginate(f"{API}/repos/{org}/{repo}/pulls?state=open", tok):
            author = (pr.get("user") or {}).get("login", "?")
            row = {"repo": repo, "number": pr["number"],
                   "title": pr["title"], "author": author}
            if pr.get("draft"):
                skipped.append({**row, "reason": "draft"})
            elif is_bot(author):
                skipped.append({**row, "reason": f"bot author ({author})"})
            else:
                # mergeable_state needs the single-PR endpoint.
                _, detail = request(
                    "GET", f"{API}/repos/{org}/{repo}/pulls/{pr['number']}", tok)
                row["mergeable_state"] = detail.get("mergeable_state", "unknown")
                candidates.append(row)
    return candidates, skipped


def print_table(rows, columns):
    widths = [max(len(str(r[c])) for r in rows + [dict.fromkeys(columns, c)])
              for c in columns]
    for r in [dict(zip(columns, columns))] + rows:
        print("  ".join(str(r[c]).ljust(w) for c, w in zip(columns, widths)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--merge", action="store_true",
                    help="actually merge (default is dry-run)")
    ap.add_argument("--method", choices=["merge", "squash", "rebase"],
                    default="merge",
                    help="merge method (default: merge, the house habit)")
    ap.add_argument("--org", default=DEFAULT_ORG)
    ap.add_argument("--repos",
                    help="comma-separated repo names to scan instead of the whole org")
    args = ap.parse_args()
    tok = token()

    repos = org_repos(args.org, tok, args.repos)
    print(f"Scanning {len(repos)} repos in {args.org} ...\n")
    candidates, skipped = collect(args.org, repos, tok)

    if candidates:
        print(f"WOULD MERGE ({len(candidates)}):")
        print_table(candidates,
                    ["repo", "number", "author", "mergeable_state", "title"])
    else:
        print("WOULD MERGE (0): nothing to do")
    if skipped:
        print(f"\nSKIPPED ({len(skipped)}):")
        print_table(skipped, ["repo", "number", "author", "reason", "title"])

    if not args.merge:
        print("\nDry-run only. Re-run with --merge to merge the list above.")
        return 0
    if not candidates:
        return 0

    answer = input(f"\nMerge {len(candidates)} PRs via '{args.method}'? [y/N] ")
    if answer.strip().lower() != "y":
        print("Aborted.")
        return 0

    merged, failed = [], []
    for pr in candidates:
        status, resp = request(
            "PUT", f"{API}/repos/{args.org}/{pr['repo']}/pulls/{pr['number']}/merge",
            tok, {"merge_method": args.method})
        if status == 200 and resp.get("merged"):
            merged.append(pr)
            print(f"  merged  {pr['repo']}#{pr['number']}")
        else:
            pr["error"] = f"HTTP {status}: {resp.get('message', resp)}"
            failed.append(pr)
            print(f"  FAILED  {pr['repo']}#{pr['number']} -> {pr['error']}")

    print(f"\nDone: {len(merged)} merged, {len(failed)} failed.")
    if failed:
        print("Failures:")
        print_table(failed, ["repo", "number", "error", "title"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
