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

"""StartupOS command line interface.

Runs from the canonical engine directory as well as from the fetched skill
layout. The previous `main.py` did `from core.compiler import compile_instance`
while sitting beside `compiler.py` as a flat file, with no `core` package
anywhere — it raised `ModuleNotFoundError` on every invocation and could never
have run from this directory.
"""

import argparse
import os
import sys


def _bootstrap_package():
    """Make `core.*` importable whichever layout we are running from.

    In the skill's fetched layout the modules live in a real `core/` package.
    In the protocol repo they are flat files in this directory, so we register
    this directory *as* the `core` package before importing anything.
    """
    try:
        import core.compiler  # noqa: F401

        return
    except ImportError:
        pass

    import importlib.util

    here = os.path.dirname(os.path.abspath(__file__))
    init_file = os.path.join(here, "__init__.py")
    spec = importlib.util.spec_from_file_location(
        "core", init_file, submodule_search_locations=[here]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["core"] = module
    spec.loader.exec_module(module)


_bootstrap_package()

import core  # noqa: E402

core.enable_utf8_console()

from core import jurisdictions  # noqa: E402
from core import paths as path_utils  # noqa: E402
from core import schemas  # noqa: E402
from core import template_engine  # noqa: E402
from core.agent_bridge import (  # noqa: E402
    auto_provision_profile,
    log_ambient_milestone,
    update_profile_answer,
)
from core.compiler import compile_instance  # noqa: E402
from core.errors import StartupOSError  # noqa: E402


def _add_common(parser):
    parser.add_argument(
        "--root",
        default=None,
        help="Workspace root override (else $STARTUPOS_ROOT, then discovery)",
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="startupos",
        description="StartupOS strategic compiler — business and life planning suites.",
    )
    subparsers = parser.add_subparsers(dest="command")

    compile_parser = subparsers.add_parser(
        "compile", help="Compile an instance's document suite"
    )
    compile_parser.add_argument(
        "--type", choices=path_utils.INSTANCE_TYPES, required=True
    )
    compile_parser.add_argument("--name", required=True, help="Instance folder name")
    compile_parser.add_argument(
        "--compliance-root",
        default=None,
        help="Directory containing per-instance compliance folders",
    )
    compile_parser.add_argument(
        "--monorepo-root",
        default=None,
        help="Deprecated alias: <root>/Compliance is used",
    )
    compile_parser.add_argument("--quiet", action="store_true")
    _add_common(compile_parser)

    provision_parser = subparsers.add_parser("provision", help="Create a new profile")
    provision_parser.add_argument(
        "--type", choices=path_utils.INSTANCE_TYPES, required=True
    )
    provision_parser.add_argument("--name", required=True)
    provision_parser.add_argument(
        "--base", default=None, help="Primary geographic base"
    )
    provision_parser.add_argument(
        "--jurisdiction",
        default=None,
        help=f"ISO country code: {', '.join(jurisdictions.all_codes())}",
    )
    provision_parser.add_argument(
        "--relationships", default=None, help="Life profiles only"
    )
    _add_common(provision_parser)

    milestone_parser = subparsers.add_parser("milestone", help="Log a milestone")
    milestone_parser.add_argument(
        "--type", choices=path_utils.INSTANCE_TYPES, default="life"
    )
    milestone_parser.add_argument("--name", required=True)
    milestone_parser.add_argument("--category", required=True)
    milestone_parser.add_argument("--entry", required=True)
    milestone_parser.add_argument(
        "--date", default=None, help="YYYY-MM-DD (default: today)"
    )
    _add_common(milestone_parser)

    answer_parser = subparsers.add_parser("answer", help="Update one answer")
    answer_parser.add_argument(
        "--type", choices=path_utils.INSTANCE_TYPES, required=True
    )
    answer_parser.add_argument("--name", required=True)
    answer_parser.add_argument("--question", required=True, help="Question label")
    answer_parser.add_argument("--value", required=True)
    _add_common(answer_parser)

    check_parser = subparsers.add_parser(
        "check", help="Compliance gate for CI: exit 0 ok, 1 pending, 2 expired"
    )
    check_parser.add_argument(
        "--type", choices=path_utils.INSTANCE_TYPES, default="business"
    )
    check_parser.add_argument("--name", required=True)
    check_parser.add_argument("--compliance-root", default=None)
    _add_common(check_parser)

    lint_parser = subparsers.add_parser(
        "lint", help="Report drift between question schemas and templates"
    )
    lint_parser.add_argument("--type", choices=path_utils.INSTANCE_TYPES, default=None)
    _add_common(lint_parser)

    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Add a Jurisdiction question to profiles created before it existed",
    )
    migrate_parser.add_argument(
        "--type", choices=path_utils.INSTANCE_TYPES, default=None
    )
    migrate_parser.add_argument(
        "--name", default=None, help="One profile; omit to migrate every profile"
    )
    migrate_parser.add_argument(
        "--jurisdiction",
        required=True,
        help=f"ISO code: {', '.join(jurisdictions.all_codes())}",
    )
    migrate_parser.add_argument("--dry-run", action="store_true")
    _add_common(migrate_parser)

    expand_parser = subparsers.add_parser(
        "expand",
        help="Add the full question set to a profile created with the core set",
    )
    expand_parser.add_argument(
        "--type", choices=path_utils.INSTANCE_TYPES, required=True
    )
    expand_parser.add_argument("--name", required=True)
    _add_common(expand_parser)

    polish_parser = subparsers.add_parser(
        "polish",
        help="Opt-in AI rephrasing of compiled prose; numbers never leave "
        "the machine (requires $GROQ_API_KEY)",
    )
    polish_parser.add_argument(
        "--type", choices=path_utils.INSTANCE_TYPES, required=True
    )
    polish_parser.add_argument("--name", required=True, help="Instance folder name")
    polish_parser.add_argument("--quiet", action="store_true")
    _add_common(polish_parser)

    list_parser = subparsers.add_parser("list", help="List profiles in the workspace")
    _add_common(list_parser)

    subparsers.add_parser("jurisdictions", help="List supported jurisdictions")

    return parser


def cmd_compile(args):
    result = compile_instance(
        instance_type=args.type,
        instance_name=args.name,
        monorepo_root=args.monorepo_root,
        workspace_root=args.root,
        compliance_root=args.compliance_root,
        quiet=args.quiet,
    )
    return 0 if result.ok else 1


def cmd_provision(args):
    path = auto_provision_profile(
        instance_type=args.type,
        instance_name=args.name,
        primary_base=args.base,
        key_relationships=args.relationships,
        jurisdiction=args.jurisdiction,
        workspace_root=args.root,
    )
    print(f"[Success] Profile provisioned at: {path}")
    if not args.jurisdiction:
        print(
            "[Note] No --jurisdiction given. Regulated compliance sections stay "
            "suppressed until a '**Jurisdiction**' answer is set."
        )
    return 0


def cmd_milestone(args):
    from datetime import date as date_cls

    entry_date = None
    if args.date:
        entry_date = date_cls.fromisoformat(args.date)

    root = path_utils.resolve_workspace_root(args.root, verbose=False)
    questions_file = path_utils.questions_path(root, args.type, args.name)

    result = log_ambient_milestone(
        filepath=questions_file,
        category=args.category,
        entry_text=args.entry,
        entry_date=entry_date,
        workspace_root=args.root,
    )
    if not result.changed:
        print(f"[Skip] {result.error}")
        return 0
    print(f"[Success] Milestone logged in {questions_file}")
    if result.error:
        print(f"[Warning] {result.error}", file=sys.stderr)
        return 1
    return 0


def cmd_answer(args):
    root = path_utils.resolve_workspace_root(args.root, verbose=False)
    questions_file = path_utils.questions_path(root, args.type, args.name)

    result = update_profile_answer(
        filepath=questions_file,
        question_label=args.question,
        new_answer=args.value,
        workspace_root=args.root,
    )
    print(f"[Success] Updated '{args.question}' in {questions_file}")
    if result.error:
        print(f"[Warning] {result.error}", file=sys.stderr)
        return 1
    return 0


def cmd_check(args):
    result = compile_instance(
        instance_type=args.type,
        instance_name=args.name,
        workspace_root=args.root,
        compliance_root=args.compliance_root,
        quiet=True,
    )
    status = result.compliance_status
    labels = {0: "OK", 1: "PENDING evidence", 2: "EXPIRED certificate"}
    print(f"[Compliance] {args.type}/{args.name}: {labels.get(status, status)}")
    for key, label in sorted(result.missing_fields.items()):
        print(f"  unanswered: {key} — {label}")
    for warning in result.warnings:
        print(f"  warn: {warning}")
    return status


def cmd_lint(args):
    root = path_utils.resolve_workspace_root(args.root, verbose=False)
    engine_supplied = {
        "trading_name",
        "instance_name",
        "company_name",
        "company_name_status",
        "entity_type_hint",
        "jurisdiction_code",
        "jurisdiction_name",
        "currency",
        "currency_symbol",
        "currency_note",
        "privacy_law",
        "standards_body",
        "registry_name",
        "tax_authority",
        "trademarks_details",
        "fin_summary",
        "fin_grid_rev",
        "fin_projection_table",
        "fin_unit_economics",
        "fin_consistency",
        "market_funnel_table",
        "market_sizing_flags",
        "competitor_table",
        "living_ledger_cv",
        "living_ledger_obituary",
        "milestone_count",
        "he_she",
        "he_she_lower",
        "his_her",
        "his_her_capital",
        "him_her",
        "himself_herself",
        "company_name",
        "reg_number",
        "reg_date",
        "registered_office",
        "postal_address",
        "tax_number",
        "tax_pin",
        "tax_pin_issue_date",
        "tax_pin_expiry_date",
        "tax_compliance_status",
        "bee_level",
        "bee_procurement_recognition",
        "bee_black_ownership",
        "bee_youth_owned",
        "bee_disabled_owned",
        "bee_rural_owned",
        "bee_cert_number",
        "bee_issue_date",
        "bee_expiry_date",
    }

    # Answers the engine consumes to build other placeholders, rather than
    # templates referencing them directly. Reporting these as "unused" would be
    # wrong — dropping them would break financials, pronouns and jurisdiction.
    engine_consumed = {
        "jurisdiction",
        "pronouns",
        "gender",
        "projected_year_1",
        "projected_year_2",
        "projected_year_3",
        "historical_turnover_2024",
        "historical_turnover_2025",
        "historical_turnover_2026_ytd",
        # Unit-economics inputs: consumed by the financial computations in
        # `compiler._add_computed_financials`, surfaced through the derived
        # `fin_*` placeholders rather than referenced by name in a template.
        "average_revenue_per_customer",
        "customer_acquisition_cost",
        "customer_churn_rate",
        "customer_count_year_1",
        "monthly_operating_costs",
        "cash_on_hand",
    }

    types_to_check = [args.type] if args.type else list(path_utils.INSTANCE_TYPES)
    exit_code = 0

    for instance_type in types_to_check:
        template_root = path_utils.templates_dir(root, instance_type)
        if not os.path.isdir(template_root):
            print(f"[lint] {instance_type}: no templates at {template_root}")
            exit_code = max(exit_code, 1)
            continue

        placeholders = set()
        template_count = 0
        block_errors = []
        for current, _subdirs, filenames in os.walk(template_root):
            for entry in sorted(filenames):
                if not entry.endswith(".md"):
                    continue
                template_count += 1
                full = os.path.join(current, entry)
                relative = os.path.relpath(full, template_root).replace(os.sep, "/")
                with open(full, "r", encoding="utf-8") as handle:
                    body = handle.read()
                placeholders |= template_engine.find_placeholders(body)
                for error in template_engine.check_blocks(body):
                    block_errors.append(f"{relative}: {error}")

        uncollected, unused = schemas.validate_schema_against_templates(
            instance_type, placeholders, engine_supplied
        )
        unused = [name for name in unused if name not in engine_consumed]

        print(
            f"[lint] {instance_type}: {template_count} templates, "
            f"{len(placeholders)} distinct placeholders"
        )
        if block_errors:
            exit_code = max(exit_code, 1)
            print("  BLOCK STRUCTURE errors (the block renders literally):")
            for error in block_errors:
                print(f"    - {error}")
        if uncollected:
            exit_code = max(exit_code, 1)
            print(
                "  MISSING from the question schema (templates ask for these, "
                "nothing collects them):"
            )
            for name in uncollected:
                print(f"    - {name}")
        if unused:
            print("  Collected but referenced by no template and no engine field:")
            for name in unused:
                print(f"    - {name}")
        if not uncollected and not unused and not block_errors:
            print("  Schema and templates agree.")

    return exit_code


def cmd_migrate(args):
    from core.agent_bridge import ensure_question

    code = args.jurisdiction.strip().upper()
    entry = jurisdictions.get(code)
    if not entry.is_known:
        print(
            f"[Error] Unknown jurisdiction {args.jurisdiction!r}. "
            f"Known codes: {', '.join(jurisdictions.all_codes())}",
            file=sys.stderr,
        )
        return 1

    root = path_utils.resolve_workspace_root(args.root, verbose=False)
    types_to_scan = [args.type] if args.type else list(path_utils.INSTANCE_TYPES)

    targets = []
    for instance_type in types_to_scan:
        directory = os.path.join(root, "instances", instance_type)
        if not os.path.isdir(directory):
            continue
        names = (
            [args.name]
            if args.name
            else sorted(
                entry_name
                for entry_name in os.listdir(directory)
                if os.path.isdir(os.path.join(directory, entry_name))
            )
        )
        for name in names:
            candidate = path_utils.questions_path(root, instance_type, name)
            if os.path.exists(candidate):
                targets.append((instance_type, name, candidate))

    if not targets:
        print("No profiles found to migrate.")
        return 1

    prompt = (
        "Which country's company law and tax regime does this apply under? "
        "Use an ISO country code."
    )
    changed = 0
    conflicts = []

    from core.parser import parse_questions_md

    for instance_type, name, path in targets:
        # Warn when the profile's own Primary Base points somewhere else.
        # Bulk-stamping ZA onto a US company is exactly the mistake this whole
        # rewrite exists to prevent, so it is worth catching at the door.
        inferred = jurisdictions.resolve(parse_questions_md(path).answers, [])
        mismatch = inferred.is_known and inferred.code != code
        if mismatch:
            conflicts.append((instance_type, name, inferred.code))

        if args.dry_run:
            note = (
                f"   <-- WARNING: Primary Base suggests {inferred.code}"
                if mismatch
                else ""
            )
            print(f"  would set Jurisdiction={code} on {instance_type}/{name}{note}")
            continue

        if mismatch and not args.name:
            print(
                f"  {instance_type}/{name}: SKIPPED — Primary Base suggests "
                f"{inferred.code}, not {code}. Migrate it explicitly with "
                f"--name {name} --jurisdiction {inferred.code}"
            )
            continue
        result = ensure_question(path, "Jurisdiction", prompt, code)
        if result.changed:
            changed += 1
            print(
                f"  {instance_type}/{name}: Jurisdiction set to {code} ({entry.name})"
            )
        else:
            print(f"  {instance_type}/{name}: {result.error}")

    if conflicts and args.dry_run:
        print("\n[Warning] These profiles look like they belong elsewhere:")
        for instance_type, name, suggested in conflicts:
            print(f"  {instance_type}/{name} -> Primary Base suggests {suggested}")
        print("  Migrate them individually with the right code.")

    if not args.dry_run:
        print(
            f"\n[Success] Migrated {changed} of {len(targets)} profiles. "
            "Recompile them to pick up the jurisdiction-specific sections."
        )
    return 0


def cmd_expand(args):
    from core.agent_bridge import expand_profile

    root = path_utils.resolve_workspace_root(args.root, verbose=False)
    target = path_utils.questions_path(root, args.type, args.name)
    result = expand_profile(target, args.type)

    if not result.changed:
        print(f"[Skip] {result.error}")
        return 0

    added = getattr(result, "added", [])
    print(f"[Success] Added {len(added)} questions to {target}")
    print(
        "          Answer them, then recompile. Unanswered ones appear under "
        "Completion Gaps rather than as claims."
    )
    return 0


def cmd_polish(args):
    # Imported lazily: a skill install with a cached pre-polish engine can
    # still run every other command; only `polish` needs the new module.
    from core import polish as polish_mod

    call_model = polish_mod.build_call_model_from_env()
    if call_model is None:
        print(
            f"[Skip] ${polish_mod.API_KEY_ENV_VAR} is not set — the polish step "
            "is a no-op and your documents are unchanged.\n"
            "       Export a Groq API key to enable it. Numbers, tables and "
            "evidence never leave this machine either way."
        )
        return 0

    report = polish_mod.polish_instance(
        instance_type=args.type,
        instance_name=args.name,
        call_model=call_model,
        workspace_root=args.root,
        quiet=args.quiet,
    )
    if args.quiet:
        print(report.summary())
    return 0


def cmd_list(args):
    root = path_utils.resolve_workspace_root(args.root, verbose=False)
    base = os.path.join(root, "instances")
    if not os.path.isdir(base):
        print(f"No instances directory at {base}")
        return 1
    for instance_type in path_utils.INSTANCE_TYPES:
        directory = os.path.join(base, instance_type)
        if not os.path.isdir(directory):
            continue
        names = sorted(
            entry
            for entry in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, entry))
        )
        print(f"{instance_type}: {', '.join(names) if names else '(none)'}")
    return 0


def cmd_jurisdictions(_args):
    print(f"{'Code':<6} {'Name':<24} {'Currency':<9} Features")
    for code in jurisdictions.all_codes():
        entry = jurisdictions.get(code)
        features = ", ".join(sorted(entry.features)) or "—"
        print(f"{entry.code:<6} {entry.name:<24} {entry.currency:<9} {features}")
    return 0


_COMMANDS = {
    "compile": cmd_compile,
    "provision": cmd_provision,
    "milestone": cmd_milestone,
    "answer": cmd_answer,
    "check": cmd_check,
    "polish": cmd_polish,
    "lint": cmd_lint,
    "migrate": cmd_migrate,
    "expand": cmd_expand,
    "list": cmd_list,
    "jurisdictions": cmd_jurisdictions,
}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    handler = _COMMANDS[args.command]
    try:
        return handler(args)
    except StartupOSError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
