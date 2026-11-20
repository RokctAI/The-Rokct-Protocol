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

"""Level 3 groundwork: assemble one vertical (9:16) video for social.

A visual (clip or still) is cover-scaled and centre-cropped to 1080x1920,
a still gently zoomed, captions burned in as timed boxed text (a hook, then
lines), and the voice loudness-normalised for phone speakers; H.264 + AAC
MP4, +faststart. This module builds the ffmpeg filter graph and command;
the caller decides the inputs and runs it.

Moved verbatim from RokctAI/agent lms/team/scripts/tiktok_render.py
(2026-11-20, one audio engine, step 7), which now imports it. Briefs,
the one-voice rule and watermark handling stay with the caller.
"""

import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# The upload master TikTok transcodes best from: full-bleed 9:16 so the
# platform has nothing to crop, H.264 High at CRF 19 (visually clean at
# this size without silly files), AAC stereo, and +faststart so the moov
# atom leads and the upload previews immediately.
WIDTH, HEIGHT = 1080, 1920
FPS = 30
CRF = 19
PRESET = "medium"
AUDIO_BITRATE = "192k"
AUDIO_RATE = 48000

# Social-delivery loudness (-16 LUFS integrated, -1.5 dBTP) - the level
# phone speakers expect. loudnorm resamples internally, so the audio chain
# pins the rate back down afterwards.
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"

# The hook must land inside ~3 seconds (README rule), so its caption owns
# the opening 3 and the on_screen_text lines split the rest evenly.
HOOK_SECONDS = 3.0

# Caption burn-in (assume muted viewing). drawtext does not wrap, so text
# is wrapped here by character count. Boxed for legibility on any footage,
# and placed clear of TikTok's own chrome: the hook high, the working at
# two-thirds - above the caption/progress zone, below nothing important.
HOOK_FONTSIZE, HOOK_WRAP, HOOK_Y = 58, 26, 0.14
TEXT_FONTSIZE, TEXT_WRAP, TEXT_Y = 52, 30, 0.66
LINE_SPACING = 14
BOX = "box=1:boxcolor=black@0.45:boxborderw=22"

# The captions carry CAPS notation (², −, √, ←, ✓, ₙ ...), so the font
# must cover it or the working turns to tofu. DejaVu Sans Bold does and
# ships nearly everywhere; extend this tuple, never point it at a font
# that cannot draw the maths.
FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/local/share/fonts/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
)

# A still is never a freeze-frame: unless --hold, it creeps from 1.0x to
# ZOOM_MAX across the whole timeline - a few percent, felt rather than
# seen. zoompan rounds its window to whole pixels, which at these tiny
# per-frame steps reads as jitter, so the still is first blown up OVERSCAN
# times the output and the zoom rides that finer grid.
ZOOM_MAX = 1.06
OVERSCAN = 2.5


def find_font():
    for cand in FONTS:
        if Path(cand).exists():
            return Path(cand)
    sys.exit(
        "No caption font found; install DejaVu Sans (fonts-dejavu-core) "
        "or add a maths-capable font path to FONTS."
    )


def wrapped(text: str, width: int):
    """drawtext does not wrap, so wrap here - only when a line needs it,
    and only ever at existing spaces, so no character (the decimal comma
    in 2,28 included) is added, dropped or reordered."""
    if len(text) <= width:
        return text
    return "\n".join(textwrap.wrap(text, width)) or text


def overlay_plan(brief: dict, duration: float):
    """(text, start, end, is_hook) for every caption: the hook owns the
    opening HOOK_SECONDS, then on_screen_text splits the remainder evenly,
    in order, the last line holding to the end."""
    plan = []
    hook_end = min(HOOK_SECONDS, duration)
    hook = str(brief.get("hook") or "").strip()
    if hook:
        plan.append((hook, 0.0, hook_end, True))
    lines = [str(t) for t in brief.get("on_screen_text") or [] if str(t).strip()]
    if lines and duration > hook_end:
        slot = (duration - hook_end) / len(lines)
        for i, line in enumerate(lines):
            plan.append((line, hook_end + i * slot, hook_end + (i + 1) * slot, False))
    return plan


def esc(value):
    """Escape a literal for use inside an ffmpeg filter option, where
    backslash, quote, colon, comma, semicolon, brackets and equals are all
    structure."""
    out = str(value)
    for ch in "\\':,;[]=":
        out = out.replace(ch, "\\" + ch)
    return out


def drawtext(textfile: Path, font: Path, is_hook: bool, start: float, end: float):
    """One caption layer. textfile + expansion=none hands ffmpeg the exact
    bytes on disk - no %-expansion, no quoting games - which is the
    guarantee that 2,28 lands on screen as 2,28. The end backs off half a
    frame so back-to-back captions never double-draw on the seam frame."""
    size, y = (HOOK_FONTSIZE, HOOK_Y) if is_hook else (TEXT_FONTSIZE, TEXT_Y)
    end = max(start, end - 0.5 / FPS)
    return (
        f"drawtext=fontfile={esc(font)}:textfile={esc(textfile)}"
        f":expansion=none:fontcolor=white:fontsize={size}"
        f":line_spacing={LINE_SPACING}:{BOX}"
        f":x=(w-text_w)/2:y=h*{y}"
        f":enable='between(t,{start:.3f},{end:.3f})'"
    )


def build_graph(kind, region, hold, duration, captions, silent=False):
    """The whole filter graph. Video: the watermark strip cropped away
    first (stills only), cover-scale and centre-crop to 1080x1920,
    conform to 30fps - zoompan doing both crop and creep for a zooming
    still - then the caption layers. Audio: the voice loudness-normalised
    and silence-padded; the output -t cuts both to the timeline. The
    visual's own soundtrack, if it has one, is never mapped: canonical
    voice only."""
    steps = []
    if region:
        steps.append(f"crop={region[2]}:{region[3]}:0:0")
    if kind == "still" and not hold:
        big_w, big_h = round(WIDTH * OVERSCAN), round(HEIGHT * OVERSCAN)
        rate = (ZOOM_MAX - 1.0) / max(duration * FPS, 1.0)
        steps += [
            f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase",
            f"crop={big_w}:{big_h}",
            "setsar=1",
            f"zoompan=z='min(zoom+{rate:.8f},{ZOOM_MAX})'"
            f":x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2'"
            f":d=1:s={WIDTH}x{HEIGHT}:fps={FPS}",
        ]
    else:
        steps += [
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase",
            f"crop={WIDTH}:{HEIGHT}",
            "setsar=1",
            f"fps={FPS}",
        ]
    steps += captions
    if silent:
        return f"[0:v]{','.join(steps)}[v]"
    return f"[0:v]{','.join(steps)}[v];[1:a]{LOUDNORM},aresample={AUDIO_RATE},apad[a]"


def render_cmd(visual: Path, kind, audio, graph, duration, out: Path):
    """audio=None renders a silent post: no audio input, no audio stream."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if kind == "motion":
        # A clip shorter than the timeline loops rather than freezing.
        cmd += ["-stream_loop", "-1", "-i", str(visual)]
    else:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-i", str(visual)]
    if audio is not None:
        cmd += ["-i", str(audio)]
    cmd += ["-filter_complex", graph, "-map", "[v]"]
    if audio is not None:
        cmd += ["-map", "[a]"]
    cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-c:v", "libx264", "-preset", PRESET, "-crf", str(CRF)]
    cmd += ["-pix_fmt", "yuv420p"]
    if audio is not None:
        cmd += ["-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ac", "2"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(out)]
    return cmd


def probe_seconds(path: Path):
    """Container duration via ffprobe, None when unknowable. This sets
    the clock: audio longer than the brief's duration_seconds extends the
    timeline (the voice is never cut), shorter audio is silence-padded to
    it."""
    if not shutil.which("ffprobe"):
        return None
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration"]
    cmd += ["-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    try:
        run = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(run.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None
