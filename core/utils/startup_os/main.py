import argparse
import sys
import os

# Add parent directory to path to ensure standard sibling imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.compiler import compile_instance

def main():
    parser = argparse.ArgumentParser(
        description="StartupOS Strategic Compiler Pipeline (Venture-Grade Dual Engine)"
    )
    
    # Add positional or named compile commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    compile_parser = subparsers.add_parser("compile", help="Compile a strategic instance suite")
    compile_parser.add_argument(
        "--type", 
        choices=["business", "life"], 
        required=True, 
        help="Type of strategic plan to compile (business or life)"
    )
    compile_parser.add_argument(
        "--name", 
        required=True, 
        help="Name of the instance folder (e.g. SouthRiver, ROKCT, Rendani)"
    )
    compile_parser.add_argument(
        "--monorepo-root",
        default=None,
        help="Custom root path to the Monorepo (useful for local overrides or custom CI paths)"
    )

    args = parser.parse_args()

    if args.command == "compile":
        try:
            compile_instance(
                instance_type=args.type,
                instance_name=args.name,
                monorepo_root=args.monorepo_root
            )
        except Exception as e:
            print(f"[Error] Error during compilation: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(0)

if __name__ == "__main__":
    main()
