"""Tests for the Sales Summary report.

The REST API is replaced with a fake (monkeypatch), so the tests
do not need the internet and give the same result every time.
"""

import pandas as pd
import pytest
import requests

from reportgen.blocks import Chart, Heading, Note, Paragraph, Table
from reportgen.docx_writer import write_report
from reportgen.errors import ReportError
from reportgen.reports import REPORT_REGISTRY, Period
from reportgen.reports.base import money
from reportgen.reports.sales_summary import SalesSummaryReport

OCTOBER = Period.month(2026, 10)
FAKE_PRODUCTS = [
    {"id": product_id, "title": f"Test product {product_id}", "category": "test", "price": 1.0}
    for product_id in [78, 79, 80, 81, 82, 101, 102, 159, 160, 161]
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
    monkeypatch.setattr(requests, "get", lambda url, **kwargs: FakeResponse({"products": FAKE_PRODUCTS}))


@pytest.fixture
def api_down(monkeypatch):
    def fail(url, **kwargs):
        raise requests.ConnectionError()

    monkeypatch.setattr(requests, "get", fail)


def blocks_of(blocks, block_type):
    return [block for block in blocks if isinstance(block, block_type)]


def test_sales_report_is_registered():
    assert REPORT_REGISTRY["sales"] is SalesSummaryReport


def test_report_uses_all_three_sources(api_works):
    blocks = SalesSummaryReport(OCTOBER).build()

    assert blocks_of(blocks, Heading)[0].text == "Sales Summary - October 2026"
    region_table, product_table = blocks_of(blocks, Table)
    assert "Target" in region_table.data.columns                                # from the PDF
    assert product_table.data["Product"].iloc[0].startswith("Test product")     # from the API
    assert len(blocks_of(blocks, Chart)) == 2
    assert blocks_of(blocks, Note) == []                                        # nothing went wrong


def test_total_matches_the_csv(api_works):
    sales = pd.read_csv("data/sales.csv")
    expected_total = sales[sales["date"].str.startswith("2026-10")]["amount"].sum()

    blocks = SalesSummaryReport(OCTOBER).build()

    overview_text = blocks_of(blocks, Paragraph)[1].text
    assert money(expected_total) in overview_text


def test_region_table_has_a_row_per_region(api_works):
    blocks = SalesSummaryReport(OCTOBER).build()

    region_table = blocks_of(blocks, Table)[0]
    assert sorted(region_table.data["Region"]) == ["NSW", "QLD", "SA", "VIC", "WA"]


def test_api_down_still_makes_report_with_ids_and_note(api_down):
    blocks = SalesSummaryReport(OCTOBER).build()

    product_table = blocks_of(blocks, Table)[1]
    assert product_table.data["Product"].iloc[0].startswith("Product ")
    notes = blocks_of(blocks, Note)
    assert len(notes) == 1
    assert "products" in notes[0].text


def test_missing_targets_file_still_makes_report(api_works):
    report = SalesSummaryReport(OCTOBER, sources={"targets": {"kind": "pdf", "path": "data/nope.pdf"}})

    blocks = report.build()

    region_table = blocks_of(blocks, Table)[0]
    assert "Target" not in region_table.data.columns
    assert len(blocks_of(blocks, Note)) == 1


def test_period_without_sales_raises_error(api_works):
    with pytest.raises(ReportError, match="No sales data"):
        SalesSummaryReport(Period.month(2025, 1)).build()


def test_full_sales_report_to_word(api_works, tmp_path):
    report = SalesSummaryReport(OCTOBER)

    output = write_report(report.build(), tmp_path / report.output_filename())

    assert output.name == "SalesSummary_2026-10.docx"
    assert output.exists()