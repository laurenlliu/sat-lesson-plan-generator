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

    if not os.environ.get("GROQ_API_KEY"):
        print("\nSet GROQ_API_KEY (free at console.groq.com) to also generate a full "
              "lesson plan from this ranking (see generate_lesson_plan.py).")
        return

    from generate_lesson_plan import build_user_prompt, SYSTEM_PROMPT, MODEL
    from openai import OpenAI
    from types import SimpleNamespace

    report_ns = SimpleNamespace(**report)
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY"),
    )
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=7000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(report_ns, ranked)},
        ],
    )
    print("\n\n" + response.choices[0].message.content)

    os.makedirs("output", exist_ok=True)
    md_path = os.path.join("output", "sample_lesson_plan.md")
    with open(md_path, "w") as f:
        f.write(response.choices[0].message.content)

    from render_pdf import render_pdf
    pdf_path = os.path.join("output", "sample_lesson_plan.pdf")
    render_pdf(md_path, pdf_path)
    print(f"\n\nSaved to {md_path} and {pdf_path}")


if __name__ == "__main__":
    main()
