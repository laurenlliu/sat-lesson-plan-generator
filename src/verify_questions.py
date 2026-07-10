"""
Verification pass for the math practice questions in a generated lesson
plan. Llama 3.3 70B (the free model this project uses) is fast but not
fully reliable at multi-step math -- in testing, roughly half of the
generated math practice questions had incorrect stated answers. This
module re-checks each math question's stated answer against an
independent solve, regenerates the question once if they disagree, and
flags it for manual review if it still can't be confirmed.

Parsing relies on the strict per-question format the system prompt in
generate_lesson_plan.py requires the model to follow:

    ### <time range> — <Domain Name>
    ...
    1. **<question text>**
    - A) <choice>
    - B) <choice>
    - C) <choice>
    - D) <choice>
    Answer: <letter> — <one-sentence explanation>

Reading/Writing questions aren't re-verified here since the documented
failure mode is specifically multi-step math, not reading comprehension.
"""

import re
from typing import Optional

MATH_DOMAINS = {
    "Algebra",
    "Advanced Math",
    "Problem-Solving and Data Analysis",
    "Geometry and Trigonometry",
}

DOMAIN_HEADER_RE = re.compile(r"^###.*—\s*(.+?)\s*$")
QUESTION_NUM_RE = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*$")
CHOICE_RE = re.compile(r"^-\s*([A-D])\)\s*(.+)$")
ANSWER_RE = re.compile(r"^Answer:\s*([A-D])\s*—\s*(.+)$", re.IGNORECASE)


def parse_plan_questions(plan_text: str) -> list:
    """Extracts every well-formed practice question from a generated plan.

    Returns a list of dicts: domain, number, question, choices (dict
    A-D -> text), answer_letter, explanation, and raw_text (the exact
    verbatim chunk from the numbered line through the answer line, so it
    can be located and replaced later with a plain string match)."""
    lines = plan_text.split("\n")
    results = []
    current_domain = None
    i = 0
    while i < len(lines):
        # Match against the stripped line so the model's incidental
        # indentation (it doesn't always reproduce the prompt's example
        # formatting at zero indent) doesn't break parsing.
        header_match = DOMAIN_HEADER_RE.match(lines[i].strip())
        if header_match:
            current_domain = header_match.group(1).strip()
            i += 1
            continue

        question_match = QUESTION_NUM_RE.match(lines[i].strip())
        if question_match and current_domain:
            choices = {}
            j = i + 1
            while j < len(lines):
                choice_match = CHOICE_RE.match(lines[j].strip())
                if not choice_match:
                    break
                choices[choice_match.group(1)] = choice_match.group(2).strip()
                j += 1

            answer_match = ANSWER_RE.match(lines[j].strip()) if len(choices) == 4 and j < len(lines) else None
            if answer_match:
                results.append({
                    "domain": current_domain,
                    "number": question_match.group(1),
                    "question": question_match.group(2),
                    "choices": choices,
                    "answer_letter": answer_match.group(1).upper(),
                    "explanation": answer_match.group(2).strip(),
                    "raw_text": "\n".join(lines[i:j + 1]),
                })
                i = j + 1
                continue
        i += 1
    return results


def _solve_independently(client, model: str, question: dict) -> Optional[str]:
    prompt = (
        "Solve this SAT-style multiple-choice question independently. "
        "Respond with only the single correct letter (A, B, C, or D) and nothing else.\n\n"
        f"{question['question']}\n"
        + "\n".join(f"{letter}) {text}" for letter, text in question["choices"].items())
    )
    response = client.chat.completions.create(
        model=model,
        max_tokens=20,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    match = re.search(r"\b([A-D])\b", response.choices[0].message.content.upper())
    return match.group(1) if match else None


def verify_question(client, model: str, question: dict) -> bool:
    return _solve_independently(client, model, question) == question["answer_letter"]


def regenerate_question(client, model: str, domain: str) -> str:
    prompt = (
        f'Write ONE original SAT-style multiple-choice practice question (4 choices) '
        f'for the content domain "{domain}", along with the correct answer and a '
        f"one-sentence explanation. Double-check the math carefully before answering -- "
        f"work through it step by step first, then state the answer.\n\n"
        "Format it exactly like this, and include nothing else in your response:\n\n"
        "1. **<question text>**\n"
        "- A) <choice>\n- B) <choice>\n- C) <choice>\n- D) <choice>\n"
        "Answer: <letter> — <one-sentence explanation>"
    )
    response = client.chat.completions.create(
        model=model,
        max_tokens=400,
        temperature=0.5,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def verify_and_fix_plan(plan_text: str, client, model: str) -> tuple:
    """Re-checks every math question's stated answer, regenerating once on
    a mismatch and falling back to a visible warning if it still can't be
    confirmed. Returns (possibly-modified plan_text, summary dict)."""
    math_questions = [q for q in parse_plan_questions(plan_text) if q["domain"] in MATH_DOMAINS]

    summary = {"checked": 0, "auto_fixed": 0, "flagged": 0}
    for q in math_questions:
        summary["checked"] += 1
        if verify_question(client, model, q):
            continue

        regenerated_text = regenerate_question(client, model, q["domain"])
        regenerated = parse_plan_questions(f"### placeholder — {q['domain']}\n{regenerated_text}")

        if regenerated and verify_question(client, model, regenerated[0]):
            fixed_text = re.sub(r"^\s*\d+\.", f"{q['number']}.", regenerated_text.strip(), count=1)
            plan_text = plan_text.replace(q["raw_text"], fixed_text, 1)
            summary["auto_fixed"] += 1
        else:
            warning = q["raw_text"] + (
                "\n⚠️ Unverified — an independent check did not confirm this answer. "
                "Have a tutor re-solve before use."
            )
            plan_text = plan_text.replace(q["raw_text"], warning, 1)
            summary["flagged"] += 1

    return plan_text, summary
