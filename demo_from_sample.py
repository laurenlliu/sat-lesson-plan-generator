"""
Runs the ranking + lesson plan generation steps against the bundled
synthetic sample report (samples/sample_extracted_report.json),
skipping PDF extraction entirely. Useful for trying the tool out
without a real score report PDF on hand.

Usage:
    python demo_from_sample.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rank_domains import rank_domains  # noqa: E402


def main():
    with open("samples/sample_extracted_report.json") as f:
        report = json.load(f)

    ranked = rank_domains(report["domains"])
    print("Domains ranked by tutoring priority:\n")
    for d in ranked:
        print(f"  {d['priority_score']:>5.1f}  {d['name']} ({d['section']}, "
              f"band {d['perf_low']}-{d['perf_high']})")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nSet ANTHROPIC_API_KEY to also generate a full lesson plan "
              "from this ranking (see generate_lesson_plan.py).")
        return

    from generate_lesson_plan import build_user_prompt, SYSTEM_PROMPT, MODEL
    import anthropic
    from types import SimpleNamespace

    report_ns = SimpleNamespace(**report)
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(report_ns, ranked)}],
    )
    print("\n\n" + message.content[0].text)


if __name__ == "__main__":
    main()
