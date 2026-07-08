"""
Extracts structured score data from College Board digital SAT / PSAT
score report PDFs.

These reports do not expose individual missed questions, only
performance bands per content domain (e.g. "Performance: 420-480")
along with each domain's weight in the section. This module pulls out:

  - student name, grade, test administration, test date
  - total score, section scores (Reading & Writing, Math), percentiles
  - each of the 8 content domains: name, section, question weight,
    performance band (low/high)

The domain breakdown is laid out in two side-by-side columns (Reading
and Writing on the left, Math on the right), which plain text
extraction interleaves incorrectly. We use pdfplumber's word
coordinates to split the page by x-position and reconstruct each
column separately before parsing.

Usage:
    python extract_report.py path/to/report.pdf
"""

import re
import sys
import json
import subprocess
from collections import defaultdict
from dataclasses import dataclass, asdict

import pdfplumber

# Domains appear in this order within each column, top to bottom.
RW_DOMAINS = ["Information and Ideas", "Craft and Structure",
              "Expression of Ideas", "Standard English Conventions"]
MATH_DOMAINS = ["Algebra", "Advanced Math",
                "Problem-Solving and Data Analysis", "Geometry and Trigonometry"]


@dataclass
class Domain:
    name: str
    section: str  # "Reading and Writing" or "Math"
    weight_pct: float
    question_count: str  # e.g. "13-15 questions"
    perf_low: int
    perf_high: int


@dataclass
class ScoreReport:
    student_name: str
    grade: str
    test_administration: str
    tested_on: str
    total_score: int
    rw_score: int
    math_score: int
    rw_percentile: str
    math_percentile: str
    domains: list


def _pdftotext(pdf_path: str) -> str:
    result = subprocess.run(
        ["pdftotext", pdf_path, "-"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def _search(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def _column_text(page, x_min: float, x_max: float, top_min: float, top_max: float) -> str:
    """Reconstruct reading-order text for words within an x/y bounding box."""
    lines = defaultdict(list)
    for w in page.extract_words():
        if top_min <= w["top"] <= top_max and x_min <= w["x0"] < x_max:
            lines[round(w["top"])].append(w["text"])
    return "\n".join(" ".join(lines[t]) for t in sorted(lines))


def _parse_domains(column_text: str, domain_names: list, section: str) -> list:
    domains = []
    for name in domain_names:
        pattern = (
            re.escape(name)
            + r"\s*\n\(([\d.]+)% of (?:test )?section, ([\d\-]+ questions)\)"
            + r"\s*\n?Performance:\s*(\d+)-(\d+)"
        )
        match = re.search(pattern, column_text)
        if match:
            weight_pct, question_count, perf_low, perf_high = match.groups()
            domains.append(Domain(
                name=name,
                section=section,
                weight_pct=float(weight_pct),
                question_count=question_count,
                perf_low=int(perf_low),
                perf_high=int(perf_high),
            ))
    return domains


def extract_report(pdf_path: str) -> ScoreReport:
    flat_text = _pdftotext(pdf_path)

    student_name = _search(r"Name:\s*(.+)", flat_text)
    grade = _search(r"Grade:\s*(\S+)", flat_text)
    test_administration = _search(r"Test administration:\s*(.+)", flat_text)
    tested_on = _search(r"Tested on:\s*(.+)", flat_text)
    total_score = int(_search(r"TOTAL SCORE\s*\n*(\d{3,4})", flat_text))

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        # Domain block sits roughly between y=228 and y=400 on page 1 of
        # both the SAT and PSAT layouts; columns split at x=160 and x=270.
        rw_text = _column_text(page, x_min=160, x_max=270, top_min=228, top_max=400)
        # x_max=450 excludes the NMSC Selection Index sidebar box that
        # appears only on PSAT/NMSQT reports, to the right of the Math column.
        math_text = _column_text(page, x_min=270, x_max=450, top_min=228, top_max=400)

        # Section scores (total score per section + percentile) live in the
        # narrow left sidebar, e.g. "540 ... 58th*" then "550 ... 66th*".
        sidebar_text = _column_text(page, x_min=0, x_max=160, top_min=228, top_max=340)

    # Match each score/percentile pair on its own line to avoid accidentally
    # picking up numbers from the "Score Range: 510-570" lines further down.
    score_lines = re.findall(r"^(\d{3})(?:\s+2\s*0\s*0\s*[–-])?\s*$", sidebar_text, re.MULTILINE)
    percentile_lines = re.findall(r"^(\d+\w{2}\*)\s*$", sidebar_text, re.MULTILINE)
    rw_score, math_score = int(score_lines[0]), int(score_lines[1])
    rw_percentile, math_percentile = percentile_lines[0], percentile_lines[1]

    domains = (
        _parse_domains(rw_text, RW_DOMAINS, "Reading and Writing")
        + _parse_domains(math_text, MATH_DOMAINS, "Math")
    )

    return ScoreReport(
        student_name=student_name,
        grade=grade,
        test_administration=test_administration,
        tested_on=tested_on,
        total_score=total_score,
        rw_score=rw_score,
        math_score=math_score,
        rw_percentile=rw_percentile,
        math_percentile=math_percentile,
        domains=[asdict(d) for d in domains],
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract_report.py path/to/report.pdf")
        sys.exit(1)

    report = extract_report(sys.argv[1])
    print(json.dumps(asdict(report), indent=2))
