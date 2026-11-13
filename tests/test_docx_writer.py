"""Tests for the Word writer."""

import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw charts without opening a window
import matplotlib.pyplot as plt
import pandas as pd
import pytest
from docx import Document

from reportgen.blocks import Bullets, Chart, Heading, Note, Paragraph, Table
from reportgen.docx_writer import DEFAULT_TEMPLATE, write_report
from reportgen.errors import TemplateError


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_sample_blocks(tmp_path: Path) -> list:
    image = tmp_path / "chart.png"
    fig, ax = plt.subplots()
    ax.bar(["A", "B"], [3, 5])
    fig.savefig(image)
    plt.close(fig)

    table_data = pd.DataFrame({"Region": ["VIC", "NSW", "QLD"], "Sales": ["$85,000", "$83,000", "$55,000"]})
    return [
        Heading("Writer Test", level=0),
        Paragraph("A normal paragraph."),
        Bullets(["First point", "Second point"]),
        Note("Something to notice."),
        Table(table_data, caption="Sales by region"),
        Chart(image, caption="A small chart"),
    ]


def test_writer_creates_document_with_all_blocks(tmp_path):
    output = write_report(make_sample_blocks(tmp_path), tmp_path / "report.docx")

    document = Document(str(output))
    texts = [p.text for p in document.paragraphs]
    assert "Writer Test" in texts
    assert "A normal paragraph." in texts
    assert len(document.tables) == 1
    assert len(document.tables[0].rows) == 4            # 1 header row + 3 data rows
    assert len(document.inline_shapes) == 1             # the chart picture


def test_writer_keeps_template_header_and_footer(tmp_path):
    output = write_report([Paragraph("Hello")], tmp_path / "report.docx")

    footer_text = Document(str(output)).sections[0].footer.paragraphs[0].text
    assert "TechInnovate" in footer_text


def test_writer_never_changes_the_template(tmp_path):
    before = file_hash(DEFAULT_TEMPLATE)
    write_report(make_sample_blocks(tmp_path), tmp_path / "report.docx")

    assert file_hash(DEFAULT_TEMPLATE) == before


def test_writer_refuses_to_overwrite_template():
    with pytest.raises(TemplateError, match="cannot be the template"):
        write_report([Paragraph("x")], DEFAULT_TEMPLATE)


def test_missing_template_raises_error(tmp_path):
    with pytest.raises(TemplateError, match="Template not found"):
        write_report([Paragraph("x")], tmp_path / "out.docx", template_path=tmp_path / "nope.docx")


def test_broken_template_raises_error(tmp_path):
    broken = tmp_path / "broken.docx"
    broken.write_text("not a Word file")

    with pytest.raises(TemplateError, match="Could not open template"):
        write_report([Paragraph("x")], tmp_path / "out.docx", template_path=broken)