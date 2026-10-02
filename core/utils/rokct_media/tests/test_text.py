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

"""Text normalisation and pronunciations. Model-free; lifted from factory
voice_batch/tests (test_voice_batch.TextNorm, test_pronunciations)."""
import json
import unittest

from rokct_media.speech.plan import PlanError, sentence_item, whole_take_line, render_parts
from rokct_media.text import pronounce as P
from rokct_media.text.norm import TAIL_PAD, norm_words, speak_text, split_sentences, tts_prompt, word_errors

PRON = P.validate({
    "words": {"Mahikeng": "mah-hee-KENG", "Nkosi": "n-KOH-see"},
    "ambiguous": {"Thendo": ["TEN-doh", "TEN-dooh"]},
})


class TextNorm(unittest.TestCase):
    def test_split(self):
        self.assertEqual(split_sentences("Right. Go on! Why?  Yes."), ["Right.", "Go on!", "Why?", "Yes."])

    def test_speak_text_punctuation_only(self):
        self.assertEqual(speak_text("Method: a by c - two, three — done."), "Method, a by c, two, three, done.")
        self.assertEqual(norm_words(speak_text("Stay — with me.")), norm_words("Stay — with me."))

    def test_numbers_and_symbols(self):
        self.assertEqual(word_errors("two x squared minus five x minus one", "2x² - 5x - 1"), 0)
        self.assertEqual(word_errors("minus twelve", "-12"), 0)
        self.assertEqual(word_errors("forty minutes", "40 minutes."), 0)

    def test_spelling_and_punctuation(self):
        self.assertEqual(word_errors("Practise tomorrow's drill.", "Practice tomorrows drill"), 0)
        self.assertEqual(word_errors("Top-level work", "top level work"), 0)

    def test_asr_homophones(self):
        ref = "We move quickly and we move correctly — nothing in this session is guessed."
        self.assertEqual(word_errors(ref, "We move quickly and we move correctly, nothing in this session is guest."), 0)
        self.assertEqual(word_errors("Our guest.", "Our guessed."), 0)
        self.assertEqual(word_errors(ref, "We move quickly and we move correctly, nothing in this session is best."), 1)

    def test_tts_prompt_pads_the_end(self):
        self.assertEqual(TAIL_PAD, " ...")
        self.assertEqual(tts_prompt("Let us begin."), "Let us begin. ...")
        self.assertEqual(tts_prompt("Ready?"), "Ready? ...")
        self.assertEqual(tts_prompt("Not you, not today "), "Not you, not today. ...")
        self.assertEqual(norm_words(tts_prompt("Two x minus 3.")), norm_words("Two x minus 3."))

    def test_real_errors_count(self):
        self.assertEqual(word_errors("Let us start.", "Let's start."), 2)
        self.assertEqual(word_errors("Done.", ""), 1)


class ShippedFile(unittest.TestCase):
    def test_empty_and_valid(self):
        raw = json.loads(P.PRONUNCIATIONS.read_text(encoding="utf-8"))
        self.assertEqual((raw["words"], raw["ambiguous"]), ({}, {}))
        self.assertIn("{{", raw["_comment"])
        self.assertEqual(P.load(), P.empty())


class Validate(unittest.TestCase):
    def test_rejects(self):
        for bad in ({"words": {"x": ""}}, {"words": {"x": "a.b"}}, {"words": {"x": "a|b"}},
                    {"words": {"1x": "y"}}, {"words": []}, {"ambiguous": {"Thendo": ["TEN-doh"]}},
                    {"ambiguous": {"Thendo": "TEN-doh"}}, {"other": {}},
                    {"words": {"Thendo": "x"}, "ambiguous": {"thendo": ["a", "b"]}}):
            with self.assertRaises(P.PronunciationError, msg=str(bad)):
                P.validate(bad)

    def test_multiword_and_comment(self):
        p = P.validate({"_comment": "x", "words": {"Mr Zulu": "mister ZOO-loo"}})
        self.assertEqual(P.apply("Hi, Mr Zulu.", p)[1], "Hi, mister ZOO-loo.")


class Merge(unittest.TestCase):
    def test_job_map_over_global(self):
        m = P.merge(PRON, {"words": {"mahikeng": "MAH-ee-keng", "Rokct": "Rocket"},
                           "ambiguous": {"Nkosi": ["n-KOH-see", "NKO-see"]}})
        self.assertEqual(m["words"], {"mahikeng": "MAH-ee-keng", "Rokct": "Rocket"})
        self.assertEqual(set(m["ambiguous"]), {"Thendo", "Nkosi"})
        self.assertIs(P.merge(PRON, None), PRON)
        with self.assertRaises(P.PronunciationError):
            P.merge(PRON, {"words": {"x": "a|b"}})


class Inline(unittest.TestCase):
    def test_with_punctuation(self):
        d, t, w = P.apply("Well done, {{Thendo|TEN-doh}}!")
        self.assertEqual((d, t, w), ("Well done, Thendo!", "Well done, TEN-doh!", [["Thendo", "TEN-doh"]]))
        d, t, _ = P.apply("({{Thendo|TEN-dooh}}'s turn.)")
        self.assertEqual((d, t), ("(Thendo's turn.)", "(TEN-dooh's turn.)"))

    def test_several_per_line(self):
        d, t, w = P.apply("{{Thendo|TEN-doh}} and {{Thendo|TEN-dooh}} met {{Lerato|leh-RAH-toh}}.")
        self.assertEqual(d, "Thendo and Thendo met Lerato.")
        self.assertEqual(t, "TEN-doh and TEN-dooh met leh-RAH-toh.")
        self.assertEqual([x[1] for x in w], ["TEN-doh", "TEN-dooh", "leh-RAH-toh"])

    def test_malformed_rejected(self):
        for bad in ("Hi {{Thendo}}.", "Hi {{Thendo|}}.", "Hi {{|TEN-doh}}.", "Hi {{Thendo|TEN-doh}.",
                    "Hi {Thendo|TEN-doh}}.", "Hi {{Thendo|TEN|doh}}.", "Hi }} there."):
            with self.assertRaises(P.PronunciationError, msg=bad):
                P.apply(bad, PRON)

    def test_inline_wins_over_global(self):
        d, t, w = P.apply("From {{Mahikeng|MAH-ee-keng}} to Mahikeng.", PRON)
        self.assertEqual(d, "From Mahikeng to Mahikeng.")
        self.assertEqual(t, "From MAH-ee-keng to mah-hee-KENG.")
        self.assertEqual(w, [["Mahikeng", "MAH-ee-keng"], ["Mahikeng", "mah-hee-KENG"]])


class Global(unittest.TestCase):
    def test_whole_words_any_case(self):
        d, t, w = P.apply("Nkosi's class, nkosi, Nkosinathi.", PRON)
        self.assertEqual(t, "n-KOH-see's class, n-KOH-see, Nkosinathi.")
        self.assertEqual(len(w), 2)

    def test_never_touches_ambiguous(self):
        self.assertEqual(P.apply("Thendo.", PRON)[1], "Thendo.")

    def test_ambiguous_case_and_possessive(self):
        self.assertEqual(P.ambiguous_uses("THENDO's book, {{Thendo|x}}", PRON), ["Thendo"])
        self.assertEqual(P.ambiguous_uses("Thendos", PRON), [])


class Wildcard(unittest.TestCase):
    def test_respelled_word_matches_one_to_n(self):
        w = [["Thendo", "TEN-doh"]]
        for hyp in ("Hi Thendo.", "Hi Tendo.", "Hi, ten doe.", "Hi ten though so."):
            self.assertEqual(P.word_errors_wild("Hi Thendo.", hyp, w), 0, hyp)
        self.assertEqual(P.word_errors_wild("Hi Thendo.", "Hi.", w), 1)
        self.assertEqual(P.word_errors_wild("Hi Thendo.", "Hi ten doe so much.", w), 1)

    def test_other_words_stay_exact(self):
        w = [["Thendo", "TEN-doh"]]
        self.assertEqual(P.word_errors_wild("Well done Thendo.", "Well gone Tendo.", w), 1)
        self.assertEqual(P.word_errors_wild("Thendo said two.", "Tendo said 2.", w), 0)

    def test_no_wild_is_word_errors(self):
        for ref, hyp in (("Let us start.", "Let's start."), ("Done.", ""), ("a b c", "a x c")):
            self.assertEqual(P.word_errors_wild(ref, hyp, []), word_errors(ref, hyp))
            self.assertEqual(P.word_errors_wild(ref, hyp, None), word_errors(ref, hyp))


class Plans(unittest.TestCase):
    def test_sentence_item(self):
        a = sentence_item({"id": "s01", "text": "Hi {{Thendo|TEN-doh}}. Welcome to Mahikeng.\n"}, PRON)
        self.assertEqual(a["text"], "Hi Thendo. Welcome to Mahikeng.")
        self.assertEqual(a["sentences"], ["Hi Thendo.", "Welcome to Mahikeng."])
        self.assertEqual(a["render_text"], ["Hi TEN-doh.", "Welcome to mah-hee-KENG."])
        self.assertEqual(a["sentence_wild"], [[["Thendo", "TEN-doh"]], [["Mahikeng", "mah-hee-KENG"]]])
        self.assertEqual(a["tts_text"], "Hi TEN-doh. Welcome to mah-hee-KENG.")
        plain = sentence_item({"id": "s02", "text": "Plain line - with a dash."}, P.empty())
        self.assertNotIn("tts_text", plain)
        self.assertEqual(plain["render_text"], ["Plain line, with a dash."])

    def test_ambiguous_fails_without_quoting_the_line(self):
        with self.assertRaises(PlanError) as cm:
            sentence_item({"id": "s01", "text": "Hello Thendo."}, PRON)
        self.assertIn("s01 uses 'Thendo': write {{Thendo|TEN-doh}} or {{Thendo|TEN-dooh}}", str(cm.exception))
        self.assertNotIn("Hello", str(cm.exception))

    def test_render_parts_join_short(self):
        self.assertEqual(render_parts("Begin. Here is the plan for today."), ["Begin. Here is the plan for today."])
        self.assertEqual(render_parts("Looking for funding? Here's one you can apply for, right now."),
                         ["Looking for funding?", "Here's one you can apply for, right now."])
        self.assertEqual(render_parts("This one is long enough. Go now."), ["This one is long enough. Go now."])

    def test_whole_take_line(self):
        ln = whole_take_line({"id": "open", "text": "Looking for funding? Here's one you can apply for, right now.",
                              "prefer_seeds": [44]}, P.empty())
        self.assertEqual(ln["rounds"], [[44], [11, 22, 33], [55]])
        self.assertEqual(ln["tts_parts"], ln["parts"])
        self.assertEqual(ln["takes"], 1)
        with self.assertRaises(PlanError):
            whole_take_line({"id": "x", "text": "Hi there.", "prefer_seeds": [99]}, P.empty())
        with self.assertRaises(PlanError):
            whole_take_line({"id": "x", "text": "Hi there.", "keep_through": "Rocket"}, P.empty())
        ln = whole_take_line({"id": "brand", "text": "{{Rokct|Rocket}} tutors.", "keep_through": "Rokct"}, P.empty())
        self.assertEqual((ln["text"], ln["tts_parts"]), ("Rokct tutors.", ["Rocket tutors."]))


if __name__ == "__main__":
    unittest.main()
