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

"""Audio helpers: ffmpeg, resampling, trimming, stretching, ducking, loudness.

All audio inside the pipeline is float32 numpy, shape (n,) for mono or
(n, 2) for stereo, at the output sample rate (44.1 kHz by default).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------------------------

def ffmpeg_exe() -> str:
    """System ffmpeg if present, else the static build from imageio-ffmpeg."""
    env = os.environ.get("FFMPEG")
    if env:
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as exc:
        raise RuntimeError("ffmpeg not found: install ffmpeg or `pip install imageio-ffmpeg`") from exc


def _run(args: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-nostdin", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {proc.stderr[-1500:]}")
    return proc


def read_audio(path: str | Path, sr: int, channels: int = 1) -> np.ndarray:
    """Decode any audio file ffmpeg understands to float32 at `sr`."""
    proc = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(path), "-f", "f32le",
         "-acodec", "pcm_f32le", "-ac", str(channels), "-ar", str(sr), "-"],
        capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"cannot decode {path}: {proc.stderr.decode(errors='replace')[-800:]}")
    audio = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    return audio.reshape(-1, channels) if channels > 1 else audio


def write_wav(path: str | Path, audio: np.ndarray, sr: int, subtype: str = "PCM_16") -> None:
    import soundfile as sf

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    sf.write(str(tmp), audio, sr, format="WAV", subtype=subtype)
    os.replace(tmp, path)


def encode_mp3(wav_path: Path, mp3_path: Path, bitrate_kbps: int, gain_db: float = 0.0) -> None:
    tmp = mp3_path.with_suffix(".part.mp3")
    af = ["-af", f"volume={gain_db:.3f}dB"] if abs(gain_db) > 1e-3 else []
    _run(["-y", "-i", str(wav_path), *af, "-codec:a", "libmp3lame", "-b:a", f"{bitrate_kbps}k",
          "-id3v2_version", "3", str(tmp)])
    os.replace(tmp, mp3_path)


def ffmpeg_ebur128(path: Path) -> dict:
    """Independent measurement with ffmpeg's EBU R128 scanner (true peak 4x)."""
    proc = _run(["-i", str(path), "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"])
    text = proc.stderr
    summary = text[text.rfind("Summary:"):]
    def grab(label):
        m = re.search(label + r":\s+(-?[\d.]+|-inf)", summary)
        return None if not m or m.group(1) == "-inf" else float(m.group(1))
    return {"integrated_lufs": grab("I"), "lra_lu": grab("LRA"), "true_peak_dbtp": grab("Peak")}


def media_duration(path: Path) -> float:
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(path),
                           "-f", "null", "-"], capture_output=True, text=True)
    times = re.findall(r"time=(\d+):(\d+):([\d.]+)", proc.stderr)
    if not times:
        return float("nan")
    h, m, s = times[-1]
    return int(h) * 3600 + int(m) * 60 + float(s)


# ---------------------------------------------------------------------------
# Basic ops
# ---------------------------------------------------------------------------

def resample(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return audio.astype(np.float32)
    from math import gcd
    from scipy.signal import resample_poly

    g = gcd(sr_in, sr_out)
    return resample_poly(audio, sr_out // g, sr_in // g, axis=0).astype(np.float32)


def db(x: float) -> float:
    return 10.0 ** (x / 20.0)


def trim_silence(audio: np.ndarray, sr: int, thresh_db: float = -42.0,
                 pad_s: float = 0.04) -> np.ndarray:
    """Cut leading/trailing silence, relative to the clip's own peak."""
    if audio.size == 0:
        return audio
    win = max(1, int(0.01 * sr))
    n = audio.size // win
    if n == 0:
        return audio
    frames = audio[: n * win].reshape(n, win)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    ref = rms.max()
    active = np.where(20 * np.log10(rms / ref + 1e-12) > thresh_db)[0]
    if active.size == 0:
        return audio
    pad = int(pad_s * sr)
    start = max(0, active[0] * win - pad)
    end = min(audio.size, (active[-1] + 1) * win + pad)
    return audio[start:end]


def fade(audio: np.ndarray, sr: int, fade_in_s: float = 0.0, fade_out_s: float = 0.0) -> np.ndarray:
    out = audio.copy()
    n = out.shape[0]
    fi = min(n, int(fade_in_s * sr))
    fo = min(n, int(fade_out_s * sr))
    shape = (-1, 1) if out.ndim == 2 else (-1,)
    if fi > 0:
        out[:fi] *= np.linspace(0, 1, fi, dtype=np.float32).reshape(shape) ** 2
    if fo > 0:
        out[n - fo:] *= np.linspace(1, 0, fo, dtype=np.float32).reshape(shape) ** 2
    return out


def loudness(audio: np.ndarray, sr: int) -> float:
    """Integrated loudness (LUFS, BS.1770-4) via pyloudnorm."""
    import pyloudnorm as pyln

    if audio.shape[0] < int(0.45 * sr):
        audio = np.concatenate([audio, np.zeros((int(0.45 * sr) - audio.shape[0],) + audio.shape[1:],
                                                dtype=np.float32)])
    return float(pyln.Meter(sr).integrated_loudness(audio))


def normalize_loudness(audio: np.ndarray, sr: int, target_lufs: float) -> np.ndarray:
    lufs = loudness(audio, sr)
    if not np.isfinite(lufs):
        return audio
    return (audio * db(target_lufs - lufs)).astype(np.float32)


def true_peak_db(audio: np.ndarray, sr: int, oversample: int = 4) -> float:
    """True peak estimate by 4x oversampling (as BS.1770 prescribes)."""
    from scipy.signal import resample_poly

    up = resample_poly(audio, oversample, 1, axis=0)
    peak = float(np.max(np.abs(up))) if up.size else 0.0
    return 20 * np.log10(peak + 1e-12)


# ---------------------------------------------------------------------------
# Time stretch (pitch preserved)
# ---------------------------------------------------------------------------

def time_stretch(audio: np.ndarray, sr: int, tempo: float) -> np.ndarray:
    """tempo > 1 = faster/shorter. Uses ffmpeg's rubberband filter (formant
    and pitch preserved), falling back to atempo if rubberband is missing."""
    if abs(tempo - 1.0) < 1e-3:
        return audio
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "in.wav", Path(td) / "out.wav"
        write_wav(src, audio, sr, subtype="FLOAT")
        try:
            _run(["-y", "-i", str(src), "-af",
                  f"rubberband=tempo={tempo:.5f}:pitchq=quality:window=short:formant=preserved",
                  str(dst)])
        except RuntimeError:
            _run(["-y", "-i", str(src), "-af", f"atempo={tempo:.5f}", str(dst)])
        out = read_audio(dst, sr, channels=1 if audio.ndim == 1 else audio.shape[1])
    return out


# ---------------------------------------------------------------------------
# Ducking, limiting, final loudness
# ---------------------------------------------------------------------------

def envelope(audio: np.ndarray, sr: int, attack_s: float = 0.03, release_s: float = 0.35,
             lookahead_s: float = 0.12, gate_db: float = -45.0) -> np.ndarray:
    """0..1 'voice is active' envelope for sidechain ducking."""
    mono = audio if audio.ndim == 1 else audio.mean(axis=1)
    hop = max(1, int(0.01 * sr))
    n = int(np.ceil(mono.size / hop))
    padded = np.zeros(n * hop, dtype=np.float32)
    padded[: mono.size] = mono
    rms = np.sqrt(np.mean(padded.reshape(n, hop) ** 2, axis=1) + 1e-12)
    level = 20 * np.log10(rms + 1e-12)
    target = np.clip((level - gate_db) / 15.0, 0, 1)          # soft knee over 15 dB
    # Hold across short gaps between words so the bed doesn't pump.
    hold = int(0.25 / 0.01)
    held = target.copy()
    for k in range(1, hold + 1):
        held[k:] = np.maximum(held[k:], target[:-k])
    target = held
    a_att = np.exp(-0.01 / attack_s)
    a_rel = np.exp(-0.01 / release_s)
    env = np.zeros_like(target)
    prev = 0.0
    for i, t in enumerate(target):
        coeff = a_att if t > prev else a_rel
        prev = coeff * prev + (1 - coeff) * t
        env[i] = prev
    shift = int(lookahead_s / 0.01)
    if shift:
        env = np.concatenate([env[shift:], np.full(shift, env[-1] if env.size else 0.0)])
    full = np.repeat(env, hop)[: mono.size]
    return full.astype(np.float32)


def limiter(audio: np.ndarray, sr: int, ceiling_db: float, release_s: float = 0.08,
            lookahead_s: float = 0.005) -> np.ndarray:
    """Look-ahead peak limiter (sample-peak, stereo linked)."""
    ceiling = db(ceiling_db)
    peak = np.abs(audio) if audio.ndim == 1 else np.max(np.abs(audio), axis=1)
    la = max(1, int(lookahead_s * sr))
    # Required gain per sample, then a moving minimum over the look-ahead.
    need = np.minimum(1.0, ceiling / np.maximum(peak, 1e-9))
    from scipy.ndimage import minimum_filter1d
    need = minimum_filter1d(need, size=2 * la + 1, mode="nearest")
    # Smooth release: gain may drop instantly, recovers exponentially.
    a = np.exp(-1.0 / (release_s * sr))
    gain = np.empty_like(need)
    g = 1.0
    for i in range(need.size):          # ~1.3M iterations for 30 s; fine offline
        x = need[i]
        g = x if x < g else a * g + (1 - a) * x
        gain[i] = g
    return (audio * (gain[:, None] if audio.ndim == 2 else gain)).astype(np.float32)


def master(audio: np.ndarray, sr: int, target_lufs: float, tp_ceiling_db: float) -> tuple[np.ndarray, dict]:
    """Normalize to target integrated loudness with a true-peak ceiling.

    Gain to target, limit, re-measure, repeat. Converges in 2-3 passes for
    speech-over-music at broadcast levels.
    """
    out = audio.astype(np.float32)
    info = {}
    margin = 0.3
    for _ in range(4):
        out = normalize_loudness(out, sr, target_lufs)
        tp = true_peak_db(out, sr)
        if tp <= tp_ceiling_db:
            break
        out = limiter(out, sr, tp_ceiling_db - margin)
        margin += 0.3
    out = normalize_loudness(out, sr, target_lufs)
    tp = true_peak_db(out, sr)
    if tp > tp_ceiling_db:
        # Last resort: trade loudness for peak compliance.
        out = (out * db(tp_ceiling_db - tp - 0.05)).astype(np.float32)
        info["loudness_backed_off_db"] = round(tp - tp_ceiling_db + 0.05, 2)
    info["integrated_lufs"] = round(loudness(out, sr), 2)
    info["true_peak_dbtp"] = round(true_peak_db(out, sr), 2)
    return out, info
