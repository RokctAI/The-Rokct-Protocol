# rokct-media

The Rokct media engine: one pip-installable package that takes a **job
folder** and renders it. What is in the folder decides how far the engine
takes it. This version renders **level 1, speech**: script + a registered
voice -> QC-gated voice clips (24 kHz mono PCM_16, -20 dBFS). Audio
composition (L2), video (L3) and still composition follow in later
migration steps; a folder that asks for them fails with a clear message.

The level-1 code is lifted verbatim from factory's `voice_batch` stack
(render_takes, qc, textnorm, pronunciations, mp3) and the agent's
`render_voices.Renderer`, plus PR #196's whole-take mode (`prefer_seeds`,
`keep_through`, `asset`), so a deterministic render reproduces the old
engines byte for byte.

## Install

```bash
pip install core/utils/rokct_media                     # core: numpy, soundfile, jsonschema
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install "core/utils/rokct_media[voice]"            # the voice model and the QC stack
# or, pinned to a protocol commit (never main):
pip install "rokct-media[voice] @ git+https://github.com/RokctAI/The-Rokct-Protocol@<sha>#subdirectory=core/utils/rokct_media"
```

## A speech job

```text
tutor_001_ack_02/
├── script.md      the words (blank-line paragraphs become segments)
├── voice.txt      one registered voice id, or "role: voice_id" lines
├── job.json       optional: overrides (segments, cast, speech, output, deliver)
├── out/           written: <segment>.wav (+ .mp3), result.json
└── .work/         written: takes, measurements (safe to delete)
```

```bash
rokct-media render tutor_001_ack_02/ --voices voices.toml
rokct-media validate tutor_001_ack_02/ --voices voices.toml
rokct-media voices verify --voices voices.toml
rokct-media compare baseline_manifest.json candidate_manifest.json -o compare.json
```

Exit codes: 0 all outputs gated and written; 1 a gate failed; 2 manifest
or input error; 3 refused (a publishing sink with a voice whose
`agreement_in_place` is false, a reference whose sha256 does not match, or
an unpinned model).

## Voices are the caller's

The package contains no voice references, agreements or renders. The
caller passes a voices file (`--voices`, or `ROKCT_MEDIA_VOICES`) from its
private store:

```toml
[voice_a]
ref = "lms/team/voice_refs/voice_a_ref.wav"   # relative to ROKCT_MEDIA_VOICES_ROOT
sha256 = "<64 hex>"
f0_target_hz = 102
f0_tolerance_hz = 8
agreement_in_place = false    # set by the owner only
# confirmed_by = "owner"
# confirmed_on = 2026-10-01
aliases = ["tutor_001"]
# optional per-voice settings (factory lesson_voices.json):
# ddpm_steps = 14                 # this voice's diffusion steps (Voice A: none, so 10)
# similarity_min_lt_5s = 0.83     # similarity gate under 5 s
# similarity_min_ge_5s = 0.88     # similarity gate at 5 s or longer
# pace_wpm = 149                  # pace target, report-only
# pace_tolerance_wpm = 15
```

A reference is checked against its sha256 before the model loads. A job
that delivers to a publishing sink is refused (exit 3) unless every voice
in it has `agreement_in_place = true`; local renders never need it.

## Speech settings (job.json `speech`)

| key | default | |
|---|---|---|
| `selection` | `f0_closest` | per-sentence takes, median F0 closest to the voice's target (the tutor batches); `whole_take` gates one seed's whole segment (the Reel voices) and allows `takes`, `prefer_seeds`, `keep_through` |
| `seed_rounds` | `[[11,22,33],[44],[55]]` | |
| `cfg` | 1.3 | |
| `steps` | the voice's `ddpm_steps`, else 10 | set it in a job only to override every voice |
| `near_miss_words` | 0 | lessons use 1: on the last seed round only, a sentence with no word-exact take may use one at most this many words off (flagged `needs_listen`) |
| `model_revision` | `c00898d257e6b46004e3e2866a47534085fb685a` | a full commit sha; branch names are refused |
| `asr_model`, `language` | `small.en`, `en` | |

The gate (kept in step with factory voice_batch as of 2026-11-20): F0
inside the voice's window, similarity >= 0.88 at 5 s or longer (>= 0.83
under), word-exact ASR with respelled words and names as wildcards, a
clean tail (last 50 ms <= -34 dB of the loudest 10 ms frame), and the
clip checks (loudness within 2 dB of -20 dBFS, >= 180 ms lead-in, no
clipping, a quiet head and a faded onset). A take never counts when it
ends mid-word, carries seconds of dead air, or is hissy (5-11 kHz share
more than 12 dB above the reference's). Pace is recorded, never gated.
Sentences of three words or fewer are rendered joined to a neighbour. Pronunciations: the package's global list,
the job's `pronunciations` merged over it, and inline `{{word|respelling}}`.

## Clip finishing

Every finished clip goes through the same steps, in this order: each take
is trimmed at -40 dB keeping 40 ms of its own silence at each end
(`PAD_S`, 12 ms fades), takes are joined with 200-240 ms gaps, then a
lead-in is added, then the clip is RMS-normalised to -20 dBFS.

The lead-in (`LEAD_S`, default 200 ms) makes sure no clip starts with
speech at sample 0. It is sized to the trailing silence clips already end
on (mostly from the prompt's `" ..."` suffix, not just the 40 ms pad),
so it is set separately from `PAD_S`. It counts the silence the clip
already has before its first sound and pads only up to the target, so an
existing lead-in is never doubled; a 10 ms fade-in (`LEAD_FADE_S`) goes on
the first sound when padding is added. Like the tail pad, it is a constant
in `rokct_media/speech/stitch.py`; `stitch(..., lead_s=0)` turns it off.

## Level 2: audio composition (`rokct_media.compose`)

An ad or spoken-spot JSON goes in, and a mixed, mastered MP3/WAV comes out. The voices come from a content-addressed line cache, so only changed lines are re-rendered. On top of the voices go a procedural music bed and sound effects, ducking under speech, loudness normalisation and a true-peak limiter. This code was moved verbatim from factory `radio_ads/adfactory` (2026-11-20), and the factory example ads render byte-identically through it.

```sh
pip install "rokct-media[voice,compose] @ git+https://github.com/RokctAI/The-Rokct-Protocol@<sha>#subdirectory=core/utils/rokct_media"
```

```python
from rokct_media.compose.pipeline import make_ad
make_ad("spot.json", "out/", voices_dir=Path("voices"), cache_dir=Path("cache/tts"))
```

The ad format is `rokct_media/compose/ad.schema.json`. The default `voices/` and `cache/`, and any relative paths in an ad, resolve against `ROKCT_MEDIA_COMPOSE_ROOT` if it is set, otherwise against the working folder.

## Tests

```bash
python -m pytest core/utils/rokct_media/tests -q
```

Model-free: gate logic, pronunciations, folder conventions, the voices
registry and refusals, compare, and the render worker with the dummy
engine. Parity with the old engines is proven in factory's media baseline
workflow (`baseline.yml`, candidate job).
