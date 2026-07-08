"""
Generates a personalized, multi-week SAT lesson plan from ranked
domain data using the Claude API.

Important: this does NOT pull from or reproduce any official
College Board test content. Score reports only expose performance
bands per content domain, not individual missed questions, so there
is no real question bank to draw from here. Instead, Claude generates
original, SAT-style practice questions for each priority domain. A
tutor should review generated questions before handing them to a
student; this tool is meant to support lesson planning, not replace
tutor judgment.

Requires an ANTHROPIC_API_KEY environment variable.

Usage:
    python generate_lesson_plan.py current_report.pdf [previous_report.pdf]
"""

import os
import sys
import json

import anthropic

from extract_report import extract_report
from rank_domains import rank_domains

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an experienced SAT tutor building a personalized \
lesson plan for a student, based on their College Board score report data. \
You are given content domains ranked by tutoring priority (combining how \
weak the student's performance band is with how much that domain is worth \
on the actual test).

For each of the top priority domains, provide:
- A short, plain-language explanation of what the domain tests
- 2-3 original SAT-style practice questions (multiple choice, 4 options), \
with an answer key and a one-sentence explanation per question
- A suggested amount of tutoring time to spend on it relative to the others

Then provide an overall multi-week pacing plan sequencing the domains.

Do not reference or reproduce real SAT questions; generate original \
practice questions only, clearly written in the style and difficulty of \
the domain. Keep the tone practical and encouraging, written for a tutor \
to hand directly to a student or use as a session outline."""


def build_user_prompt(report, ranked_domains: list) -> str:
    domain_summary = "\n".join(
        f"- {d['name']} ({d['section']}, {d['weight_pct']}% of section): "
        f"performance band {d['perf_low']}-{d['perf_high']}"
        + (f", moved {d['change']:+.0f} pts since last test" if "change" in d else "")
        for d in ranked_domains
    )

    return f"""Student: {report.student_name} (Grade {report.grade})
Most recent test: {report.test_administration}, total score {report.total_score}
Reading & Writing: {report.rw_score} ({report.rw_percentile})
Math: {report.math_score} ({report.math_percentile})

Domains ranked by tutoring priority (highest priority first):
{domain_summary}

Build a lesson plan focused on the top 4 priority domains."""


def generate_lesson_plan(current_pdf: str, previous_pdf: str = None) -> str:
    report = extract_report(current_pdf)
    previous_report = extract_report(previous_pdf) if previous_pdf else None

    ranked = rank_domains(
        report.domains,
        previous_report.domains if previous_report else None,
    )

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(report, ranked)}],
    )

    return message.content[0].text


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: python generate_lesson_plan.py current_report.pdf [previous_report.pdf]")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: set the ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    current_pdf = sys.argv[1]
    previous_pdf = sys.argv[2] if len(sys.argv) == 3 else None

    plan = generate_lesson_plan(current_pdf, previous_pdf)
    print(plan)
