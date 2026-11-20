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

"""Procedural music beds and sound effects. No samples, no licences.

Everything is synthesised with numpy: additive pads and plucks, a sine bass,
and simple drums (pitch-swept sine kick, filtered-noise hats and claps).
The results are modest, but they are clean, royalty-free by construction
and good enough to sit under a voice.

    generate_bed("upbeat", seconds=32, sr=44100, seed=1) -> (n, 2) float32
"""
from __future__ import annotations

import numpy as np

A4 = 440.0
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
        "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def midi(name: str, octave: int) -> int:
    return 12 * (octave + 1) + NOTE[name]


def hz(m: float) -> float:
    return A4 * 2 ** ((m - 69) / 12)


# Chords as semitone offsets from the key root (scale degrees in a major key).
DEGREES = {
    "I": [0, 4, 7], "ii": [2, 5, 9], "iii": [4, 7, 11], "IV": [5, 9, 12],
    "V": [7, 11, 14], "vi": [9, 12, 16],
    "Imaj7": [0, 4, 7, 11], "vi7": [9, 12, 16, 19], "IVmaj7": [5, 9, 12, 16],
    "Vsus": [7, 12, 14], "iii7": [4, 7, 11, 14],
}

STYLES = {
    "upbeat": dict(bpm=112, key=("D", 3), prog=["I", "V", "vi", "IV"], beats_per_chord=4,
                   pad=0.30, pluck=0.28, pluck_div=2, arp=True, bass=0.45, bass_pattern="eighths",
                   kick="four", hat=0.16, clap=0.22, shaker=0.0, brightness=0.9),
    "calm": dict(bpm=72, key=("F", 3), prog=["Imaj7", "vi7", "IVmaj7", "Vsus"], beats_per_chord=4,
                 pad=0.55, pluck=0.20, pluck_div=1, arp=True, bass=0.30, bass_pattern="whole",
                 kick=None, hat=0.0, clap=0.0, shaker=0.0, brightness=0.45),
    "corporate": dict(bpm=100, key=("C", 3), prog=["I", "vi", "IV", "V"], beats_per_chord=4,
                      pad=0.35, pluck=0.32, pluck_div=2, arp=False, bass=0.38, bass_pattern="quarters",
                      kick="half", hat=0.0, clap=0.10, shaker=0.08, brightness=0.7),
}


def _adsr(n: int, sr: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    env = np.full(n, s, dtype=np.float32)
    na, nd, nr = int(a * sr), int(d * sr), int(r * sr)
    na = min(na, n)
    env[:na] = np.linspace(0, 1, na, endpoint=False)
    nd = min(nd, n - na)
    env[na:na + nd] = np.linspace(1, s, nd, endpoint=False)
    nr = min(nr, n)
    if nr:
        env[n - nr:] *= np.linspace(1, 0, nr)
    return env


def _pad_note(f: float, n: int, sr: int, brightness: float, rng) -> np.ndarray:
    t = np.arange(n) / sr
    out = np.zeros(n, dtype=np.float64)
    for detune in (-0.07, 0.0, 0.06):            # three slightly detuned voices
        ff = f * 2 ** (detune / 12)
        phase = rng.uniform(0, 2 * np.pi)
        for h in range(1, 7):
            amp = (1.0 / h) * (brightness ** (h - 1))
            out += amp * np.sin(2 * np.pi * ff * h * t + phase * h)
    lfo = 1 + 0.08 * np.sin(2 * np.pi * 0.23 * t + rng.uniform(0, 6))
    return (out * lfo / 6.0).astype(np.float32)


def _pluck(f: float, n: int, sr: int, brightness: float) -> np.ndarray:
    """Piano/marimba-ish additive pluck: upper partials decay faster."""
    t = np.arange(n) / sr
    out = np.zeros(n, dtype=np.float64)
    for h, amp in zip(range(1, 8), (1.0, 0.55, 0.3, 0.2, 0.12, 0.08, 0.05)):
        decay = 2.5 + 3.0 * h
        out += amp * (brightness ** (h - 1)) * np.exp(-decay * t) * np.sin(2 * np.pi * f * h * t * (1 + 0.0004 * h * h))
    click = np.exp(-t * 400) * 0.1
    return (out / 2.0 + click).astype(np.float32)


def _kick(sr: int) -> np.ndarray:
    n = int(0.35 * sr)
    t = np.arange(n) / sr
    freq = 45 + 90 * np.exp(-t * 28)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    return (np.sin(phase) * np.exp(-t * 9)).astype(np.float32)


def _noise_hit(sr: int, rng, dur: float, decay: float, hp: float) -> np.ndarray:
    n = int(dur * sr)
    noise = rng.standard_normal(n).astype(np.float32)
    # crude high-pass: subtract a moving average
    k = max(1, int(sr / hp))
    smooth = np.convolve(noise, np.ones(k) / k, mode="same")
    x = noise - smooth
    t = np.arange(n) / sr
    return (x * np.exp(-t * decay) * 0.5).astype(np.float32)


def _place(buf: np.ndarray, clip: np.ndarray, start: int, gain: float, pan: float = 0.0) -> None:
    if start >= buf.shape[0]:
        return
    end = min(buf.shape[0], start + clip.shape[0])
    seg = clip[: end - start] * gain
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[start:end, 0] += seg * left * np.sqrt(2)
    buf[start:end, 1] += seg * right * np.sqrt(2)


def _one_pole_lowpass(x: np.ndarray, sr: int, cutoff: float) -> np.ndarray:
    from scipy.signal import lfilter

    a = np.exp(-2 * np.pi * cutoff / sr)
    return lfilter([1 - a], [1, -a], x, axis=0).astype(np.float32)


def generate_bed(style: str, seconds: float, sr: int = 44100, seed: int = 1) -> np.ndarray:
    if style not in STYLES:
        raise ValueError(f"unknown bed style {style!r}; choose from {', '.join(STYLES)}")
    p = STYLES[style]
    rng = np.random.default_rng(seed)
    n_total = int(seconds * sr)
    buf = np.zeros((n_total, 2), dtype=np.float32)
    beat = 60.0 / p["bpm"]
    root = midi(*p["key"])
    # Seed varies the progression's rotation and the arp pattern.
    prog = p["prog"][seed % len(p["prog"]):] + p["prog"][: seed % len(p["prog"])] if seed % 3 == 2 else p["prog"]
    chord_len = beat * p["beats_per_chord"]
    n_chords = int(np.ceil(seconds / chord_len)) + 1

    kick = _kick(sr)
    for c in range(n_chords):
        t0 = c * chord_len
        s0 = int(t0 * sr)
        degree = prog[c % len(prog)]
        notes = [root + 12 + o for o in DEGREES[degree]]
        # --- pad -----------------------------------------------------------
        n = int((chord_len + 0.6) * sr)
        pad = np.zeros(n, dtype=np.float32)
        for m in notes:
            pad += _pad_note(hz(m), n, sr, p["brightness"], rng)
        pad *= _adsr(n, sr, 0.35, 0.4, 0.8, 0.6) / len(notes)
        _place(buf, pad, s0, p["pad"], pan=-0.15)
        _place(buf, pad, s0 + int(0.011 * sr), p["pad"] * 0.6, pan=0.35)
        # --- bass ----------------------------------------------------------
        bass_root = root - 12 + DEGREES[degree][0]
        steps = {"eighths": [(i * 0.5, 0.45) for i in range(2 * p["beats_per_chord"])],
                 "quarters": [(i, 0.9) for i in range(p["beats_per_chord"])],
                 "whole": [(0, chord_len / beat)]}[p["bass_pattern"]]
        for pos, length in steps:
            nb = int(length * beat * sr)
            tb = np.arange(nb) / sr
            f = hz(bass_root)
            tone = np.sin(2 * np.pi * f * tb) + 0.25 * np.sin(2 * np.pi * 2 * f * tb)
            tone *= _adsr(nb, sr, 0.01, 0.1, 0.7, 0.05)
            _place(buf, tone.astype(np.float32), s0 + int(pos * beat * sr), p["bass"])
        # --- plucks / arp ----------------------------------------------------
        div = p["pluck_div"]
        steps_n = p["beats_per_chord"] * div
        order = [0, 1, 2, 1] if p["arp"] else [0, 2, 1, 2]
        if seed % 2:
            order = order[::-1]
        for k in range(steps_n):
            if not p["arp"] and k % 2 == 1 and rng.random() < 0.4:
                continue
            m = notes[order[k % len(order)] % len(notes)] + 12
            npl = int(1.2 * sr)
            pl = _pluck(hz(m), npl, sr, p["brightness"])
            pan = 0.3 if k % 2 else -0.3
            _place(buf, pl, s0 + int(k * beat / div * sr), p["pluck"] * (0.8 + 0.2 * rng.random()), pan)
        # --- drums ------------------------------------------------------------
        for b in range(p["beats_per_chord"]):
            sb = s0 + int(b * beat * sr)
            if p["kick"] == "four" or (p["kick"] == "half" and b % 2 == 0):
                _place(buf, kick, sb, 0.55)
            if p["clap"] and b % 2 == 1:
                _place(buf, _noise_hit(sr, rng, 0.18, 22, 1500), sb, p["clap"], pan=0.05)
            if p["hat"]:
                _place(buf, _noise_hit(sr, rng, 0.05, 90, 7000), sb + int(0.5 * beat * sr), p["hat"], pan=0.25)
            if p["shaker"]:
                for q in range(4):
                    _place(buf, _noise_hit(sr, rng, 0.04, 120, 6000), sb + int(q * beat / 4 * sr),
                           p["shaker"] * (1.0 if q % 2 else 0.6), pan=-0.3)

    buf = _one_pole_lowpass(buf, sr, 9000 if p["brightness"] > 0.6 else 5000)
    # Gentle master: remove DC, normalize to a fixed loudness later in the mix.
    buf -= buf.mean(axis=0, keepdims=True)
    peak = np.max(np.abs(buf)) or 1.0
    return (buf / peak * 0.8).astype(np.float32)


# ---------------------------------------------------------------------------
# Built-in sound effects
# ---------------------------------------------------------------------------

def generate_sfx(name: str, sr: int = 44100, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if name == "ding":                     # shop-counter bell / till ding
        n = int(1.6 * sr)
        t = np.arange(n) / sr
        x = sum(a * np.exp(-d * t) * np.sin(2 * np.pi * f * t)
                for f, a, d in ((1318.5, 1.0, 3.0), (2637, 0.35, 5.0), (3950, 0.15, 8.0), (1975.5, 0.25, 4.0)))
        return (x / 1.8).astype(np.float32)
    if name == "hooter":                   # two-tone minibus-taxi hoot: beep-beep
        out = []
        for dur in (0.16, 0.28):
            n = int(dur * sr)
            t = np.arange(n) / sr
            tone = np.sign(np.sin(2 * np.pi * 415 * t)) * 0.5 + np.sign(np.sin(2 * np.pi * 520 * t)) * 0.5
            env = _adsr(n, sr, 0.008, 0.02, 0.9, 0.03)
            out += [tone * env * 0.5, np.zeros(int(0.09 * sr))]
        x = np.concatenate(out).astype(np.float32)
        return _one_pole_lowpass(x, sr, 3000)
    if name == "whoosh":
        n = int(0.9 * sr)
        noise = rng.standard_normal(n).astype(np.float32)
        t = np.linspace(0, 1, n)
        env = np.sin(np.pi * t) ** 2
        from scipy.signal import lfilter
        out = np.zeros(n, dtype=np.float32)
        # sweep a one-pole lowpass cutoff upward in blocks
        block = 512
        zi = np.zeros(1)
        for i in range(0, n, block):
            fc = 300 + 5000 * t[i]
            a = np.exp(-2 * np.pi * fc / sr)
            y, zi = lfilter([1 - a], [1, -a], noise[i:i + block], zi=zi)
            out[i:i + block] = y
        return (out * env * 1.5).astype(np.float32)
    raise ValueError(f"unknown built-in sfx {name!r}")
