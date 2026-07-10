# SAT Lesson Plan Generator

A tool that turns a student's College Board digital SAT/PSAT score report
into a time-blocked 2-hour tutoring session plan, generated with the
free Groq API (Llama 3.3 70B).

Built as a side project by an SAT tutor, for SAT tutors: hand it a score
report PDF, and get back a prioritized lesson plan targeting the student's
weakest, highest-value content domains, along with original practice
questions for each one.

## Why this exists

Score reports show performance by content domain (e.g. "Algebra: 420-460")
but not individual missed questions, so there's no way to build a lesson
plan around specific mistakes. This tool instead:

1. Extracts each domain's performance band and question weight from the PDF
2. Ranks domains by tutoring priority, combining how weak the band is with
   how much that domain is worth on the actual test
3. If given two reports for the same student, factors in improvement or
   decline between tests
4. Sends the ranked data to Llama 3.3 70B (via Groq), which drafts a
   time-blocked 2-hour session plan with original practice questions per
   domain, ready for a parent or manager to review and approve

**A note on practice questions:** these are model-generated, not pulled
from any real SAT test. Official SAT questions are College Board's
copyrighted material, so this tool doesn't source, store, or reproduce them.
A tutor should review generated questions before using them with a student.

## How it works

```
score_report.pdf
      │
      ▼
extract_report.py     → pulls student info, section scores, and the
                         8 content domain performance bands
      │
      ▼
rank_domains.py        → scores each domain by weakness + test weight
      │
      ▼
generate_lesson_plan.py → sends ranked domains to Llama 3.3 70B via Groq,
                          gets back a time-blocked session plan with
                          practice questions
      │
      ▼
verify_questions.py    → re-checks each math question's stated answer
                          against an independent solve, regenerating or
                          flagging any that don't hold up
      │
      ▼
render_pdf.py           → converts the plan into a clean, printable PDF
```

## Optional: tutoring book page references

`src/generate_lesson_plan.py` includes an `ACT_BOOK_PAGE_MAP` dictionary
that maps each SAT/PSAT domain to page ranges in a specific tutoring book
(currently set up for one edition of a Princeton Review ACT prep book,
since ACT and SAT content maps only loosely onto each other). Page numbers
are hardcoded, never model-generated, so they can't be hallucinated. If
you use a different book, update this dictionary with your own page
numbers, or remove the "Book reference" lines from the prompt entirely if
you don't want this feature.

## Setup

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your-key-here
```

Get a free Groq API key at [console.groq.com](https://console.groq.com), no
credit card required. The free tier's rate limits are more than enough for
this project's scale (generating a handful of lesson plans, not serving
production traffic).

## Usage

With a real score report PDF:

```bash
python main.py path/to/score_report.pdf

# Or compare against an earlier test for the same student:
python main.py path/to/latest_report.pdf path/to/earlier_report.pdf
```

This prints the lesson plan and saves both `output/lesson_plan.md` and
`output/lesson_plan.pdf` (clean, formatted, ready to print).

No score report on hand? Try the bundled synthetic sample:

```bash
python demo_from_sample.py
```

This runs the ranking step against `samples/sample_extracted_report.json`
(a fake student, no real data), and generates a full lesson plan too if
`GROQ_API_KEY` is set.

## Project structure

```
main.py                    CLI entry point
demo_from_sample.py         Try it without a PDF or real student data
src/
  extract_report.py         PDF → structured score data (pdfplumber)
  rank_domains.py            Ranks domains by tutoring priority
  generate_lesson_plan.py    Builds the prompt and generates the plan via Groq
  verify_questions.py        Re-checks math question answers, fixes or flags bad ones
  render_pdf.py              Converts the generated plan into a printable PDF
samples/
  sample_extracted_report.json   Synthetic example report for demos
tests/
  test_verify_questions.py       Tests for the verification pass (no API key needed)
```

## Running tests

```bash
python3 -m unittest discover tests
```

These use a fake model client (no API calls, no `GROQ_API_KEY` needed) and
pin down the question parser's tolerance for the kind of formatting
variation the model actually produces between runs (indentation, blank
lines) plus the verification pass's fix/flag logic.

## A note on privacy

Real student score reports contain personally identifiable information.
This repo does not include any real score report PDFs or extracted data;
the bundled sample uses a fictional student. If you use this tool with
real students, keep their reports and any extracted output out of version
control (the `.gitignore` here already excludes `*.pdf` and `output/`).

## Known limitations

Llama 3.3 70B (the free model this project uses) is fast but not fully
reliable at multi-step math. In testing, roughly half of the generated
math practice questions had incorrect stated answers, even though the
questions themselves looked plausible.

`src/verify_questions.py` mitigates this: after the plan is generated,
every math question's stated answer is re-checked with an independent
solve (a separate model call that doesn't see the proposed answer). If
the independent solve disagrees, the question is regenerated once and
re-checked; if it still can't be confirmed, the original question is
kept but flagged in the plan with a visible "⚠️ Unverified" note so the
tutor knows to double-check it by hand rather than trusting it silently.
Reading/Writing questions aren't re-checked, since the documented
failure mode is specifically multi-step math.

This roughly halves the questions a tutor needs to hand-verify, but it's
not a guarantee — the independent solve uses the same model, which can
occasionally agree on a wrong answer. For anything graded or
high-stakes, still pull real practice questions from College Board's
own MyPractice tool (which are pre-verified) and use this tool just for
domain ranking and session structure.

## Possible next steps

- Web UI for uploading a report and viewing the plan (currently CLI-only)
- Persisting lesson plans per student across sessions
- Support for the paper/school-day SAT report layout, in addition to the
  digital SAT/PSAT layout this currently targets
