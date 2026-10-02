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

"""Seed rounds, and the render worker that turns them into takes.

The worker is lifted from factory voice_batch/render_takes.py and runs in
its own process (python -m rokct_media.speech.takes), so the voice model
is never resident beside the ASR and speaker models:

    python -m rokct_media.speech.takes --jobs jobs.json --ref REF.wav \
        --engine voice_model --engine-opts '{"model_path": "<snapshot dir>"}'

jobs.json: [{"key": "<segment>#<n>", "text": "...", "seed": 11, "out": "takes/...wav"}]
Each sentence goes to the engine as text.norm.tts_prompt (sentence + " ...")
so its last word is not clipped, and is written normalised to -20 dBFS,
24 kHz mono PCM_16. A take whose file already exists is skipped; a take
already in the render cache is copied from it. Logs ids, seeds and timings
only, never the text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

SEED_ROUNDS = ([11, 22, 33], [44], [55])


def all_seeds(rounds=SEED_ROUNDS) -> list[int]:
    return [s for r in rounds for s in r]


def seed_rounds(prefer: list[int] | None = None, rounds=SEED_ROUNDS) -> list[list[int]]:
    """The rounds with the preferred seeds first, one round each: the same
    seeds, only in a different order (factory PR #196 reel_voice.py)."""
    prefer = list(prefer or [])
    rest = [[s for s in r if s not in prefer] for r in rounds]
    return [[s] for s in prefer] + [r for r in rest if r]


def safe(key: str) -> str:
    return key.replace("/", "_").replace("#", "_s")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_root() -> Path:
    return Path(
        os.environ.get("ROKCT_MEDIA_CACHE") or Path.home() / ".cache" / "rokct-media"
    )


def cache_key(identity: dict, ref_sha256: str, prompt: str, seed: int) -> str:
    """sha256 of the engine identity, the reference, the prompt and the
    seed. Everything downstream of the take (stitch, tempo, mix, encode)
    is outside the key, so changing it never re-renders."""
    blob = json.dumps(
        {"engine": identity, "ref": ref_sha256, "prompt": prompt, "seed": int(seed)},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--engine", default="voice_model")
    ap.add_argument("--engine-opts", default="{}", help="JSON object of engine options")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    jobs = [
        j
        for j in json.loads(Path(args.jobs).read_text(encoding="utf-8"))
        if not Path(j["out"]).exists()
    ]
    print(f"{len(jobs)} take(s) to render", flush=True)
    if not jobs:
        return 0
    from ..audio.dsp import normalise, write_wav
    from ..models.base import engine_class
    from ..text.norm import tts_prompt

    engine = engine_class(args.engine)(**json.loads(args.engine_opts))
    ident = engine.identity()
    ref = Path(args.ref)
    ref_sha = sha256_file(ref)
    cache = None if args.no_cache else cache_root() / "takes"
    loaded = False
    failures = 0
    for n, j in enumerate(jobs, 1):
        seed = int(j["seed"])
        prompt = tts_prompt(j["text"])
        out = Path(j["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        hit = (
            cache / (key := cache_key(ident, ref_sha, prompt, seed))[:2] / f"{key}.wav"
            if cache
            else None
        )
        if hit is not None and hit.is_file():
            shutil.copyfile(hit, out)
            print(f"[{n}/{len(jobs)}] {j['key']} seed{seed} from cache", flush=True)
            continue
        if not loaded:
            engine.load()
            loaded = True
        t0 = time.time()
        try:
            audio = engine.render(prompt, ref, seed)
            tmp = out.with_suffix(".part.wav")
            dur = write_wav(tmp, normalise(audio))
            tmp.rename(out)
        except Exception as exc:  # noqa: BLE001 - one bad take must not stop the batch
            failures += 1
            print(
                f"[{n}/{len(jobs)}] {j['key']} seed{seed} FAILED ({type(exc).__name__})",
                flush=True,
            )
            continue
        if hit is not None:
            try:
                hit.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(out, hit)
            except OSError:
                pass  # a full or read-only cache never fails a render
        print(
            f"[{n}/{len(jobs)}] {j['key']} seed{seed} {dur:.2f}s audio, {time.time() - t0:.0f}s wall",
            flush=True,
        )
    return 0 if failures < len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
