"""Tests for the IT Support KPI report.

The public holidays API is replaced with a fake (monkeypatch).
"""

from datetime import date

import pandas as pd
import pytest
import requests

from reportgen.blocks import Heading, Note, Paragraph, Table
from reportgen.docx_writer import write_report
from reportgen.errors import ReportError
from reportgen.reports import REPORT_REGISTRY, Period
from reportgen.reports.it_support_kpi import ITSupportKPIReport, working_days

OCTOBER = Period.month(2026, 10)
FAKE_HOLIDAYS = [
    {"date": "2026-10-05", "localName": "Labour Day", "global": False, "counties": ["AU-NSW"]},  # not VIC
    {"date": "2026-10-20", "localName": "Test Day", "global": True, "counties": None},          # everywhere
]


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


@pytest.fixture
def api_works(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, **kwargs: FakeResponse(FAKE_HOLIDAYS))


@pytest.fixture
def api_down(monkeypatch):
    def fail(url, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(requests, "get", fail)


def blocks_of(blocks, block_type):
    return [block for block in blocks if isinstance(block, block_type)]


def test_it_support_report_is_registered():
    assert REPORT_REGISTRY["it-support"] is ITSupportKPIReport


def test_working_days_skip_weekends_and_holidays():
    holidays = pd.DataFrame({"date": ["2026-10-20"]})  # a Tuesday

    assert working_days(OCTOBER.start, OCTOBER.end, None) == 22
    assert working_days(OCTOBER.start, OCTOBER.end, holidays) == 21
    assert working_days(date(2026, 10, 3), date(2026, 10, 4), None) == 0  # Saturday and Sunday


def test_ticket_count_matches_the_excel_file(api_works):
    tickets = pd.read_excel("data/tickets.xlsx", sheet_name="Tickets")
    expected = (pd.to_datetime(tickets["opened"]).dt.strftime("%Y-%m") == "2026-10").sum()

    blocks = ITSupportKPIReport(OCTOBER).build()

    overview_text = blocks_of(blocks, Paragraph)[1].text
    assert overview_text.startswith(f"{expected} tickets were opened")


def test_only_holidays_for_our_state_are_counted(api_works):
    blocks = ITSupportKPIReport(OCTOBER).build()

    overview_text = blocks_of(blocks, Paragraph)[1].text
    assert "(21 working days)" in overview_text  # Test Day counts, NSW Labour Day does not


def test_report_has_priority_client_and_backup_tables(api_works):
    blocks = ITSupportKPIReport(OCTOBER).build()

    headings = [block.text for block in blocks_of(blocks, Heading)]
    assert "Tickets by priority" in headings
    assert "Backups" in headings
    priority_table = blocks_of(blocks, Table)[0]
    assert list(priority_table.data["Priority"]) == ["P1", "P2", "P3", "P4"]


def test_holiday_api_down_still_makes_report(api_down):
    blocks = ITSupportKPIReport(OCTOBER).build()

    notes = blocks_of(blocks, Note)
    assert len(notes) == 1
    assert "holidays" in notes[0].text
    assert "(22 working days)" in blocks_of(blocks, Paragraph)[1].text  # weekends only


def test_missing_backup_file_still_makes_report(api_works):
    report = ITSupportKPIReport(OCTOBER, sources={"backups": {"kind": "pdf", "path": "data/nope.pdf"}})

    blocks = report.build()

    assert "Backups" not in [block.text for block in blocks_of(blocks, Heading)]
    assert len(blocks_of(blocks, Note)) == 1


def test_period_without_tickets_raises_error(api_works):
    with pytest.raises(ReportError, match="No tickets"):
        ITSupportKPIReport(Period.month(2025, 1)).build()


def test_full_it_support_report_to_word(api_works, tmp_path):
    report = ITSupportKPIReport(OCTOBER)

    output = write_report(report.build(), tmp_path / report.output_filename())

    assert output.name == "ITSupportKPI_2026-10.docx"
    assert output.exists()