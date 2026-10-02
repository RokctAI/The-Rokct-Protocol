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

"""rokct-media: a job folder in, gated media out.

    from rokct_media import render, validate, Result
    res = render("jobs/tutor_001_ack_02", voices="voices.toml")

This version renders level 1 (speech): script + a registered voice ->
QC-gated 24 kHz mono clips at -20 dBFS, lifted verbatim from factory's
voice_batch stack so a deterministic render reproduces it byte for byte.
Levels 2 and 3 and still composition follow in later steps.
"""
from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__", "render", "validate", "Result"]


def __getattr__(name):
    if name == "Result":
        from .result import Result
        return Result
    raise AttributeError(name)


def validate(folder, *, voices=None, voices_root=None, level=None, preset=None, profiles=None, deliver=None):
    """Load and check a job without rendering. Returns (job, problems):
    problems is a list of strings, empty when the job would render."""
    from .manifest.load import JobError, load_job
    from .voices.registry import Registry, VoiceError
    try:
        job = load_job(folder, level=level, preset=preset, profiles=profiles, deliver=deliver)
    except JobError as exc:
        return None, [str(exc)]
    problems = []
    try:
        reg = Registry.load(voices, voices_root)
        for s in job.segments:
            reg.get(job.voice_of(s))
    except VoiceError as exc:
        problems.append(str(exc))
    return job, problems


def render(folder, *, level=None, deliver=None, preset=None, profiles=None, on_progress=None, isolate=True,
           voices=None, voices_root=None, model_path=None, speech=None, no_cache=False):
    """Render a job folder; returns a Result (also written to out/result.json).

    voices      the caller's voices file (default: $ROKCT_MEDIA_VOICES)
    model_path  a local snapshot of the pinned model revision (default: the
                hub cache, or $ROKCT_MEDIA_MODEL_PATH)
    speech      overrides for job.json "speech" (e.g. {"asr_model": ...})
    isolate     run the voice model and the QC models in child processes
    """
    from pathlib import Path

    from .levels import l1_speech
    from .manifest.load import JobError, load_job
    from .result import Result
    from .voices.registry import Registry, VoiceError
    try:
        job = load_job(folder, level=level, preset=preset, profiles=profiles, deliver=deliver, speech=speech)
    except JobError as exc:
        res = Result(status="invalid", errors=[str(exc)])
        if Path(folder).is_dir():
            res.write(Path(folder) / "out" / "result.json")
        return res
    try:
        reg = Registry.load(voices, voices_root)
    except VoiceError as exc:
        res = Result(status="invalid", job_id=job.id, errors=[str(exc)])
        res.write(job.out_dir / "result.json")
        return res
    return l1_speech.run(job, reg, model_path=model_path, isolate=isolate, on_progress=on_progress,
                         no_cache=no_cache)
