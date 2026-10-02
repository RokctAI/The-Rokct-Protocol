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

"""rokct-media command line.

    rokct-media render <job-folder> [--voices voices.toml] [--model-path DIR]
                       [--level 1] [--deliver local,return] [--profile clip_wav ...]
                       [--asr-model small.en] [--engine voice_model|dummy] [--no-cache] [--json]
    rokct-media validate <job-folder>... [--voices voices.toml]
    rokct-media voices verify [--voices voices.toml]
    rokct-media compare <baseline_manifest.json> <candidate_manifest.json>
                        [--engine NAME ...] [--expected-diffs expected_diffs.toml] [-o compare.json] [--json]

Exit codes: 0 all outputs gated and written (compare: everything passed);
1 a gate failed (compare: a difference); 2 manifest or input error;
3 refused (a voice without agreement_in_place for a publishing sink, a
reference whose sha256 does not match, or an unpinned model).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__


def _voices_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--voices",
        help="the caller's voices file (TOML or JSON); default $ROKCT_MEDIA_VOICES",
    )
    p.add_argument(
        "--voices-root",
        help="folder relative refs resolve against; default $ROKCT_MEDIA_VOICES_ROOT, "
        "else the voices file's folder",
    )


def cmd_render(a) -> int:
    from . import render

    deliver = (
        [s.strip() for s in a.deliver.split(",") if s.strip()] if a.deliver else None
    )
    speech = {"asr_model": a.asr_model, "language": a.language, "engine": a.engine}
    res = render(
        a.folder,
        level=a.level,
        deliver=deliver,
        preset=a.preset,
        profiles=a.profile or None,
        voices=a.voices,
        voices_root=a.voices_root,
        model_path=a.model_path,
        speech=speech,
        no_cache=a.no_cache,
        isolate=not a.in_process,
    )
    if a.json:
        print(json.dumps(res.to_dict(), indent=1, ensure_ascii=False))
    else:
        print(f"{res.job_id or a.folder}: {res.status} ({len(res.outputs)} output(s))")
        for m in res.refusals:
            print(f"refused: {m}", file=sys.stderr)
        for m in res.errors:
            print(f"error: {m}", file=sys.stderr)
        if res.result_path:
            print(f"result: {res.result_path}")
    return res.exit_code


def cmd_validate(a) -> int:
    from . import validate

    rc = 0
    for folder in a.folders:
        job, problems = validate(folder, voices=a.voices, voices_root=a.voices_root)
        if problems:
            rc = 2
            for p in problems:
                print(f"{folder}: error: {p}", file=sys.stderr)
        else:
            print(
                f"{folder}: ok ({job.id}, level {job.level}, {len(job.segments)} segment(s), "
                f"selection {job.speech['selection']})"
            )
    return rc


def cmd_voices(a) -> int:
    from .voices.registry import Registry, VoiceError, VoiceRefused

    try:
        reg = Registry.load(a.voices, a.voices_root)
    except VoiceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not reg.voices:
        print(
            "error: no voices file (pass --voices or set ROKCT_MEDIA_VOICES)",
            file=sys.stderr,
        )
        return 2
    rc = 0
    for v in reg.voices.values():
        try:
            v.verify()
            print(
                f"{v.id}: ok (sha256 verified, F0 {v.f0_target_hz:g} +/- {v.f0_tolerance_hz:g} Hz, "
                f"agreement_in_place {str(v.agreement_in_place).lower()})"
            )
        except VoiceRefused as exc:
            print(f"{v.id}: refused: {exc}")
            rc = max(rc, 3)
        except VoiceError as exc:
            print(f"{v.id}: error: {exc}")
            rc = max(rc, 2) if rc != 3 else rc
    return rc


def cmd_compare(a) -> int:
    from .compare import (
        CompareError,
        compare,
        load_expected,
        load_manifest,
        render_text,
    )

    try:
        report = compare(
            load_manifest(a.baseline),
            load_manifest(a.candidate),
            a.engine or None,
            load_expected(a.expected_diffs),
        )
    except CompareError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.output:
        Path(a.output).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1) if a.json else render_text(report))
    return 0 if report["status"] == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rokct-media", description="Rokct media engine")
    ap.add_argument("--version", action="version", version=f"rokct-media {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="render a job folder")
    r.add_argument("folder")
    _voices_args(r)
    r.add_argument("--model-path", help="local snapshot of the pinned model revision")
    r.add_argument("--level", type=int, choices=[1, 2, 3])
    r.add_argument(
        "--deliver", help="comma-separated sinks (replaces job.json deliver)"
    )
    r.add_argument("--preset")
    r.add_argument("--profile", action="append")
    r.add_argument("--asr-model")
    r.add_argument("--language")
    r.add_argument(
        "--engine", help="speech engine (default voice_model; dummy for tests)"
    )
    r.add_argument(
        "--no-cache", action="store_true", help="do not read or write the take cache"
    )
    r.add_argument("--in-process", action="store_true", help=argparse.SUPPRESS)
    r.add_argument("--json", action="store_true", help="print the Result as JSON")
    r.set_defaults(func=cmd_render)

    v = sub.add_parser("validate", help="check job folders without rendering")
    v.add_argument("folders", nargs="+")
    _voices_args(v)
    v.set_defaults(func=cmd_validate)

    vo = sub.add_parser("voices", help="voices registry")
    vo.add_argument("action", choices=["verify"])
    _voices_args(vo)
    vo.set_defaults(func=cmd_voices)

    c = sub.add_parser("compare", help="compare a candidate manifest with the baseline")
    c.add_argument("baseline")
    c.add_argument("candidate")
    c.add_argument(
        "--engine", action="append", help="compare only this engine (repeatable)"
    )
    c.add_argument(
        "--expected-diffs",
        help="expected_diffs.toml: differences allowed, with reasons",
    )
    c.add_argument("-o", "--output", help="write the report as JSON here")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=cmd_compare)

    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
