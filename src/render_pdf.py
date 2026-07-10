"""
Renders a generated lesson plan (markdown text) as a clean, printable PDF.

The lesson plan comes back from the model as markdown (### headers,
**bold**, numbered questions, "- " bullet lines). This does a simple,
line-based markdown -> ReportLab conversion, good enough for a tutor
handout without pulling in a full markdown parser dependency.

Usage:
    python render_pdf.py output/lesson_plan.md output/lesson_plan.pdf
"""

import re
import sys

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem,
)


def _inline_markdown_to_html(text: str) -> str:
    """Converts **bold** markdown to ReportLab's inline <b> tags, and
    cleans up LaTeX-style math notation the model sometimes emits
    (\\(...\\), \\frac{a}{b}) into plain readable text, since ReportLab
    doesn't render LaTeX."""
    text = re.sub(r"\\\((.+?)\\\)", r"\1", text)  # \(x\) -> x
    text = re.sub(r"\\frac\{(.+?)\}\{(.+?)\}", r"(\1)/(\2)", text)  # \frac{a}{b} -> (a)/(b)
    text = text.replace("\\", "")  # drop any remaining stray backslashes
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="PlanTitle", parent=styles["Title"], spaceAfter=18,
    ))
    styles.add(ParagraphStyle(
        name="PlanH2", parent=styles["Heading2"],
        spaceBefore=16, spaceAfter=8, textColor="#1a1a2e",
    ))
    styles.add(ParagraphStyle(
        name="PlanH3", parent=styles["Heading3"],
        spaceBefore=14, spaceAfter=6, textColor="#16213e",
    ))
    styles.add(ParagraphStyle(
        name="PlanBody", parent=styles["Normal"],
        fontSize=10.5, leading=15, spaceAfter=6, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="PlanAnswer", parent=styles["Normal"],
        fontSize=10.5, leading=15, spaceAfter=10,
        textColor="#0f5132", leftIndent=14,
    ))
    styles.add(ParagraphStyle(
        name="PlanWarning", parent=styles["Normal"],
        fontSize=10.5, leading=15, spaceAfter=10,
        textColor="#8a4b00", leftIndent=14,
    ))
    return styles


def markdown_to_flowables(markdown_text: str, styles) -> list:
    flowables = []
    bullet_buffer = []

    def flush_bullets():
        if bullet_buffer:
            flowables.append(ListFlowable(
                [ListItem(Paragraph(_inline_markdown_to_html(b), styles["PlanBody"]))
                 for b in bullet_buffer],
                bulletType="bullet", start="circle", leftIndent=18,
            ))
            bullet_buffer.clear()

    for raw_line in markdown_text.split("\n"):
        line = raw_line.rstrip()

        if not line.strip():
            flush_bullets()
            flowables.append(Spacer(1, 6))
            continue

        if line.startswith("### "):
            flush_bullets()
            flowables.append(Paragraph(_inline_markdown_to_html(line[4:]), styles["PlanH3"]))
        elif line.startswith("## "):
            flush_bullets()
            flowables.append(Paragraph(_inline_markdown_to_html(line[3:]), styles["PlanH2"]))
        elif line.startswith("# "):
            flush_bullets()
            flowables.append(Paragraph(_inline_markdown_to_html(line[2:]), styles["PlanTitle"]))
        elif line.strip().startswith("- ") or line.strip().startswith("* "):
            bullet_buffer.append(line.strip()[2:])
        elif line.strip().lower().startswith("answer:"):
            flush_bullets()
            flowables.append(Paragraph(_inline_markdown_to_html(line.strip()), styles["PlanAnswer"]))
        elif line.strip().startswith("⚠️"):
            flush_bullets()
            flowables.append(Paragraph(_inline_markdown_to_html(line.strip()), styles["PlanWarning"]))
        else:
            flush_bullets()
            flowables.append(Paragraph(_inline_markdown_to_html(line.strip()), styles["PlanBody"]))

    flush_bullets()
    return flowables


def render_pdf(markdown_path: str, pdf_path: str):
    with open(markdown_path) as f:
        markdown_text = f.read()

    styles = build_styles()
    doc = SimpleDocTemplate(
        pdf_path, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
    )
    story = markdown_to_flowables(markdown_text, styles)
    doc.build(story)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python render_pdf.py input.md output.pdf")
        sys.exit(1)
    render_pdf(sys.argv[1], sys.argv[2])
    print(f"Saved PDF to {sys.argv[2]}")
