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

"""Job folder conventions, job.json and the voices registry. Model-free."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from rokct_media import render, validate
from rokct_media.manifest import names
from rokct_media.manifest.load import JobError, load_job
from rokct_media.voices.registry import Registry, VoiceError, VoiceRefused


def write(d: Path, name: str, text: str) -> Path:
    p = d / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


class Conventions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name) / "tutor_001_ack_02"
        self.d.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_zero_json_speech_job(self):
        write(self.d, "Script.md", "---\nid: x\n---\n# Heading\n<!-- note -->\nSay **this** now. Then `that`.\n")
        write(self.d, "voice.txt", "voice_a\n")
        job = load_job(self.d)
        self.assertEqual((job.id, job.level, job.preset), ("tutor_001_ack_02", 1, None))
        self.assertEqual(job.cast, {"default": {"voice": "voice_a"}})
        self.assertEqual(job.segments, [{"id": "s01", "role": "default", "text": "Say this now. Then that."}])
        self.assertEqual(job.speech["selection"], "f0_closest")
        self.assertEqual((job.speech["cfg"], job.speech["steps"]), (1.3, 10))
        self.assertEqual(job.speech["model_revision"], "c00898d257e6b46004e3e2866a47534085fb685a")
        self.assertEqual(job.output, {"profiles": ["clip_wav"], "formats": ["wav"]})
        self.assertEqual(job.deliver, [{"sink": "local"}])

    def test_paragraphs_and_roles(self):
        write(self.d, "script.txt", "host: Maths homework at nine?\nThere's a tutor.\n\nSign up.\n\n"
                                    "tag: Terms apply.\n\nnote: not a role.\n")
        write(self.d, "voice.txt", "host: voice_b\ntag: voice_a\n")
        segs = load_job(self.d).segments
        self.assertEqual([(s["id"], s["role"]) for s in segs],
                         [("s01", "host"), ("s02", "host"), ("s03", "tag"), ("s04", "tag")])
        self.assertEqual(segs[0]["text"], "Maths homework at nine? There's a tutor.")
        self.assertEqual(segs[3]["text"], "note: not a role.")

    def test_subtopic_headings(self):
        write(self.d, "script.md", "# Lesson\n\n## Subtopic: Receipts\nFirst para.\n\nSecond para.\n\n"
                                   "## Subtopic: Totals\nAdd them up.\n")
        write(self.d, "voice.txt", "tutor_001")
        segs = load_job(self.d).segments
        self.assertEqual([(s["id"], s["subtopic"], s["text"]) for s in segs],
                         [("subtopic_1", "subtopic_1", "First para. Second para."),
                          ("subtopic_2", "subtopic_2", "Add them up.")])

    def test_never_guesses_a_voice(self):
        write(self.d, "script.txt", "Hello there.")
        with self.assertRaisesRegex(JobError, "no voice"):
            load_job(self.d)

    def test_nothing_to_say(self):
        write(self.d, "voice.txt", "voice_a")
        with self.assertRaisesRegex(JobError, "nothing to say"):
            load_job(self.d)

    def test_higher_levels_are_reported(self):
        write(self.d, "script.txt", "Hello there.")
        write(self.d, "voice.txt", "voice_a")
        write(self.d, "music.mp3", "x")
        with self.assertRaisesRegex(JobError, "level 2 \\(radio_ad\\).*speech jobs \\(level 1\\) only"):
            load_job(self.d)
        job = load_job(self.d, level=1)
        self.assertEqual((job.level, job.preset), (1, "radio_ad"))
        write(self.d, "job.json", json.dumps({"level": 3}))
        with self.assertRaisesRegex(JobError, "no inputs for it"):
            load_job(self.d)

    def test_preset_inference(self):
        f = lambda *n: {k: [Path(k)] for k in n}  # noqa: E731
        self.assertIsNone(names.infer_preset(f("script", "voice")))
        self.assertEqual(names.infer_preset(f("script", "scene")), "lesson")
        self.assertEqual(names.infer_preset(f("script", "video", "music")), "reel")
        self.assertEqual(names.infer_preset(f("script", "jingle")), "radio_ad")
        self.assertEqual(names.infer_preset(f("template")), "social_post")
        self.assertEqual(names.infer_preset(f("chapter")), "audiobook")

    def test_voice_txt(self):
        self.assertEqual(names.parse_voice_txt("# c\nvoice_b\n"), {"default": "voice_b"})
        for bad in ("", "Voice A", "host: voice_b\nhost: voice_a", "host voice_b\ntag: voice_a"):
            with self.assertRaises(ValueError, msg=bad):
                names.parse_voice_txt(bad)

    def test_job_json_segments_and_whole_take(self):
        write(self.d, "job.json", json.dumps({
            "schema": "rokct-media/job@1", "id": "reel_open", "cast": {"narrator": {"voice": "voice_b"}},
            "speech": {"selection": "whole_take"},
            "segments": [{"id": "open", "role": "narrator", "text": "Looking for funding? Here it is.",
                          "asset": "voice_open.wav", "prefer_seeds": [44]}]}))
        job = load_job(self.d)
        self.assertEqual((job.id, job.speech["selection"], job.segments[0]["asset"]),
                         ("reel_open", "whole_take", "voice_open.wav"))

    def test_job_json_rejects(self):
        base = {"cast": {"host": {"voice": "voice_b"}}, "segments": [{"id": "a", "text": "Hi there."}]}
        for bad, msg in (({"speech": {"tempo": 1.2}}, "tempo"), ({"bogus": 1}, "bogus"),
                         ({"speech": {"model_revision": "main"}}, "model_revision"),
                         ({"speech": {"tempo": 1.05}}, "not in this version"),
                         ({"segments": [{"id": "a", "text": "Hi.", "prefer_seeds": [44]}]}, "whole_take"),
                         ({"segments": [{"id": "a", "text": "Hi."}, {"id": "a", "text": "Yo."}]}, "twice"),
                         ({"segments": [{"id": "a", "role": "tag", "text": "Hi."}]}, "not in the cast"),
                         ({"output": {"profiles": ["tiktok_9x16"]}}, "not in this version"),
                         ({"deliver": [{"sink": "carrier_pigeon"}]}, "unknown delivery sink")):
            write(self.d, "job.json", json.dumps({**base, **bad}))
            with self.assertRaisesRegex(JobError, msg):
                load_job(self.d)

    def test_mp3_profile(self):
        write(self.d, "job.json", json.dumps({"cast": {"r": {"voice": "voice_a"}},
                                              "segments": [{"id": "a", "text": "Hi there."}],
                                              "output": {"profiles": ["clip_wav", "app_r3_mp3"]}}))
        self.assertEqual(load_job(self.d).output["formats"], ["wav", "mp3"])


class Voices(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ref = self.root / "refs" / "voice_a_ref.wav"
        self.ref.parent.mkdir()
        self.ref.write_bytes(b"RIFF-not-really-audio")
        self.sha = hashlib.sha256(self.ref.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def toml(self, body: str) -> Path:
        return write(self.root, "voices.toml", body)

    def test_load_verify_alias(self):
        p = self.toml(f'[voice_a]\nref = "refs/voice_a_ref.wav"\nsha256 = "{self.sha}"\nf0_target_hz = 102\n'
                      'f0_tolerance_hz = 8\nagreement_in_place = true\nconfirmed_by = "owner"\n'
                      'confirmed_on = 2026-10-01\naliases = ["tutor_001"]\n\n[tutor_002]\nref = ""\n')
        reg = Registry.load(p)
        v = reg.get("tutor_001")
        self.assertEqual((v.id, v.f0_target_hz, v.agreement_in_place, v.confirmed_on), ("voice_a", 102, True,
                                                                                         "2026-10-01"))
        self.assertEqual(v.verify(), self.sha)
        self.assertNotIn("ref", v.summary())
        with self.assertRaises(VoiceRefused):
            reg.get("tutor_002").verify()
        with self.assertRaisesRegex(VoiceError, "not in the voices registry"):
            reg.get("voice_c")

    def test_sha_mismatch_refused(self):
        p = self.toml(f'[voice_a]\nref = "refs/voice_a_ref.wav"\nsha256 = "{"0" * 64}"\nf0_target_hz = 102\n'
                      'f0_tolerance_hz = 8\n')
        with self.assertRaisesRegex(VoiceRefused, "does not match"):
            Registry.load(p).get("voice_a").verify()

    def test_bad_files(self):
        for body, msg in (('[voice_a]\nref = "x.wav"\nsha256 = "abc"\n', "sha256"),
                          ('[Voice_A]\nref = ""\n', "voice id"),
                          (f'[voice_a]\nref = "x.wav"\nsha256 = "{self.sha}"\nf0_target_hz = 1\n'
                           'f0_tolerance_hz = 1\nagreement_in_place = "yes"\n', "agreement_in_place"),
                          ('[voice_a]\nref = ""\ndonor = "x"\n', "unknown field")):
            with self.assertRaisesRegex(VoiceError, msg):
                Registry.load(self.toml(body))

    def test_json_voices_file(self):
        p = write(self.root, "voices.json", json.dumps({"voices": {"voice_a": {
            "ref": str(self.ref), "sha256": self.sha, "f0_target_hz": 102, "f0_tolerance_hz": 8}}}))
        self.assertEqual(Registry.load(p).get("voice_a").verify(), self.sha)


class Refusals(unittest.TestCase):
    """Refusals happen before any model loads, so they need no model."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        ref = write(root, "refs/voice_b_ref.wav", "not audio")
        sha = hashlib.sha256(ref.read_bytes()).hexdigest()
        self.voices = write(root, "voices.toml", f'[voice_b]\nref = "refs/voice_b_ref.wav"\nsha256 = "{sha}"\n'
                                                 'f0_target_hz = 196\nf0_tolerance_hz = 12\n')
        self.job = root / "job"
        write(self.job, "script.txt", "Looking for funding?")
        write(self.job, "voice.txt", "voice_b")

    def tearDown(self):
        self.tmp.cleanup()

    def test_publish_without_agreement_is_refused(self):
        res = render(self.job, voices=self.voices, deliver=["local", "publish"], isolate=False)
        self.assertEqual((res.status, res.exit_code), ("refused", 3))
        self.assertIn("voice_b: agreement_in_place is false", res.refusals[0])
        result = json.loads((self.job / "out" / "result.json").read_text())
        self.assertEqual(result["status"], "refused")
        self.assertFalse((self.job / ".work").exists())

    def test_wrong_reference_is_refused(self):
        (Path(self.tmp.name) / "refs/voice_b_ref.wav").write_text("changed")
        res = render(self.job, voices=self.voices, isolate=False)
        self.assertEqual(res.status, "refused")
        self.assertIn("sha256 does not match", res.refusals[0])

    def test_unknown_voice_and_unimplemented_sink(self):
        res = render(self.job, voices=None, isolate=False)
        self.assertEqual((res.status, res.exit_code), ("invalid", 2))
        res = render(self.job, voices=self.voices, deliver=["commit"], isolate=False)
        self.assertEqual(res.status, "invalid")
        self.assertIn("not in this version: commit", res.errors[0])

    def test_validate(self):
        job, problems = validate(self.job, voices=self.voices)
        self.assertEqual((job.id, problems), ("job", []))
        _, problems = validate(self.job)
        self.assertIn("not in the voices registry", problems[0])


if __name__ == "__main__":
    unittest.main()
