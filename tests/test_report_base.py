"""Tests for the report frame: Period, Report.load_source and helpers."""

from datetime import date

import pandas as pd
import pytest

from reportgen.errors import DataSourceError, ReportError
from reportgen.reports.base import Period, Report, money, percent, require_columns


class DemoReport(Report):
    """A tiny report used only in these tests (not registered)."""

    key = "demo"
    file_prefix = "Demo"
    default_sources = {
        "sales": {"kind": "csv", "path": "data/sales.csv"},
        "missing": {"kind": "csv", "path": "data/does_not_exist.csv"},
    }

    def build(self):
        return []


OCTOBER = Period.month(2026, 10)


# ---------- Period ----------

def test_month_period_has_first_and_last_day():
    assert OCTOBER.start == date(2026, 10, 1)
    assert OCTOBER.end == date(2026, 10, 31)


def test_month_label_and_file_tag():
    assert OCTOBER.label == "October 2026"
    assert OCTOBER.file_tag == "2026-10"


def test_custom_range_label_and_file_tag():
    period = Period(date(2026, 10, 1), date(2026, 10, 15))

    assert period.label == "01 Oct 2026 to 15 Oct 2026"
    assert period.file_tag == "2026-10-01_to_2026-10-15"


def test_previous_of_a_month_is_the_month_before():
    assert OCTOBER.previous() == Period.month(2026, 9)


def test_previous_of_january_is_december_last_year():
    assert Period.month(2026, 1).previous() == Period.month(2025, 12)


def test_start_after_end_raises_error():
    with pytest.raises(ReportError, match="after end date"):
        Period(date(2026, 10, 31), date(2026, 10, 1))


def test_filter_keeps_only_rows_in_period():
    df = pd.DataFrame({"when": ["2026-09-30 23:59", "2026-10-01 00:00", "2026-10-31 18:00", "2026-11-01"]})

    result = OCTOBER.filter(df, "when")

    assert list(result["when"]) == ["2026-10-01 00:00", "2026-10-31 18:00"]


def test_months_lists_every_month_touched():
    assert Period(date(2026, 8, 15), date(2026, 10, 2)).months() == ["2026-08", "2026-09", "2026-10"]


# ---------- Report.load_source ----------

def test_output_filename_uses_prefix_and_period():
    assert DemoReport(OCTOBER).output_filename() == "Demo_2026-10.docx"


def test_load_source_reads_data():
    df = DemoReport(OCTOBER).load_source("sales")

    assert len(df) > 0


def test_required_source_failure_stops_the_report():
    with pytest.raises(DataSourceError, match="File not found"):
        DemoReport(OCTOBER).load_source("missing", required=True)


def test_optional_source_failure_adds_a_note():
    report = DemoReport(OCTOBER)

    result = report.load_source("missing", required=False)

    assert result is None
    assert len(report.notes) == 1
    assert "missing" in report.notes[0]


def test_unknown_source_name_raises_error():
    with pytest.raises(ReportError, match="no data source called"):
        DemoReport(OCTOBER).load_source("nope")


def test_sources_can_be_overridden():
    report = DemoReport(OCTOBER, sources={"sales": {"kind": "csv", "path": "data/other.csv"}})

    assert report.sources["sales"]["path"] == "data/other.csv"
    assert DemoReport.default_sources["sales"]["path"] == "data/sales.csv"  # default unchanged


# ---------- helpers ----------

def test_require_columns_reports_missing_ones():
    with pytest.raises(ReportError, match="missing column"):
        require_columns(pd.DataFrame({"a": [1]}), ["a", "b"], "sales")


def test_money_and_percent_format():
    assert money(12345.6) == "$12,346"
    assert percent(0.1234) == "12.3%"