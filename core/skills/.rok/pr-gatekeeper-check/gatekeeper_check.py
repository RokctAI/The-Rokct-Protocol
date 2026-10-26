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

"""Mechanical checks for the PR gatekeeper. A tool, not a replacement.

    python3 gatekeeper_check.py --repo /path/to/checkout --head <ref-or-sha> \
        [--base origin/main] [--body-file pr_body.md] [--name control] [--fetch] [--no-run]

Prints one line per rule: PASS, FAIL, NEEDS-READ, NEEDS-RAY, NOT RUN or INFO.
Exit 0 when nothing FAILs, 1 when something does, 2 on bad usage. It never
flips, merges or comments on a PR: the gatekeeper reads the output, reads what
the script cannot prove, and makes the call.

Rules live in checklist.json next to this file. One rule is one line there.
Standard library only.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CHECKLIST = os.path.join(HERE, "checklist.json")
DEFAULT_LOG = "/mnt/project-files/gatekeeper/runs.jsonl"

PASS, FAIL, READ, RAY, NOTRUN, INFO = "PASS", "FAIL", "NEEDS-READ", "NEEDS-RAY", "NOT RUN", "INFO"

VERSION_FILES = ("manifest.json", "pyproject.toml", "pubspec.yaml", "__init__.py", "versions.json")
ART_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov", ".psd", ".ai")
FILE_TOKEN = re.compile(r"`([A-Za-z0-9_.\-/]+\.[A-Za-z0-9]{1,5}|[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-/]+)`")
SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("api key assignment", re.compile(r"""(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*["'][A-Za-z0-9_\-/+=]{20,}["']""")),
]
NOTE_PATTERNS = re.compile(
    r"(?i)\b(next time|later on|in a later pr|follow[- ]?up|to ?do for ray|ray (should|can|will|needs? to)|left for)\b")
STACK = re.compile(r"(?i)(stacks? on|merge)\s+(?:RokctAI/\w+)?#(\d+)")


class Ctx:
    def __init__(self, repo, head, base, body, name, run_commands):
        self.repo, self.head, self.base, self.body, self.name = repo, head, base, body, name
        self.run_commands = run_commands
        self._files = None
        self._patch = None

    def git(self, *args, check=False):
        p = subprocess.run(["git", "-C", self.repo] + list(args), capture_output=True, text=True)
        if check and p.returncode:
            raise RuntimeError("git %s: %s" % (" ".join(args), p.stderr.strip()))
        return p

    @property
    def files(self):
        if self._files is None:
            out = self.git("diff", "--name-status", "-M", "%s...%s" % (self.base, self.head), check=True).stdout
            self._files = [(l.split("\t")[0][0], l.split("\t")[-1]) for l in out.splitlines() if l]
        return self._files

    @property
    def paths(self):
        return [p for _, p in self.files]

    @property
    def patch(self):
        if self._patch is None:
            self._patch = self.git("diff", "-U0", "%s...%s" % (self.base, self.head), check=True).stdout
        return self._patch

    def show(self, ref, path):
        p = self.git("show", "%s:%s" % (ref, path))
        return p.stdout if p.returncode == 0 else None


def applies(rule, ctx):
    repos = rule.get("repos")
    if repos and ctx.name not in repos:
        return False
    when = rule.get("when_touches")
    if when and not any(fnmatch.fnmatch(p, g) for p in ctx.paths for g in when):
        return False
    return True


# ---- checks: each returns (status, detail) -------------------------------

def check_merge(ctx, rule):
    p = ctx.git("merge-tree", "--write-tree", ctx.base, ctx.head)
    conflicts = [l for l in p.stdout.splitlines() if l.startswith("CONFLICT")]
    if p.returncode == 0 and not conflicts:
        return PASS, "merge-tree exit 0, no CONFLICT lines against %s" % ctx.base
    if p.returncode == 0:
        return FAIL, "exit 0 but CONFLICT lines: %s" % "; ".join(conflicts)
    names = re.findall(r"CONFLICT \([^)]*\): (?:Merge conflict in )?(.+)", p.stdout)
    return FAIL, "merge-tree exit %d, %d conflict(s): %s" % (p.returncode, len(conflicts), ", ".join(names or conflicts) or p.stderr.strip())


def check_bullet_files(ctx, rule):
    if not ctx.body:
        return NOTRUN, "NOT RUN: no PR body given (--body-file), so bullets were not checked"
    named = []
    for m in FILE_TOKEN.finditer(ctx.body):
        t = m.group(1)
        if "/" not in t and not re.search(r"\.(py|json|md|yaml|yml|toml|dart|js|ts|tsx|html|css|sh|kt|txt|png|svg)$", t):
            continue
        if t not in named:
            named.append(t)
    if not named:
        return INFO, "PR body names no files in backticks"
    missing = [t for t in named if not any(p == t or p.endswith("/" + t) or p.startswith(t.rstrip("/") + "/") for p in ctx.paths)]
    if not missing:
        return PASS, "all %d named files are in the diff" % len(named)
    return READ, "named in the body but not in the diff (maybe 'unchanged', maybe a lie): %s" % ", ".join(missing)


def version_in(text, path):
    if text is None:
        return None
    base = os.path.basename(path)
    if base in ("manifest.json", "versions.json"):
        try:
            data = json.loads(text)
        except ValueError:
            return None
        if isinstance(data, dict):
            v = data.get("version")
            return v if isinstance(v, str) else None
        return None
    pat = r"""^\s*__version__\s*=\s*["']([^"']+)["']""" if base == "__init__.py" else r"""^version\s*[:=]\s*["']?([0-9][^"'\s]*)"""
    m = re.search(pat, text, re.M)
    return m.group(1) if m else None


def vtuple(v):
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.+\-]", v.split("+")[0]))


def check_versions(ctx, rule):
    changed = [p for st, p in ctx.files if st != "D"]
    code = [p for p in changed if not p.lower().endswith((".md", ".txt")) and "/tests/" not in "/" + p and not os.path.basename(p).startswith("test_")]
    vfiles = [p for p in changed if os.path.basename(p) in VERSION_FILES]
    logs = [p for p in changed if os.path.basename(p).upper() == "CHANGELOG.MD"]
    problems, notes = [], []
    for p in vfiles:
        new, old = version_in(ctx.show(ctx.head, p), p), version_in(ctx.show(ctx.base, p), p)
        if new and old and vtuple(new) <= vtuple(old) and new != old:
            problems.append("%s goes down %s -> %s" % (p, old, new))
        if new and old and new == old and os.path.basename(p) != "versions.json":
            notes.append("%s edited but version stays %s" % (p, new))
    for lg in logs:
        d = os.path.dirname(lg)
        text = ctx.show(ctx.head, lg) or ""
        m = re.search(r"^##\s*\[?v?(\d+\.\d+\.\d+[^\]\s]*)", text, re.M)
        if not m:
            continue
        top = m.group(1)
        for vf in ("manifest.json", "pyproject.toml", "pubspec.yaml"):
            vp = os.path.join(d, vf) if d else vf
            v = version_in(ctx.show(ctx.head, vp), vp)
            if v and v != top:
                problems.append("%s top entry %s but %s says %s" % (lg, top, vp, v))
    if code and not vfiles and rule.get("require_bump"):
        problems.append("code changed (%d files) but no version file changed" % len(code))
    if problems:
        return FAIL, "; ".join(problems)
    if not vfiles and not logs:
        return READ if code else INFO, "no version file or CHANGELOG touched"
    return PASS, "versions consistent in %d version file(s), %d CHANGELOG(s)%s" % (len(vfiles), len(logs), (" (" + "; ".join(notes) + ")") if notes else "")


def check_command(ctx, rule):
    for tool in rule.get("requires", []):
        if not shutil.which(tool):
            return NOTRUN, rule.get("not_run_text") or "NOT RUN: %s is not installed" % tool
    if not ctx.run_commands:
        return NOTRUN, "NOT RUN: run skipped (--no-run)"
    wt = tempfile.mkdtemp(prefix="gk-wt-")
    try:
        if ctx.git("worktree", "add", "--detach", wt, ctx.head).returncode:
            return NOTRUN, "NOT RUN: could not make a worktree of %s" % ctx.head
        cwd = os.path.join(wt, rule.get("cwd", "."))
        env = dict(os.environ, **{k: v.replace("{WT}", wt) for k, v in rule.get("env", {}).items()})
        try:
            p = subprocess.run(rule["cmd"], shell=True, cwd=cwd, env=env, capture_output=True, text=True,
                               timeout=rule.get("timeout", 900))
        except subprocess.TimeoutExpired:
            return FAIL, "timed out: %s" % rule["cmd"]
        out = p.stdout + p.stderr
        passed = sum(int(x) for x in re.findall(r"(\d+) passed", out)) or sum(int(x) for x in re.findall(r"Ran (\d+) tests?", out))
        failed = sum(int(x) for x in re.findall(r"(\d+) failed", out)) + sum(int(x) for x in re.findall(r"FAILED \(.*?(?:failures|errors)=(\d+)", out))
        errors = sum(int(x) for x in re.findall(r"(\d+) errors?", out))
        allowed = rule.get("allow_errors", 0)
        detail = "%s: %d passed, %d failed, %d errors (allowed %d)" % (rule["cmd"], passed, failed, errors, allowed)
        claimed = [int(x) for x in re.findall(r"(\d+) passed", ctx.body or "")]
        if failed or passed == 0 or errors > allowed:
            return FAIL, detail + "; tail: " + " | ".join(out.strip().splitlines()[-3:])
        if claimed and passed not in claimed:
            return READ, detail + "; PR body claims %s passed" % sorted(set(claimed))
        return PASS, detail
    finally:
        ctx.git("worktree", "remove", "--force", wt)
        shutil.rmtree(wt, ignore_errors=True)


def check_requires_pair(ctx, rule):
    """If the diff touches A, it must also touch B (demo, tour, guide)."""
    touched = [p for p in ctx.paths if any(fnmatch.fnmatch(p, g) for g in rule["if_touches"])]
    if not touched:
        return INFO, "does not touch %s" % ", ".join(rule["if_touches"])
    present = [p for p in ctx.paths if any(fnmatch.fnmatch(p, g) for g in rule["then_touches"])]
    if present:
        return PASS, "%s touched with %s" % (rule["what"], ", ".join(present[:3]))
    return rule.get("severity", READ), "touches %d file(s) under %s but nothing under %s (%s)" % (
        len(touched), ", ".join(rule["if_touches"]), ", ".join(rule["then_touches"]), rule["what"])


def check_secrets(ctx, rule):
    hits = []
    cur = None
    for line in ctx.patch.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            for label, pat in SECRET_PATTERNS:
                if pat.search(line):
                    hits.append("%s in %s" % (label, cur))
    if hits:
        return FAIL, "possible secret(s): %s" % ", ".join(sorted(set(hits)))
    return PASS, "no secret patterns in added lines"


def check_notes(ctx, rule):
    if not ctx.body:
        return NOTRUN, "NOT RUN: no PR body given (--body-file)"
    hits = sorted(set(m.group(0).lower() for m in NOTE_PATTERNS.finditer(ctx.body)))
    if hits:
        return READ, "PR body leaves work for later or for Ray (%s); Ray acts on no PR notes, send it back or have the PR say what is unproven" % ", ".join(hits)
    return PASS, "no 'next time' or note-for-Ray wording"


def check_merge_order(ctx, rule):
    found = sorted(set(m.group(2) for m in STACK.finditer(ctx.body or "")))
    if not found:
        return INFO, "no 'stacks on #N' in the body"
    return INFO, "stacked on #%s: merge that first; the diff against main includes it until then; versions may need renumbering" % ", #".join(found)


def check_art(ctx, rule):
    art = [p for st, p in ctx.files if st != "D" and p.lower().endswith(ART_EXT)]
    if art:
        return RAY, "art/media in the diff, needs Ray's own approval attached: %s" % ", ".join(art[:6])
    return PASS, "no art or media files"


CHECKS = {
    "merge": check_merge, "bullet_files": check_bullet_files, "versions": check_versions,
    "command": check_command, "requires_pair": check_requires_pair, "secrets": check_secrets,
    "notes": check_notes, "merge_order": check_merge_order, "art": check_art,
}


def run(ctx, rules):
    results = []
    for rule in rules:
        if not applies(rule, ctx):
            continue
        fn = CHECKS.get(rule["check"])
        if fn is None:
            results.append((rule["id"], READ, "unknown check %r in checklist" % rule["check"], rule))
            continue
        try:
            status, detail = fn(ctx, rule)
        except Exception as exc:  # a broken check must never read as PASS
            status, detail = READ, "check crashed: %s" % exc
        results.append((rule["id"], status, detail, rule))
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--body-file")
    ap.add_argument("--name", help="repo name for the checklist (default: folder name)")
    ap.add_argument("--checklist", default=DEFAULT_CHECKLIST)
    ap.add_argument("--log", default=os.environ.get("GATEKEEPER_LOG", DEFAULT_LOG))
    ap.add_argument("--pr", default="", help="label for the log, e.g. control#192")
    ap.add_argument("--fetch", action="store_true", help="git fetch origin before checking")
    ap.add_argument("--no-run", action="store_true", help="skip test and compose commands")
    args = ap.parse_args(argv)

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print("no such repo: %s" % repo, file=sys.stderr)
        return 2
    if args.fetch:
        subprocess.run(["git", "-C", repo, "fetch", "-q", "origin"], check=False)
    body = open(args.body_file).read() if args.body_file else ""
    with open(args.checklist) as f:
        rules = json.load(f)["rules"]
    ctx = Ctx(repo, args.head, args.base, body, args.name or os.path.basename(repo), not args.no_run)
    try:
        sha = ctx.git("rev-parse", "--short", args.head, check=True).stdout.strip()
        ctx.git("rev-parse", "--verify", args.base, check=True)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    results = run(ctx, rules)
    width = max([len(r[0]) for r in results] or [4])
    print("gatekeeper_check %s head %s base %s (%d rules)" % (ctx.name, sha, args.base, len(results)))
    for rid, status, detail, _ in results:
        print("%-*s  %-10s  %s" % (width, rid, status, detail))
    print("-- NOT RUN lines go into the verdict and the PR in plain words.")
    print("-- The script proves mechanics only. Read: does the caller invoke it, does the test exercise the claim, is the unproven list honest.")
    bad = [r for r in results if r[1] == FAIL]
    print("RESULT: %s" % ("FAIL (%d)" % len(bad) if bad else "no FAIL; %d need reading or Ray" % sum(1 for r in results if r[1] in (READ, RAY))))

    log_dir = os.path.dirname(args.log)
    if log_dir and os.path.isdir(log_dir):
        try:
            with open(args.log, "a") as f:
                f.write(json.dumps({"t": int(time.time()), "pr": args.pr, "repo": ctx.name, "head": sha,
                                    "results": {r[0]: r[1] for r in results}}) + "\n")
        except OSError:
            pass
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
