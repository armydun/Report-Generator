"""Tests for the PDF export.

The real converters (Word, LibreOffice) are replaced with fakes, so the
tests behave the same on every computer.
"""

import pytest
import requests

import run
from reportgen import pdf_export
from reportgen.errors import ReportError
from reportgen.pdf_export import export_pdf


def works(docx_path, pdf_path):
    pdf_path.write_bytes(b"%PDF-1.7 fake")


def fails(docx_path, pdf_path):
    raise RuntimeError("not installed")


@pytest.fixture
def docx_file(tmp_path):
    path = tmp_path / "Report_2026-10.docx"
    path.write_bytes(b"fake docx")
    return path


def test_word_is_tried_first(monkeypatch, docx_file):
    monkeypatch.setattr(pdf_export, "convert_with_word", works)
    monkeypatch.setattr(pdf_export, "convert_with_libreoffice", fails)

    pdf = export_pdf(docx_file)

    assert pdf.name == "Report_2026-10.pdf"
    assert pdf.exists()


def test_libreoffice_is_used_when_word_fails(monkeypatch, docx_file):
    monkeypatch.setattr(pdf_export, "convert_with_word", fails)
    monkeypatch.setattr(pdf_export, "convert_with_libreoffice", works)

    assert export_pdf(docx_file).exists()


def test_clear_error_when_no_converter_works(monkeypatch, docx_file):
    monkeypatch.setattr(pdf_export, "convert_with_word", fails)
    monkeypatch.setattr(pdf_export, "convert_with_libreoffice", fails)

    with pytest.raises(ReportError, match="Install Microsoft Word or LibreOffice"):
        export_pdf(docx_file)


def test_old_pdf_is_never_returned(monkeypatch, docx_file):
    docx_file.with_suffix(".pdf").write_bytes(b"old pdf from last month")
    monkeypatch.setattr(pdf_export, "convert_with_word", fails)
    monkeypatch.setattr(pdf_export, "convert_with_libreoffice", fails)

    with pytest.raises(ReportError):
        export_pdf(docx_file)
    assert not docx_file.with_suffix(".pdf").exists()


def no_internet(url, **kwargs):
    raise requests.ConnectionError()


def test_cli_pdf_option_prints_both_files(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(pdf_export, "convert_with_word", works)
    monkeypatch.setattr(requests, "get", no_internet)  # the report still works without the API

    exit_code = run.main(["--report", "sales", "--month", "2026-10", "--pdf", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    printed = capsys.readouterr().out.strip().splitlines()
    assert printed[-2].endswith("SalesSummary_2026-10.docx")
    assert printed[-1].endswith("SalesSummary_2026-10.pdf")
