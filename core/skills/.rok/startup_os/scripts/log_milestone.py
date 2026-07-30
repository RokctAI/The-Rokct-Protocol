# compliance-silent
"""StartupOS milestone wrapper — append an achievement to the living ledger."""

import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bootstrap  # noqa: E402


def build_parser():
    parser = argparse.ArgumentParser(description="StartupOS conversational milestone log")
    parser.add_argument("--name", required=True, help="Instance name")
    parser.add_argument("--type", choices=("business", "life"), default="life")
    parser.add_argument("--category", required=True,
                        help="Milestone category, e.g. 'Technical Mastery'")
    parser.add_argument("--entry", required=True, help="What was achieved")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--allow-duplicate", action="store_true",
                        help="Log even if an equivalent entry already exists")
    parser.add_argument("--root", default=None, help="Workspace root override")
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()

    _bootstrap.prepare(root=args.root, sync=not args.no_sync, verbose=not args.quiet)

    from core.agent_bridge import log_ambient_milestone
    from core.errors import StartupOSError
    from core.paths import questions_path, resolve_workspace_root

    try:
        root = resolve_workspace_root(args.root, verbose=False)
        target = questions_path(root, args.type, args.name)
    except StartupOSError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1

    if not os.path.exists(target):
        print(f"[Error] No profile at {target}. Provision it first.", file=sys.stderr)
        return 1

    try:
        result = log_ambient_milestone(
            filepath=target,
            category=args.category,
            entry_text=args.entry,
            entry_date=date.fromisoformat(args.date) if args.date else None,
            deduplicate=not args.allow_duplicate,
            workspace_root=args.root,
        )
    except StartupOSError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1

    if not result.changed:
        print(f"[Skip] {result.error}")
        return 0

    print(f"[Success] Milestone logged in {target}")
    if result.error:
        print(f"[Warning] {result.error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
