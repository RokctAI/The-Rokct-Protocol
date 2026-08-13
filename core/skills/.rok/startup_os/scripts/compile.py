# compliance-silent
"""StartupOS compile wrapper.

Bootstraps the engine from the protocol repo, installs templates, and compiles
one instance's document suite.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bootstrap  # noqa: E402


def build_parser():
    parser = argparse.ArgumentParser(description="StartupOS strategic compiler")
    parser.add_argument("--type", choices=("business", "life"), required=True)
    parser.add_argument("--name", required=True, help="Instance folder name")
    parser.add_argument("--root", default=None, help="Workspace root override")
    parser.add_argument(
        "--compliance-root",
        default=None,
        help="Directory holding per-instance compliance folders",
    )
    parser.add_argument(
        "--monorepo-root",
        default=None,
        help="Deprecated alias; <root>/Compliance is used",
    )
    parser.add_argument(
        "--no-sync", action="store_true", help="Skip template installation"
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()

    _bootstrap.prepare(root=args.root, sync=not args.no_sync, verbose=not args.quiet)

    from core.compiler import compile_instance
    from core.errors import StartupOSError

    try:
        result = compile_instance(
            instance_type=args.type,
            instance_name=args.name,
            monorepo_root=args.monorepo_root,
            workspace_root=args.root,
            compliance_root=args.compliance_root,
            quiet=args.quiet,
        )
    except StartupOSError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
