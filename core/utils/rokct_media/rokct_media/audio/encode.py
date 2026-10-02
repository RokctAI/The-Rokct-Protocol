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

"""Encode a gated 24 kHz mono PCM_16 WAV to MP3 (profile app_r3_mp3, and the
listen copies of every take). Lifted from factory voice_batch/mp3.py.

lameenc (a pip wheel of LAME, in the [voice] extra) when importable,
otherwise the ffmpeg binary. Constant bitrate, mono, 24 kHz, no tags, so
the same WAV always gives the same bytes and re-runs stay idempotent.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SAMPLE_RATE = 24_000
BITRATE_KBPS = 64


def encode(wav: str | Path, mp3: str | Path, bitrate_kbps: int = BITRATE_KBPS) -> str:
    """Write `mp3` from `wav`; returns the encoder used ('lameenc' or 'ffmpeg')."""
    wav, mp3 = Path(wav), Path(mp3)
    mp3.parent.mkdir(parents=True, exist_ok=True)
    tmp = mp3.with_name(mp3.name + ".part")
    try:
        import lameenc
        import numpy as np
        import soundfile as sf
    except ImportError:
        lameenc = None
    if lameenc is not None:
        x, sr = sf.read(str(wav), dtype="int16", always_2d=True)
        if sr != SAMPLE_RATE:
            raise ValueError(f"expected {SAMPLE_RATE} Hz, got {sr}")
        pcm = np.ascontiguousarray(x.mean(axis=1).astype(np.int16) if x.shape[1] > 1 else x[:, 0])
        enc = lameenc.Encoder()
        enc.set_bit_rate(bitrate_kbps)
        enc.set_in_sample_rate(SAMPLE_RATE)
        enc.set_channels(1)
        enc.set_quality(2)
        tmp.write_bytes(bytes(enc.encode(pcm.tobytes())) + bytes(enc.flush()))
        used = "lameenc"
    else:
        ff = shutil.which("ffmpeg")
        if not ff:
            raise RuntimeError("no MP3 encoder: install lameenc or ffmpeg")
        subprocess.run([ff, "-nostdin", "-loglevel", "error", "-y", "-i", str(wav), "-map_metadata", "-1",
                        "-fflags", "+bitexact", "-flags:a", "+bitexact", "-ac", "1", "-ar", str(SAMPLE_RATE),
                        "-c:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k", "-id3v2_version", "0",
                        "-write_xing", "0", "-f", "mp3", str(tmp)], check=True)
        used = "ffmpeg"
    tmp.replace(mp3)
    return used
