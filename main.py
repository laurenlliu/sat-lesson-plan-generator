"""
SAT Lesson Plan Generator — CLI entry point.

Given one or two College Board digital SAT/PSAT score report PDFs for
a student (most recent, and optionally a prior test for comparison),
extracts performance data, ranks weak content domains, and generates
a personalized multi-week lesson plan using the Claude API.

Usage:
    python main.py path/to/current_report.pdf
    python main.py path/to/current_report.pdf path/to/previous_report.pdf

Requires ANTHROPIC_API_KEY to be set in your environment.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from generate_lesson_plan import generate_lesson_plan  # noqa: E402


def main():
    if len(sys.argv) not in (2, 3):
        print("Usage: python main.py current_report.pdf [previous_report.pdf]")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: set the ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    current_pdf = sys.argv[1]
    previous_pdf = sys.argv[2] if len(sys.argv) == 3 else None

    print("Extracting score report data and generating lesson plan...\n")
    plan = generate_lesson_plan(current_pdf, previous_pdf)

    os.makedirs("output", exist_ok=True)
    out_path = os.path.join("output", "lesson_plan.md")
    with open(out_path, "w") as f:
        f.write(plan)

    print(plan)
    print(f"\n\nSaved to {out_path}")


if __name__ == "__main__":
    main()
