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


"""Catch-up with factory voice_batch (2026-11-20): hiss and dead-air take
checks, near-miss takes, clip checks, word timings, edge-burst trimming and
the text changes. Ported from factory voice_batch/tests (test_qc_checks.py,
test_voice_batch.py); synthetic signals, no models."""

import json
import sys
import unittest
from types import SimpleNamespace

import numpy as np
import numpy.fft  # noqa: F401  (loaded before any test patches sys.modules)

from rokct_media.qc import checks as _checks
from rokct_media.qc import gate as _gate
from rokct_media.qc import meter as _meter
from rokct_media.qc.gate import pick
from rokct_media.qc.meter import Meter, hiss_db
from rokct_media.speech import stitch as _stitch
from rokct_media.text.norm import (
    norm_words,
    render_sentences,
    split_sentences,
    tts_prompt,
    word_errors,
)

# factory's qc.py, split across rokct_media's modules
qc = SimpleNamespace(
    **{
        k: getattr(m, k)
        for m in (_stitch, _meter, _gate, _checks)
        for k in dir(m)
        if not k.startswith("__")
    }
)
SR = qc.SR

try:
    import librosa  # noqa: F401
    import librosa.effects  # noqa: F401

    HAVE_LIBROSA = True
except ImportError:
    HAVE_LIBROSA = False


def tone(dur_s, amp=0.1, f=150.0, rise_s=0.02):
    t = np.arange(int(dur_s * SR)) / SR
    x = amp * np.sin(2 * np.pi * f * t)
    r = int(rise_s * SR)
    if r:
        x[:r] *= np.linspace(0, 1, r)
    return x


def good_clip():
    x = np.concatenate([np.zeros(int(0.2 * SR)), tone(2.0)])
    return x * (10 ** (qc.NORM_TARGET_DB / 20) / np.sqrt(np.mean(tone(2.0) ** 2)))


def checks(x, wpm=149.0, pace=(149.0, 15.0)):
    return qc.clip_checks(x, SR, wpm, pace)


class LeadIn(unittest.TestCase):
    def test_pads_shortfall_only(self):
        x = np.concatenate([np.zeros(int(0.05 * SR)), np.full(SR // 2, 0.1)])
        y = qc.lead_in(x)
        self.assertEqual(len(y), len(x) + int(0.15 * SR))
        self.assertAlmostEqual(qc.lead_s(y), 0.20, places=3)

    def test_no_pad_when_enough(self):
        x = np.concatenate([np.zeros(int(0.3 * SR)), tone(0.5)])
        self.assertEqual(len(qc.lead_in(x)), len(x))

    def test_fade_in_applied(self):
        x = np.ones(SR) * 0.5
        y = qc.lead_in(x)
        n0 = int(0.2 * SR)
        self.assertEqual(y[n0], 0.0)
        self.assertLess(y[n0 + 100], 0.5)
        self.assertAlmostEqual(y[n0 + int(0.01 * SR) + 5], 0.5)

    def test_silence_untouched(self):
        self.assertEqual(len(qc.lead_in(np.zeros(100))), 100)

    def test_stitch_leads_in_before_normalise(self):
        from types import SimpleNamespace as NS
        from unittest import mock

        fake = NS(
            effects=NS(split=lambda x, **kw: np.array([[0, len(x)]]))
        )  # the whole take is speech
        with mock.patch.dict(sys.modules, {"librosa": fake}):
            y, _ = qc.stitch([tone(0.5, rise_s=0), tone(0.5, rise_s=0)])
        self.assertGreaterEqual(qc.lead_s(y), 0.199)


class ClipChecks(unittest.TestCase):
    def test_good_clip_passes(self):
        gate, m = checks(good_clip())
        self.assertTrue(all(gate.values()), (gate, m))

    def test_pace_report_only(self):
        for wpm, flag in ((120, "under"), (203, "over"), (149, "ok"), (None, None)):
            gate, m = checks(good_clip(), wpm=wpm)
            self.assertNotIn("pace", gate)  # never fails or retries a clip
            self.assertTrue(all(gate.values()))
            self.assertEqual(m["pace"]["flag"], flag)
        self.assertEqual(
            qc.pace_report(125, (130, 10)),
            {"wpm": 125.0, "target_wpm": 130.0, "tolerance_wpm": 10.0, "flag": "ok"},
        )

    def test_pace_spec(self):
        self.assertEqual(qc.pace_spec(None), (149.0, 15.0))
        self.assertEqual(
            qc.pace_spec({"pace": {"wpm": 140, "tolerance_wpm": 10}}), (140.0, 10.0)
        )
        self.assertEqual(qc.pace_spec({"pace": 160}), (160.0, 15.0))

    def test_loudness(self):
        self.assertFalse(checks(good_clip() * 10 ** (2.5 / 20))[0]["loudness"])
        self.assertTrue(checks(good_clip() * 10 ** (1.5 / 20))[0]["loudness"])

    def test_measured_tutor_001_renders(self):
        """Numbers measured on tutor_001's accepted renders after lead_in +
        normalise (audio is private, so only the numbers live here)."""
        for integ, lead_ms, peak, head, rise in [
            (-18.48, 206.5, -4.14, -120.0, 35.21),
            (-18.95, 204.2, -3.8, -120.0, 29.5),
            (-19.03, 204.6, -3.12, -120.0, 47.88),
            (-19.62, 204.1, -4.04, -120.0, 26.92),
            (-18.79, 211.5, -1.18, -120.0, 21.96),
            (-19.41, 206.0, -1.01, -120.0, 44.54),
        ]:
            self.assertLessEqual(abs(integ - qc.NORM_TARGET_DB), qc.LOUDNESS_TOL_DB)
            self.assertGreaterEqual(lead_ms, qc.LEAD_MIN_S * 1000)
            self.assertLess(peak, qc.CLIP_PEAK_DBFS)
            self.assertLess(head, qc.HOT_FLOOR_DBFS)
            self.assertGreaterEqual(rise, qc.ONSET_RISE_MIN_S * 1000)

    def test_lead_in(self):
        x = good_clip()[int(0.05 * SR) :]  # 150 ms lead-in
        self.assertFalse(checks(x)[0]["lead_in"])

    def test_clipping(self):
        x = good_clip()
        x[SR : SR + 10] = 1.0
        self.assertFalse(checks(x)[0]["clipping"])
        y = good_clip()
        y[SR] = 1.0  # single full-scale sample: under the run limit
        self.assertTrue(checks(y)[0]["clipping"])

    def test_hiss_in_head(self):
        x = good_clip() + np.random.default_rng(0).normal(0, 0.003, len(good_clip()))
        gate, m = checks(x)
        self.assertGreater(m["head_rms_dbfs"], qc.HOT_FLOOR_DBFS)
        self.assertFalse(gate["onset"])

    def test_hard_onset(self):
        sq = np.concatenate([np.zeros(int(0.2 * SR)), np.full(SR, 0.1)])
        gate, m = checks(sq)
        self.assertLess(m["onset_rise_ms"], 5)
        self.assertFalse(gate["onset"])

    def test_faded_onset_at_4_96_ms_passes(self):
        """tutor_001 greetings/05 measured 4.96 ms with a silent head in every
        round: a faded onset, not a hard edge."""
        self.assertGreaterEqual(4.96, qc.ONSET_RISE_MIN_S * 1000)
        self.assertGreater(qc.ONSET_RISE_MIN_S * 1000, 1.0)


class Timings(unittest.TestCase):
    def test_shape(self):
        words = [
            {"w": " Hello", "start": 0.2, "end": 0.5},
            {"w": " there", "start": 0.55, "end": 0.8},
            {"w": " friend.", "start": 1.0, "end": 1.4},
        ]
        t = qc.timings("Hello there friend.", words, 1.6)
        self.assertEqual(set(t), {"text", "duration_s", "wpm", "words", "gaps"})
        self.assertEqual(t["words"][0], {"w": "Hello", "start": 0.2, "end": 0.5})
        self.assertEqual(
            t["gaps"], [{"start": 0.8, "end": 1.0}]
        )  # 50 ms gap dropped, 200 ms kept
        self.assertAlmostEqual(t["wpm"], 150.0)
        json.dumps(t)


class MeterWordTimestamps(unittest.TestCase):
    def test_measure_requests_word_timestamps(self):
        from types import SimpleNamespace as NS
        from unittest import mock

        seen = {}

        class ASR:
            def transcribe(self, p, **kw):
                seen.update(kw)
                return (
                    iter([NS(text=" Hi", words=[NS(word=" Hi", start=0.2, end=0.4)])]),
                    None,
                )

        m = Meter.__new__(Meter)
        m.language, m.asr, m.hi = "en", ASR(), 1e9
        m._pyin = lambda w: (np.full(10, 100.0), np.ones(10, bool))
        m._pre = lambda w: w
        m.enc = NS(embed_utterance=lambda w: np.ones(3))
        m.R = np.ones(3)
        x = good_clip()
        with mock.patch.object(
            Meter, "r16", staticmethod(lambda p: x)
        ), mock.patch.dict(sys.modules, {"soundfile": NS(read=lambda p: (x, SR))}):
            out = m.measure("x.wav", "Hi")
        self.assertTrue(seen.get("word_timestamps"))
        self.assertEqual(out["words"], [{"w": " Hi", "start": 0.2, "end": 0.4}])


class Selection(unittest.TestCase):
    def t(self, err, f0, sw, res):
        return {"err": err, "f0": f0, "swings": sw, "res": res}

    def test_hissy_take_never_counts(self):
        import numpy as np

        sr = 24000
        t = np.arange(sr) / sr
        voice = 0.3 * np.sin(2 * np.pi * 220 * t) * (1 + np.sin(2 * np.pi * 3 * t))
        noise = np.random.default_rng(0).normal(0, 0.02, sr)
        clean, hissy = hiss_db(voice, sr), hiss_db(voice + noise, sr)
        self.assertGreater(hissy - clean, 12)
        a, b = dict(self.t(0, 101, 1, 0.9), hiss=hissy), dict(
            self.t(0, 104, 2, 0.9), hiss=clean
        )
        self.assertIs(pick([a, b], ref_hiss=clean)[0], b)
        self.assertEqual(pick([a], ref_hiss=clean), (None, 0))
        self.assertIs(pick([a])[0], a)  # no reference figure: not gated

    def test_take_with_dead_air_never_counts(self):
        test_take_with_dead_air_never_counts()

    def test_sound_span(self):
        test_sound_span_measures_noise_the_asr_skips()

    def test_near_miss(self):
        test_near_miss_take_only_when_asked_and_no_exact_take()


def test_take_with_dead_air_never_counts():
    # tutor_011 greetings/06: ~6 s of generated noise before "We work
    # carefully today." The ASR heard the four words, so it passed.
    good = {
        "err": 0,
        "f0": 196.0,
        "res": 0.9,
        "swings": 0,
        "tail_db": -60.0,
        "span": 1.6,
        "n_words": 4,
    }
    noisy = dict(good, span=8.4, f0=196.5)
    assert not qc.span_ok(noisy) and qc.span_ok(good)
    assert qc.pick([noisy], 196.0, 12.0) == (None, 0)
    assert qc.pick([noisy, dict(good, f0=200.0)], 196.0, 12.0)[0]["span"] == 1.6
    # A slow real read (80 wpm) and takes measured before span existed pass.
    assert qc.span_ok(dict(good, span=1.5 + 0.75 * 4))
    assert qc.span_ok({"err": 0})


def test_sound_span_measures_noise_the_asr_skips():
    sr = 24_000
    quiet, loud = np.zeros(sr), 0.3 * np.sin(np.arange(3 * sr) / 5.0)
    assert abs(qc.sound_span_s(np.concatenate([quiet, loud, quiet]), sr) - 3.0) < 0.05


def test_near_miss_take_only_when_asked_and_no_exact_take():
    # "formulae" heard as "formality": one word off, voice and pitch fine.
    near = {
        "err": 1,
        "f0": 102.0,
        "res": 0.9,
        "swings": 0,
        "tail_db": -60.0,
        "span": 3.0,
        "n_words": 6,
    }
    assert qc.pick([near], 102.0, 8.0) == (None, 0)
    assert qc.pick([near], 102.0, 8.0, near_miss=1) == (near, 3)
    # Two words off, off pitch, or a weak voice match never count.
    assert qc.pick([dict(near, err=2)], 102.0, 8.0, near_miss=1) == (None, 0)
    assert qc.pick([dict(near, f0=130.0)], 102.0, 8.0, near_miss=1) == (None, 0)
    assert qc.pick([dict(near, res=0.7)], 102.0, 8.0, near_miss=1) == (None, 0)
    # A word-exact take wins, even off pitch (tier 2, as before).
    exact = dict(near, err=0, f0=130.0)
    assert qc.pick([near, exact], 102.0, 8.0, near_miss=1) == (exact, 2)


@unittest.skipUnless(HAVE_LIBROSA, "librosa not installed")
class EdgeBurst(unittest.TestCase):
    def test_click_before_the_speech_is_dropped(self):
        # factory f19ca14: an edge noise burst the plain -40 dB trim kept
        x = np.concatenate(
            [
                np.zeros(SR // 10),
                tone(0.05, amp=0.3),
                np.zeros(SR // 2),
                tone(1.0, amp=0.3),
            ]
        )
        s, e = qc.speech_bounds(x, SR)
        self.assertGreater(s, int(0.6 * SR))


class TextNorm(unittest.TestCase):
    def test_split(self):
        self.assertEqual(
            split_sentences("Right. Go on! Why?  Yes."),
            ["Right.", "Go on!", "Why?", "Yes."],
        )
        self.assertEqual(
            split_sentences("Class starts in 3... 2... 1... Sharing now."),
            ["Class starts in 3... 2... 1...", "Sharing now."],
        )
        self.assertEqual(
            split_sentences("Wait... Then go. It's 10... ok."),
            ["Wait...", "Then go.", "It's 10...", "ok."],
        )

    def test_render_sentences_join_short_ones(self):
        self.assertEqual(render_sentences("Yes! q, q, quack."), ["Yes! q, q, quack."])
        self.assertEqual(
            render_sentences("Let's listen together. a, a, ant. Ant starts with a!"),
            ["Let's listen together. a, a, ant.", "Ant starts with a!"],
        )
        self.assertEqual(
            render_sentences("Listen. Which picture starts with the sound? Tap it."),
            ["Listen. Which picture starts with the sound? Tap it."],
        )
        self.assertEqual(
            render_sentences("Look at the big red ball. Now find the small blue ball."),
            ["Look at the big red ball.", "Now find the small blue ball."],
        )
        self.assertEqual(render_sentences("Listen."), ["Listen."])

    def test_tts_prompt_ends_a_closing_countdown_with_a_full_stop(self):
        self.assertEqual(
            tts_prompt("Class starts in 3... 2... 1..."),
            "Class starts in 3... 2... 1. ...",
        )
        self.assertEqual(tts_prompt("Wait..."), "Wait... ...")
        self.assertEqual(
            norm_words(tts_prompt("Class starts in 3... 2... 1...")),
            norm_words("Class starts in 3... 2... 1..."),
        )
        # the pad is punctuation only: the ASR words are unchanged
        self.assertEqual(
            norm_words(tts_prompt("Two x minus 3.")), norm_words("Two x minus 3.")
        )

    def test_thousands_percent_ize_compounds(self):
        self.assertEqual(word_errors("a deposit of R1 200", "a deposit of R1200"), 0)
        self.assertEqual(word_errors("1 753 m", "1753 m"), 0)
        self.assertEqual(word_errors("12% of it", "12 percent of it"), 0)
        self.assertEqual(word_errors("organise the summary", "organize the summary"), 0)
        self.assertEqual(word_errors("use mark-up here", "use markup here"), 0)
        self.assertEqual(word_errors("two meters", "two metres"), 0)


if __name__ == "__main__":
    unittest.main()
