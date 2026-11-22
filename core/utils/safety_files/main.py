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

"""Command line: `safetyfiles build|status --profile profile.json`."""

import argparse
import json
import os
import sys

from . import __version__
from .builder import ProfileError, build, status


def main(argv=None):
    parser = argparse.ArgumentParser(prog="safetyfiles", description="Compile a site safety file from a JSON profile.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, text in (("build", "write binder.md, binder.pdf, gap_report.json, expiry_log.json"), ("status", "print gaps and expiries as JSON")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--profile", required=True, help="path to the profile JSON")
        p.add_argument("--today", help="ISO date to evaluate expiries against (default: today)")
        if name == "build":
            p.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)
    try:
        with open(args.profile, encoding="utf-8") as fh:
            profile = json.load(fh)
        base_dir = os.path.dirname(os.path.abspath(args.profile))
        if args.cmd == "build":
            report = build(profile, args.out, base_dir=base_dir, today=args.today)
        else:
            report = status(profile, base_dir=base_dir, today=args.today)
    except (OSError, json.JSONDecodeError, ProfileError) as exc:
        print("safetyfiles: %s" % exc, file=sys.stderr)
        return 2
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
