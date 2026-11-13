"""End-to-end tests for the command line (run.py).

These run the whole app, from reading the data sources to saving the Word
file, exactly as a person or a scheduler would. The APIs are faked.
"""

from datetime import date
from pathlib import Path

import pytest
import requests

import run
from reportgen.engine import source_override
from reportgen.reports import Period


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


@pytest.fixture(autouse=True)
def fake_apis(monkeypatch):
    """Answer both APIs with small fake data, so no test needs the internet."""

    def fake_get(url, **kwargs):
        if "nager" in url:
            return FakeResponse([])  # no public holidays
        return FakeResponse({"products": [{"id": 78, "title": "Laptop", "category": "laptops"}]})

    monkeypatch.setattr(requests, "get", fake_get)


@pytest.mark.parametrize("report, expected_file", [
    ("sales", "SalesSummary_2026-10.docx"),
    ("it-support", "ITSupportKPI_2026-10.docx"),
])
def test_cli_creates_each_report(report, expected_file, tmp_path, capsys):
    exit_code = run.main(["--report", report, "--month", "2026-10", "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / expected_file).exists()
    last_line = capsys.readouterr().out.strip().splitlines()[-1]
    assert last_line.endswith(expected_file)  # the path is printed for a scheduler


def test_cli_date_range(tmp_path):
    exit_code = run.main(["--report", "sales", "--from", "2026-10-01", "--to", "2026-10-15",
                          "--output-dir", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "SalesSummary_2026-10-01_to_2026-10-15.docx").exists()


def test_cli_returns_1_when_there_is_no_data(tmp_path):
    exit_code = run.main(["--report", "sales", "--month", "2025-01", "--output-dir", str(tmp_path)])

    assert exit_code == 1
    assert list(tmp_path.iterdir()) == []  # no half-made report


def test_cli_returns_1_for_a_missing_file(tmp_path):
    exit_code = run.main(["--report", "sales", "--month", "2026-10", "--source", "sales=nope.csv",
                          "--output-dir", str(tmp_path)])

    assert exit_code == 1


def test_cli_returns_1_for_an_unknown_source_name(tmp_path):
    exit_code = run.main(["--report", "sales", "--month", "2026-10", "--source", "weather=data/sales.csv",
                          "--output-dir", str(tmp_path)])

    assert exit_code == 1


@pytest.mark.parametrize("bad_arguments", [
    ["--report", "nope"],                                  # unknown report
    ["--report", "sales", "--month", "October"],           # bad month
    ["--report", "sales", "--from", "2026-10-01"],         # --from without --to
    [],                                                    # no --report
    ["--report", "sales", "--source", "sales"],            # --source without =FILE
])
def test_cli_exits_with_2_for_a_wrong_command(bad_arguments):
    with pytest.raises(SystemExit) as stop:
        run.main(bad_arguments)

    assert stop.value.code == 2


def test_list_shows_both_reports(capsys):
    assert run.main(["--list"]) == 0

    output = capsys.readouterr().out
    assert "sales: Sales Summary" in output
    assert "it-support: IT Support KPIs" in output


def test_last_month():
    assert run.last_month(date(2026, 11, 13)) == Period.month(2026, 10)
    assert run.last_month(date(2026, 1, 1)) == Period.month(2025, 12)


def test_source_override_works_out_the_kind():
    assert source_override("sales", "sales", "other.csv")["kind"] == "csv"
    assert source_override("sales", "targets", "other.pdf")["kind"] == "pdf"
    assert source_override("sales", "products", "https://example.com/api")["kind"] == "api"
    excel = source_override("it-support", "tickets", "other.xlsx")
    assert excel["sheet"] == "Tickets"  # the Excel sheet setting is kept
    assert Path(excel["path"]).is_absolute()
