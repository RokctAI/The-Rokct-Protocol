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
"""
from __future__ import annotations

SR = 24_000
GAPS_S = (0.22, 0.20, 0.24, 0.22)   # + 2 x 40 ms padding = 300/280/320/300 ms pauses
PAD_S, FADE_S = 0.04, 0.012


def stitch(arrays: list, sr: int = SR):
    import librosa
    import numpy as np
    fade, pad = int(FADE_S * sr), int(PAD_S * sr)
    out, pauses = [], []
    for j, x in enumerate(arrays):
        x = np.asarray(x, dtype=np.float64)
        _, (s, e) = librosa.effects.trim(x, top_db=40, frame_length=512, hop_length=128)
        x = x[max(0, s - pad):min(len(x), e + pad)].copy()
        ramp = np.linspace(0, 1, fade) ** 2
        x[:fade] *= ramp
        x[-fade:] *= ramp[::-1]
        out.append(x)
        if j < len(arrays) - 1:
            g = GAPS_S[j % len(GAPS_S)]
            out.append(np.zeros(int(round(g * sr))))
            pauses.append(int(round((g + 2 * PAD_S) * 1000)))
    return np.concatenate(out), pauses
