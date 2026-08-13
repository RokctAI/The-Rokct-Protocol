# compliance-silent
"""StartupOS provisioning wrapper — create a new business or life profile."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bootstrap  # noqa: E402


def build_parser():
    parser = argparse.ArgumentParser(description="StartupOS profile provisioner")
    parser.add_argument("--type", choices=("business", "life"), required=True)
    parser.add_argument(
        "--name",
        required=True,
        help="Instance name: letters, digits, dot, dash, underscore",
    )
    parser.add_argument("--base", default=None, help="Primary geographic base")
    parser.add_argument(
        "--jurisdiction",
        default=None,
        help="ISO country code (ZA, US, GB, DE...). Without it, "
        "regulated compliance sections stay suppressed.",
    )
    parser.add_argument("--relationships", default=None, help="Life profiles only")
    parser.add_argument("--root", default=None, help="Workspace root override")
    parser.add_argument("--no-sync", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()

    _bootstrap.prepare(root=args.root, sync=not args.no_sync, verbose=not args.quiet)

    from core.agent_bridge import auto_provision_profile
    from core.errors import StartupOSError

    try:
        path = auto_provision_profile(
            instance_type=args.type,
            instance_name=args.name,
            primary_base=args.base,
            key_relationships=args.relationships,
            jurisdiction=args.jurisdiction,
            workspace_root=args.root,
        )
    except StartupOSError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1

    print(f"[Success] Profile provisioned at: {path}")
    if not args.jurisdiction:
        print(
            "[Note] No --jurisdiction supplied. Company-registry, tax and "
            "B-BBEE sections stay suppressed until a '**Jurisdiction**' "
            "answer is set in questions.md."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
