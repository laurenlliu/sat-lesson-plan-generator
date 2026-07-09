"""
Generates a time-blocked 2-hour SAT tutoring session plan from ranked
domain data using the Groq API (Llama 3.3 70B), which is free to use
with generous rate limits and no credit card required.

Important: this does NOT pull from or reproduce any official
College Board test content. Score reports only expose performance
bands per content domain, not individual missed questions, so there
is no real question bank to draw from here. Instead, the model
generates original, SAT-style practice questions for each priority
domain. A tutor should review generated questions before handing
them to a student; this tool is meant to support lesson planning, not
replace tutor judgment.

Requires a GROQ_API_KEY environment variable (free at console.groq.com).

Usage:
    python generate_lesson_plan.py current_report.pdf [previous_report.pdf]
"""

import os
import sys
import json

from openai import OpenAI

from extract_report import extract_report
from rank_domains import rank_domains

MODEL = "llama-3.3-70b-versatile"

# Page references from "The Princeton Review ACT Prep 2026" table of
# contents, mapped by conceptual overlap to each SAT/PSAT content domain.
# The ACT and SAT test different content in different structures, so
# these are best-effort conceptual matches, not exact equivalents.
# Hardcoded (not model-generated) so page numbers are never hallucinated.
ACT_BOOK_PAGE_MAP = {
    "Standard English Conventions": "Sentence Basics, Punctuation Rules, Grammar Rules (pp. 139-190)",
    "Expression of Ideas": "Content Questions: Transitions and Purpose; Paragraph and Whole Essay (pp. 201-224)",
    "Information and Ideas": "The 6-Step Basic Approach; Advanced Reading Skills (pp. 421-480)",
    "Craft and Structure": "The 6-Step Basic Approach; Advanced Reading Skills (pp. 421-480)",
    "Algebra": "Fundamentals; No More Algebra (pp. 237-282)",
    "Advanced Math": "Advanced Math [ACT chapter] (pp. 391-402)",
    "Problem-Solving and Data Analysis": "Word Problems (pp. 319-350)",
    "Geometry and Trigonometry": "Plane Geometry; Graphing and Coordinate Geometry; Trigonometry (pp. 283-318, 351-402)",
}

SYSTEM_PROMPT = """You are an experienced SAT tutor preparing a single 2-hour \
tutoring session plan for a student, based on their College Board score \
report data, for a parent/manager to review and approve before the session.

You are given content domains ranked by tutoring priority (combining how \
weak the student's performance band is with how much that domain is worth \
on the actual test). The digital SAT/PSAT does not provide individual missed \
questions, only performance bands per content domain, so build the plan \
around domain-level weaknesses, not specific missed questions.

Structure the plan as a time-blocked breakdown of the full 2 hours, covering \
the 2-3 highest priority domains (not all 8, there isn't time). For each \
time block, include:
- The time range (e.g. "0:00-0:40") and domain being covered
- A short, plain-language explanation of what the domain tests (2-3 sentences)
- 6-8 original SAT-style practice questions (multiple choice, 4 options), \
with an answer key and a one-sentence explanation per question. This is \
important: a 30-40 minute block needs enough questions to fill the actual \
tutoring time, not just 2-3. Assume roughly 3-4 minutes per question \
including review and discussion, and size the question count to the block's \
length accordingly.
- What the tutor should focus on/watch for during that block

Include a short block at the end (5-10 min) for review or a quick check of \
understanding. Time blocks should sum to 2 hours total.

If a domain includes a "Book reference" line, include that reference \
verbatim in the time block (e.g. "Book: pp. 139-190") so the tutor knows \
what to review beforehand. Never invent page numbers or book references \
that were not explicitly provided.

Do not reference or reproduce real SAT questions; generate original \
practice questions only, clearly written in the style and difficulty of \
the domain. Keep the tone practical, written for a parent or manager to \
quickly review and approve, not for the student directly."""


def build_user_prompt(report, ranked_domains: list) -> str:
    domain_summary = "\n".join(
        f"- {d['name']} ({d['section']}, {d['weight_pct']}% of section): "
        f"performance band {d['perf_low']}-{d['perf_high']}"
        + (f", moved {d['change']:+.0f} pts since last test" if "change" in d else "")
        + (f"\n  Book reference: {ACT_BOOK_PAGE_MAP[d['name']]}" if d['name'] in ACT_BOOK_PAGE_MAP else "")
        for d in ranked_domains
    )

    return f"""Student: {report.student_name} (Grade {report.grade})
Most recent test: {report.test_administration}, total score {report.total_score}
Reading & Writing: {report.rw_score} ({report.rw_percentile})
Math: {report.math_score} ({report.math_percentile})

Domains ranked by tutoring priority (highest priority first):
{domain_summary}

Each domain includes a "Book reference" pointing to the tutor's Princeton \
Review ACT Prep book. Include this reference verbatim in each time block \
(e.g. "Book: pp. 139-190") so the tutor knows what to review beforehand. \
Do not invent additional page numbers beyond what's given.

Build a single 2-hour session plan focused on the top 2-3 priority domains."""


def generate_lesson_plan(current_pdf: str, previous_pdf: str = None) -> str:
    report = extract_report(current_pdf)
    previous_report = extract_report(previous_pdf) if previous_pdf else None

    ranked = rank_domains(
        report.domains,
        previous_report.domains if previous_report else None,
    )

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY"),
    )
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=7000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(report, ranked)},
        ],
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: python generate_lesson_plan.py current_report.pdf [previous_report.pdf]")
        sys.exit(1)

    if not os.environ.get("GROQ_API_KEY"):
        print("Error: set the GROQ_API_KEY environment variable first (get a free key at console.groq.com).")
        sys.exit(1)

    current_pdf = sys.argv[1]
    previous_pdf = sys.argv[2] if len(sys.argv) == 3 else None

    plan = generate_lesson_plan(current_pdf, previous_pdf)
    print(plan)
