#!/usr/bin/env python3
"""Quartermaster: approve or override a thread's model and effort.

Encodes Ray's standing model and effort policy so the gate is deterministic
where the policy is firm, and records every decision per task.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

MODELS = ("Fable 5.1", "Opus 5.5", "Sonnet 5.5", "Haiku 5.5")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
KINDS = ("judgment", "code", "plan", "batch", "verify", "design")
DEFAULT_MODEL = "Sonnet 5.5"
DEFAULT_EFFORT = "low"
DEFAULT_HISTORY = os.environ.get(
    "QUARTERMASTER_HISTORY", ".rokct/quartermaster-history.jsonl"
)

ALIASES = {
    "fable": "Fable 5.1",
    "fable 5.1": "Fable 5.1",
    "opus": "Opus 5.5",
    "opus 5.5": "Opus 5.5",
    "sonnet": "Sonnet 5.5",
    "sonnet 5.5": "Sonnet 5.5",
    "haiku": "Haiku 5.5",
    "haiku 5.5": "Haiku 5.5",
}


def normalise_model(name):
    return ALIASES.get((name or "").strip().lower(), name)


def decide(kind, model, effort):
    """Return (decision, model, effort, reason)."""
    model = normalise_model(model)
    effort = (effort or DEFAULT_EFFORT).strip().lower()
    reasons = []

    if effort not in EFFORTS:
        reasons.append(f"unknown effort {effort!r}; default is low")
        effort = DEFAULT_EFFORT

    if model not in MODELS:
        reasons.append(f"{model!r} is not an allowed model")
        model = DEFAULT_MODEL

    if effort in ("xhigh", "max"):
        return "hold", model, effort, "xhigh/max need Ray's word"

    if kind == "batch":
        # Mechanical work: Haiku is fine and high effort is fine.
        pass
    else:
        if model == "Haiku 5.5":
            reasons.append("Haiku 5.5 is for mechanical batch work only")
            model = DEFAULT_MODEL
            effort = DEFAULT_EFFORT
        if kind in ("judgment", "verify"):
            if model not in ("Fable 5.1", "Opus 5.5"):
                model = DEFAULT_MODEL
            if effort != "low":
                reasons.append(f"{kind} work runs at low effort")
                effort = DEFAULT_EFFORT
        elif kind == "plan":
            if model not in ("Fable 5.1", "Opus 5.5"):
                reasons.append("plans run on Fable 5.1 or Opus 5.5")
                model = "Fable 5.1"
            if effort == "high":
                reasons.append("plan threads cap at medium")
                effort = "medium"
        elif kind in ("code", "design"):
            if effort == "high" and model not in ("Opus 5.5", "Sonnet 5.5"):
                reasons.append("high effort code runs on Opus 5.5 or Sonnet 5.5")
                model = "Opus 5.5"

    decision = "override" if reasons else "approve"
    return decision, model, effort, "; ".join(reasons)


def append_history(path, entry):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_history(path, task_id=None):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if task_id is None or row.get("task_id") == task_id:
                rows.append(row)
    return rows


def build_entry(args, decision, model, effort, reason, approved_by):
    return {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "task_id": args.task_id,
        "task": args.task,
        "kind": args.kind,
        "proposed": {"model": normalise_model(args.model), "effort": args.effort},
        "decision": decision,
        "model": model,
        "effort": effort,
        "reason": reason,
        "approved_by": approved_by,
    }


def format_line(decision, model, effort, reason):
    line = f"{decision} {model} {effort}"
    return f"{line}: {reason}" if reason else line


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default=DEFAULT_HISTORY)
    sub = parser.add_subparsers(dest="command", required=True)

    def task_args(p):
        p.add_argument("--task-id", required=True)
        p.add_argument("--task", required=True, help="one-line task")
        p.add_argument("--kind", required=True, choices=KINDS)
        p.add_argument("--model", required=True)
        p.add_argument("--effort", default=DEFAULT_EFFORT)

    p_decide = sub.add_parser("decide", help="apply policy and record it")
    task_args(p_decide)
    p_decide.add_argument("--dry-run", action="store_true", help="do not record")

    p_record = sub.add_parser(
        "record", help="record a decision made outside the policy (Ray's word)"
    )
    task_args(p_record)
    p_record.add_argument("--approved-by", required=True)
    p_record.add_argument("--reason", default="")

    p_hist = sub.add_parser("history", help="show decisions for a task")
    p_hist.add_argument("task_id", nargs="?")

    args = parser.parse_args(argv)

    if args.command == "decide":
        decision, model, effort, reason = decide(args.kind, args.model, args.effort)
        if not args.dry_run:
            append_history(
                args.history,
                build_entry(args, decision, model, effort, reason, "quartermaster"),
            )
        print(format_line(decision, model, effort, reason))
        return 2 if decision == "hold" else 0

    if args.command == "record":
        model = normalise_model(args.model)
        append_history(
            args.history,
            build_entry(args, "approve", model, args.effort, args.reason, args.approved_by),
        )
        print(format_line("approve", model, args.effort, args.reason))
        return 0

    for row in read_history(args.history, args.task_id):
        print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
