"""Tests for the PDF data source."""

from pathlib import Path

import pandas as pd
import pytest
from reportlab.pdfgen import canvas

from reportgen.errors import DataSourceError
from reportgen.sources import SOURCE_REGISTRY, create_source

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_pdf_is_registered():
    assert "pdf" in SOURCE_REGISTRY


def test_pdf_reads_sales_targets_table():
    df = create_source("pdf", path=DATA_DIR / "sales_targets.pdf").load()

    assert list(df.columns) == ["Month", "Region", "Target"]
    assert len(df) == 15
    assert df["Month"].iloc[0] == "2026-08"                  # text stays text
    assert pd.api.types.is_numeric_dtype(df["Target"])       # "$67,000" became a number


def test_pdf_backup_numbers_add_up():
    df = create_source("pdf", path=DATA_DIR / "backup_status.pdf").load()

    assert len(df) == 18
    assert (df["Successful"] + df["Failed"] == df["Jobs"]).all()


def test_pdf_text_contains_title():
    source = create_source("pdf", path=DATA_DIR / "sales_targets.pdf")

    assert "Sales Targets by Region" in source.text()


def test_pdf_table_index_out_of_range_raises_error():
    with pytest.raises(DataSourceError, match="does not exist"):
        create_source("pdf", path=DATA_DIR / "sales_targets.pdf", table_index=5).load()


def test_pdf_without_table_raises_error(tmp_path):
    pdf_path = tmp_path / "no_table.pdf"
    page = canvas.Canvas(str(pdf_path))
    page.drawString(100, 750, "Just a sentence, no table here.")
    page.save()

    with pytest.raises(DataSourceError, match="No tables found"):
        create_source("pdf", path=pdf_path).load()


def test_pdf_broken_file_raises_error(tmp_path):
    fake_pdf = tmp_path / "broken.pdf"
    fake_pdf.write_text("this is not really a PDF")

    with pytest.raises(DataSourceError, match="Could not read PDF file"):
        create_source("pdf", path=fake_pdf).load()