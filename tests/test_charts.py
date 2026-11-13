"""Tests for the chart helpers."""

import pandas as pd
import pytest

from reportgen.charts import bar_chart, bar_with_target_chart
from reportgen.errors import ReportError

PNG_SIGNATURE = b"\x89PNG"


def test_bar_chart_creates_png(tmp_path):
    values = pd.Series({"VIC": 85000, "NSW": 83000, "QLD": 55000})

    path = bar_chart(values, "Sales by region", "sales.png", output_dir=tmp_path)

    assert path.exists()
    assert path.read_bytes()[:4] == PNG_SIGNATURE


def test_horizontal_bar_chart_creates_png(tmp_path):
    values = pd.Series({"Laptop with a long name": 12000, "Tablet": 5000})

    path = bar_chart(values, "Sales by product", "products.png", horizontal=True, output_dir=tmp_path)

    assert path.exists()


def test_bar_with_target_chart_creates_png(tmp_path):
    actual = pd.Series({"VIC": 85000, "NSW": 83000})
    target = pd.Series({"NSW": 80000, "VIC": 90000})  # different order on purpose

    path = bar_with_target_chart(actual, target, "Actual vs target", "target.png", output_dir=tmp_path)

    assert path.exists()


def test_empty_data_raises_error(tmp_path):
    with pytest.raises(ReportError, match="No data"):
        bar_chart(pd.Series(dtype=float), "Empty", "empty.png", output_dir=tmp_path)


def test_text_values_raise_error(tmp_path):
    with pytest.raises(ReportError, match="needs numbers"):
        bar_chart(pd.Series({"VIC": "a lot"}), "Text", "text.png", output_dir=tmp_path)
        
        


def test_target_chart_skips_missing_target(tmp_path):
    actual = pd.Series({"VIC": 85000, "NSW": 83000, "WA": 40000})
    target = pd.Series({"VIC": 90000, "NSW": 80000})  # no target for WA

    path = bar_with_target_chart(actual, target, "Missing target", "missing.png", output_dir=tmp_path)

    assert path.exists()