"""Render the restricted Markdown used for resumes/cover letters into an ATS-friendly .docx.

Supported: '# Name' (title), '## Section', '### Role line', '- bullet', plain paragraphs,
**bold** and *italic* inline. Single column, standard font, no tables or text boxes,
so applicant tracking systems can parse it.
"""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

FONT = "Calibri"
_INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*)")


def _runs(par, text: str, size: float):
    for chunk in _INLINE.split(text):
        if not chunk:
            continue
        bold = chunk.startswith("**")
        ital = not bold and chunk.startswith("*")
        run = par.add_run(chunk.strip("*") if (bold or ital) else chunk)
        run.bold, run.italic, run.font.size, run.font.name = bold, ital, Pt(size), FONT


def md_to_docx(md_path: Path) -> Path:
    doc = Document()
    for s in doc.sections:
        s.top_margin = s.bottom_margin = Inches(0.6)
        s.left_margin = s.right_margin = Inches(0.7)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = FONT, Pt(10.5)
    normal.paragraph_format.space_after = Pt(2)

    for line in md_path.read_text(encoding="utf-8").splitlines():
        line = line.rstrip()
        if not line or line.startswith("<!--"):
            continue
        if line.startswith("# "):
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _runs(p, f"**{line[2:]}**", 16)
        elif line.startswith("## "):
            p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(8)
            _runs(p, f"**{line[3:].upper()}**", 11)
            p.paragraph_format.keep_with_next = True
        elif line.startswith("### "):
            p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(4)
            _runs(p, line[4:] if "**" in line else f"**{line[4:]}**", 10.5)
            p.paragraph_format.keep_with_next = True
        elif line.lstrip().startswith(("- ", "* ")):
            p = doc.add_paragraph(style="List Bullet")
            _runs(p, line.lstrip()[2:], 10.5)
        else:
            p = doc.add_paragraph()
            if line.startswith("> "):  # contact line under the name
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                line = line[2:]
            _runs(p, line, 10.5)
    out = md_path.with_suffix(".docx")
    doc.save(out)
    return out
