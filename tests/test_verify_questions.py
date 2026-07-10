"""
Tests for src/verify_questions.py.

These exist because the parser broke twice in real use during
development: once on incidental indentation the model copied from a
prompt example, and once on a blank line the model inserted between the
last answer choice and the "Answer:" line. Both looked like they'd work
from reading the code; both silently found zero questions in practice.
These tests pin down that kind of model-formatting variation so a
future prompt tweak doesn't quietly break parsing again.

Run with: python3 -m unittest discover tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from verify_questions import (  # noqa: E402
    parse_plan_questions,
    verify_and_fix_plan,
    verify_question,
    _solve_independently,
)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content, finish_reason="stop"):
        self.message = FakeMessage(content)
        self.finish_reason = finish_reason


class FakeResponse:
    def __init__(self, content, finish_reason="stop"):
        self.choices = [FakeChoice(content, finish_reason)]


class FakeClient:
    """A stand-in for the OpenAI/Groq client that routes each call through
    a caller-supplied function, so tests can script model responses
    without hitting the network."""

    def __init__(self, respond_fn):
        self._respond_fn = respond_fn
        self.chat = self
        self.completions = self

    def create(self, model, max_tokens, messages, temperature=None):
        prompt = messages[-1]["content"]
        return FakeResponse(self._respond_fn(prompt))


WELL_FORMED_PLAN = """### 0:00-0:40 — Algebra
This block covers linear equations.

1. **If 3x + 5 = 20, what is the value of x?**
- A) 3
- B) 5
- C) 7
- D) 15
Answer: B — Subtract 5 from both sides to get 3x = 15, then divide by 3.

2. **If 2y - 4 = 10, what is y?**
- A) 3
- B) 5
- C) 7
- D) 9
Answer: C — Add 4 to both sides to get 2y = 14, then divide by 2 to get y = 7.

### 0:40-1:20 — Information and Ideas
This block covers reading comprehension.

1. **Which choice best supports the claim?**
- A) Choice one
- B) Choice two
- C) Choice three
- D) Choice four
Answer: A — This is the best textual support.
"""

# Mirrors the model's real, observed output: 2-space-indented choices/answer
# copied verbatim from a prompt example.
INDENTED_PLAN = """### 0:00-0:40 — Advanced Math
1. **What is the value of x in the equation 2x^2 + 5x - 3 = 0?**
  - A) -3
  - B) 1/2
  - C) 1/3
  - D) -1/2
  Answer: B — Factor or use the quadratic formula.
"""

# Mirrors the model's real, observed output: a blank line between the last
# choice and the Answer line.
BLANK_LINE_BEFORE_ANSWER_PLAN = """### 0:00-0:40 — Advanced Math
1. **What is the value of x in the equation 2sin(x) + 5cos(x) = 3?**
  - A) pi/6
  - B) pi/3
  - C) pi/4
  - D) pi/2

  Answer: B — Uses a trig identity.
"""

# Mirrors the model's real, observed output: a stray ")" after the answer
# letter (e.g. "Answer: B) — ...").
TRAILING_PAREN_ANSWER_PLAN = """### 0:00-0:40 — Advanced Math
1. **What is the value of x in the equation 2x + 3 = 9?**
  - A) 2
  - B) 3
  - C) 4
  - D) 5
  Answer: B) — Subtract 3 then divide by 2.
"""


class ParsePlanQuestionsTests(unittest.TestCase):
    def test_parses_every_question_with_correct_fields(self):
        parsed = parse_plan_questions(WELL_FORMED_PLAN)
        self.assertEqual(len(parsed), 3)

        first = parsed[0]
        self.assertEqual(first["domain"], "Algebra")
        self.assertEqual(first["number"], "1")
        self.assertEqual(first["question"], "If 3x + 5 = 20, what is the value of x?")
        self.assertEqual(first["choices"], {"A": "3", "B": "5", "C": "7", "D": "15"})
        self.assertEqual(first["answer_letter"], "B")
        self.assertIn("Subtract 5", first["explanation"])

        self.assertEqual(parsed[2]["domain"], "Information and Ideas")

    def test_raw_text_is_a_verbatim_substring_of_the_plan(self):
        parsed = parse_plan_questions(WELL_FORMED_PLAN)
        for q in parsed:
            self.assertIn(q["raw_text"], WELL_FORMED_PLAN)

    def test_tolerates_indented_choices_and_answer_line(self):
        parsed = parse_plan_questions(INDENTED_PLAN)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["domain"], "Advanced Math")
        self.assertEqual(parsed[0]["answer_letter"], "B")
        self.assertEqual(parsed[0]["choices"]["D"], "-1/2")

    def test_tolerates_blank_line_before_answer(self):
        parsed = parse_plan_questions(BLANK_LINE_BEFORE_ANSWER_PLAN)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["answer_letter"], "B")

    def test_tolerates_trailing_paren_after_answer_letter(self):
        parsed = parse_plan_questions(TRAILING_PAREN_ANSWER_PLAN)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["answer_letter"], "B")

    def test_ignores_questions_outside_any_domain_header(self):
        no_header = "1. **Orphan question?**\n- A) x\n- B) y\n- C) z\n- D) w\nAnswer: A — because.\n"
        self.assertEqual(parse_plan_questions(no_header), [])

    def test_ignores_malformed_question_missing_a_choice(self):
        missing_choice = (
            "### 0:00-0:40 — Algebra\n"
            "1. **Question?**\n- A) x\n- B) y\n- C) z\nAnswer: A — because.\n"
        )
        self.assertEqual(parse_plan_questions(missing_choice), [])


class SolveIndependentlyTests(unittest.TestCase):
    QUESTION = {
        "question": "What is 2+2?",
        "choices": {"A": "3", "B": "4", "C": "5", "D": "6"},
        "answer_letter": "B",
    }

    def test_reads_final_answer_line(self):
        client = FakeClient(lambda prompt: "2+2 is basic addition.\nFINAL ANSWER: B")
        self.assertEqual(_solve_independently(client, "fake-model", self.QUESTION), "B")

    def test_falls_back_to_last_letter_if_final_answer_line_missing(self):
        client = FakeClient(lambda prompt: "Thinking... the answer is B, not A.")
        self.assertEqual(_solve_independently(client, "fake-model", self.QUESTION), "B")

    def test_none_when_model_says_none_of_the_choices_match(self):
        client = FakeClient(lambda prompt: "None of these add up.\nFINAL ANSWER: NONE")
        self.assertIsNone(_solve_independently(client, "fake-model", self.QUESTION))

    def test_none_when_response_never_states_a_letter(self):
        client = FakeClient(lambda prompt: "I'm not sure how to approach this one at all.")
        self.assertIsNone(_solve_independently(client, "fake-model", self.QUESTION))

    def test_verify_question_true_when_independent_solve_matches(self):
        client = FakeClient(lambda prompt: "FINAL ANSWER: B")
        self.assertTrue(verify_question(client, "fake-model", self.QUESTION))

    def test_verify_question_false_on_mismatch(self):
        client = FakeClient(lambda prompt: "FINAL ANSWER: C")
        self.assertFalse(verify_question(client, "fake-model", self.QUESTION))


class VerifyAndFixPlanTests(unittest.TestCase):
    PLAN = """### 0:00-0:40 — Algebra
1. **Correct question: what is 2+2?**
- A) 3
- B) 4
- C) 5
- D) 6
Answer: B — 2+2 is 4.

2. **Wrong-but-fixable question: what is 3+3?**
- A) 5
- B) 6
- C) 7
- D) 8
Answer: A — stated wrong on purpose, should be B.

3. **Wrong-and-unfixable question: what is 4+4?**
- A) 6
- B) 7
- C) 9
- D) 10
Answer: B — stated wrong on purpose and the regen will fail too.
"""

    def _make_router(self):
        def respond(prompt):
            if "Correct question" in prompt and "FINAL ANSWER" in prompt:
                return "FINAL ANSWER: B"
            if "Wrong-but-fixable question: what is 3+3" in prompt and "FINAL ANSWER" in prompt:
                return "FINAL ANSWER: B"  # 3+3 is really 6 (B), disagreeing with the stated A
            if "Write ONE original" in prompt and self._regen_calls == 0:
                self._regen_calls += 1
                return (
                    "1. **Regenerated: what is 10+10?**\n"
                    "- A) 19\n- B) 20\n- C) 21\n- D) 22\n"
                    "Answer: B — 10+10 is 20."
                )
            if "Regenerated: what is 10+10" in prompt and "FINAL ANSWER" in prompt:
                return "FINAL ANSWER: B"
            if "Wrong-and-unfixable question: what is 4+4" in prompt and "FINAL ANSWER" in prompt:
                return "FINAL ANSWER: A"  # disagrees with stated B, triggers regen
            if "Write ONE original" in prompt:
                return (
                    "1. **Still-wrong regen: what is 5+5?**\n"
                    "- A) 9\n- B) 10\n- C) 11\n- D) 12\n"
                    "Answer: A — stated wrong again on purpose."
                )
            if "Still-wrong regen: what is 5+5" in prompt and "FINAL ANSWER" in prompt:
                return "FINAL ANSWER: B"  # disagrees with regen's stated A -- stays broken
            raise AssertionError(f"unexpected prompt: {prompt!r}")

        self._regen_calls = 0
        return respond

    def test_correct_question_is_left_untouched(self):
        client = FakeClient(self._make_router())
        result_text, summary = verify_and_fix_plan(self.PLAN, client, "fake-model")
        self.assertIn("Correct question: what is 2+2?", result_text)
        self.assertIn("Answer: B — 2+2 is 4.", result_text)

    def test_fixable_question_gets_auto_corrected_with_original_numbering(self):
        client = FakeClient(self._make_router())
        result_text, summary = verify_and_fix_plan(self.PLAN, client, "fake-model")
        self.assertEqual(summary["auto_fixed"], 1)
        self.assertIn("2. **Regenerated: what is 10+10?**", result_text)
        self.assertNotIn("Wrong-but-fixable question: what is 3+3", result_text)

    def test_unfixable_question_is_flagged_not_silently_wrong(self):
        client = FakeClient(self._make_router())
        result_text, summary = verify_and_fix_plan(self.PLAN, client, "fake-model")
        self.assertEqual(summary["flagged"], 1)
        self.assertIn("Wrong-and-unfixable question: what is 4+4", result_text)
        self.assertIn("⚠️ Unverified", result_text)

    def test_summary_counts_every_math_question_checked(self):
        client = FakeClient(self._make_router())
        _, summary = verify_and_fix_plan(self.PLAN, client, "fake-model")
        self.assertEqual(summary["checked"], 3)

    def test_non_math_domain_questions_are_never_checked(self):
        plan = (
            "### 0:00-0:40 — Information and Ideas\n"
            "1. **What's the main idea?**\n- A) x\n- B) y\n- C) z\n- D) w\n"
            "Answer: A — because, even though this is actually wrong.\n"
        )
        client = FakeClient(lambda prompt: (_ for _ in ()).throw(
            AssertionError("should never call the model for a non-math domain")
        ))
        result_text, summary = verify_and_fix_plan(plan, client, "fake-model")
        self.assertEqual(summary["checked"], 0)
        self.assertEqual(result_text, plan)


if __name__ == "__main__":
    unittest.main()
