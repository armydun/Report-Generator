"""Tests for the CSV and Excel data sources."""

from pathlib import Path

import pandas as pd
import pytest

from reportgen.errors import DataSourceError
from reportgen.sources import SOURCE_REGISTRY, create_source

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------- registry ----------

def test_csv_and_excel_are_registered():
    assert "csv" in SOURCE_REGISTRY
    assert "excel" in SOURCE_REGISTRY


def test_unknown_source_name_raises_error():
    with pytest.raises(DataSourceError, match="Unknown data source"):
        create_source("xml")


def test_wrong_option_name_raises_error():
    with pytest.raises(DataSourceError, match="Wrong options"):
        create_source("csv", pathh="data/sales.csv")


# ---------- CSV: success ----------

def test_csv_loads_sample_sales():
    df = create_source("csv", path=DATA_DIR / "sales.csv").load()

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    for column in ["date", "order_id", "region", "product_id", "quantity", "unit_price", "amount"]:
        assert column in df.columns


# ---------- CSV: errors ----------

def test_csv_missing_file_raises_error():
    with pytest.raises(DataSourceError, match="File not found"):
        create_source("csv", path="data/does_not_exist.csv").load()


def test_csv_wrong_extension_raises_error(tmp_path):
    text_file = tmp_path / "notes.txt"
    text_file.write_text("hello")

    with pytest.raises(DataSourceError, match="Wrong file type"):
        create_source("csv", path=text_file).load()


def test_csv_empty_file_raises_error(tmp_path):
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")

    with pytest.raises(DataSourceError, match="File is empty"):
        create_source("csv", path=empty_file).load()


def test_csv_header_only_raises_error(tmp_path):
    header_only = tmp_path / "header_only.csv"
    header_only.write_text("date,region,amount\n")

    with pytest.raises(DataSourceError, match="No data rows"):
        create_source("csv", path=header_only).load()


# ---------- Excel ----------

def test_excel_loads_sample_tickets():
    df = create_source("excel", path=DATA_DIR / "tickets.xlsx", sheet="Tickets").load()

    assert len(df) > 0
    assert {"ticket_id", "client", "priority", "opened", "resolved", "sla_hours"} <= set(df.columns)


def test_excel_wrong_sheet_raises_error():
    with pytest.raises(DataSourceError, match="Could not read Excel file"):
        create_source("excel", path=DATA_DIR / "tickets.xlsx", sheet="NoSuchSheet").load()


def test_excel_broken_file_raises_error(tmp_path):
    fake_excel = tmp_path / "broken.xlsx"
    fake_excel.write_text("this is not really an Excel file")

    with pytest.raises(DataSourceError, match="Could not read Excel file"):
        create_source("excel", path=fake_excel).load()