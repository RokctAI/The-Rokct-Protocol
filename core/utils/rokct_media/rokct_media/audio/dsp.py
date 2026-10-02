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

"""Clip loudness and the WAV writer of the clip_wav profile.

Lifted verbatim from the agent's lms/team/scripts/render_voices.py
(normalise, write_wav), which voice_batch rendered and stitched with:
24 kHz mono PCM_16, RMS-normalised to -20 dBFS with a peak guard at 0.99.
"""
from __future__ import annotations

import os
from pathlib import Path

SAMPLE_RATE = 24_000
SUBTYPE = "PCM_16"

# Target loudness. -20 dBFS RMS is the usual spoken-word broadcast level and
# leaves 20 dB of headroom for the occasional plosive. PEAK_CEILING stops the
# normalisation gain from clipping a line that has one loud transient in it.
TARGET_DBFS = -20.0
PEAK_CEILING = 0.99


def normalise(audio, target_dbfs: float = TARGET_DBFS):
    """Scale to target RMS dBFS, backing off if that would clip.

    Returned audio is float32 in [-1, 1]. Digital silence is passed through
    untouched: there is no gain that makes silence louder, and the naive
    formula would divide by zero.
    """
    import numpy as np

    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    if rms <= 0.0:
        return audio

    gain = (10.0 ** (target_dbfs / 20.0)) / rms
    peak = float(np.max(np.abs(audio)))
    if peak * gain > PEAK_CEILING:
        gain = PEAK_CEILING / peak
    return (audio * gain).astype(np.float32)


def write_wav(path: Path, audio) -> float:
    """Write 24 kHz mono PCM_16 and return the duration in seconds."""
    import numpy as np
    import soundfile as sf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    # Write to a sibling temp file and rename, so an interrupted run can
    # never leave a half-written WAV that a later step would then trust.
    tmp = path.with_suffix(path.suffix + ".part")
    # format= is explicit because the temp name ends '.part', and soundfile
    # otherwise infers the container from the extension and refuses.
    sf.write(str(tmp), audio, SAMPLE_RATE, format="WAV", subtype=SUBTYPE)
    os.replace(tmp, path)
    return audio.size / float(SAMPLE_RATE)


def rms_dbfs(x) -> float:
    import numpy as np
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    return round(float(20 * np.log10(np.sqrt(np.mean(x ** 2)))), 2)
