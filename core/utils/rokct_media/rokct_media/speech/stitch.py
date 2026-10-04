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

"""Join a segment's sentence takes into one clip.

Lifted verbatim from factory voice_batch/qc.py (stitch): trim each take at
-40 dB with 40 ms padding, 12 ms fades, then 200-240 ms of silence between
takes (280-320 ms pauses once the pads are counted).

The finished clip then gets a lead-in (`lead_in`): silence at the front up
to LEAD_S (200 ms, in line with the trailing silence finished clips end
on, which comes mostly from the prompt's " ..." suffix), with a 10 ms fade-in on the
first sound, so no clip starts with speech at sample 0. It runs after the
trim and before loudness normalisation.
"""

from __future__ import annotations

SR = 24_000
GAPS_S = (0.22, 0.20, 0.24, 0.22)  # + 2 x 40 ms padding = 300/280/320/300 ms pauses
PAD_S, FADE_S = 0.04, 0.012
# Lead-in: silence at the front of every finished clip. Not PAD_S: the
# tail listeners hear is the " ..." suffix's silence plus the pad (measured
# median ~130 ms below -40 dB of peak on local renders), so the lead-in is
# that, clamped to the 200-350 ms band that stops a clip sounding cut off.
# Pass lead_s= to stitch()/lead_in() to change it; 0 turns it off.
LEAD_S, LEAD_FADE_S = 0.20, 0.010
# Below this (relative to the clip's peak) a sample counts as silence when
# measuring the lead-in a clip already has; matches the stitch trim.
LEAD_TOP_DB = 40.0


def lead_in(x, sr: int = SR, lead_s: float = LEAD_S, fade_s: float = LEAD_FADE_S):
    """`x` with silence at the front up to `lead_s`, never doubled: the
    silence it already has (samples under -LEAD_TOP_DB of the peak before
    the first sound) counts, and only the shortfall is added. A 10 ms
    fade-in is applied to the first sound when padding is added."""
    import numpy as np

    x = np.asarray(x, dtype=np.float64).reshape(-1)
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    want = int(round(lead_s * sr))
    if peak <= 0.0 or want <= 0:
        return x
    loud = np.nonzero(np.abs(x) > peak * 10 ** (-LEAD_TOP_DB / 20))[0]
    have = int(loud[0]) if loud.size else len(x)
    if have >= want:
        return x
    y = x.copy()
    fade = min(int(round(fade_s * sr)), len(y) - have)
    if fade > 0:
        y[have : have + fade] *= np.linspace(0, 1, fade)
    return np.concatenate([np.zeros(want - have), y])


def stitch(arrays: list, sr: int = SR, lead_s: float = LEAD_S):
    import librosa
    import numpy as np

    fade, pad = int(FADE_S * sr), int(PAD_S * sr)
    out, pauses = [], []
    for j, x in enumerate(arrays):
        x = np.asarray(x, dtype=np.float64)
        _, (s, e) = librosa.effects.trim(x, top_db=40, frame_length=512, hop_length=128)
        x = x[max(0, s - pad) : min(len(x), e + pad)].copy()
        ramp = np.linspace(0, 1, fade) ** 2
        x[:fade] *= ramp
        x[-fade:] *= ramp[::-1]
        out.append(x)
        if j < len(arrays) - 1:
            g = GAPS_S[j % len(GAPS_S)]
            out.append(np.zeros(int(round(g * sr))))
            pauses.append(int(round((g + 2 * PAD_S) * 1000)))
    return lead_in(np.concatenate(out), sr, lead_s), pauses
