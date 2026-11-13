"""Tests for the REST API data source.

The tests never use the real internet. Instead, requests.get is replaced
with a fake function (monkeypatch), so we can also test failures such as
timeouts and server errors that are hard to cause on purpose.
"""

import pytest
import requests

from reportgen.errors import DataSourceError
from reportgen.sources import SOURCE_REGISTRY, create_source

API_URL = "https://example.com/api/products"


class FakeResponse:
    """Pretends to be a requests.Response."""

    def __init__(self, json_data=None, status_code=200, bad_json=False):
        self.json_data = json_data
        self.status_code = status_code
        self.bad_json = bad_json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def json(self):
        if self.bad_json:
            raise ValueError("not JSON")
        return self.json_data


def use_fake_get(monkeypatch, response=None, error=None):
    """Replace requests.get so it returns `response` or raises `error`."""

    def fake_get(url, **kwargs):
        if error is not None:
            raise error
        return response

    monkeypatch.setattr(requests, "get", fake_get)


# ---------- success ----------

def test_api_is_registered():
    assert "api" in SOURCE_REGISTRY


def test_api_loads_records(monkeypatch):
    products = [
        {"id": 78, "title": "Laptop A", "price": 1999.99},
        {"id": 101, "title": "Headphones B", "price": 549.99},
    ]
    use_fake_get(monkeypatch, FakeResponse({"products": products, "total": 2}))

    df = create_source("api", url=API_URL, records_path="products").load()

    assert len(df) == 2
    assert list(df.columns) == ["id", "title", "price"]
    assert df.loc[df["id"] == 78, "title"].iloc[0] == "Laptop A"


def test_api_follows_nested_path(monkeypatch):
    use_fake_get(monkeypatch, FakeResponse({"data": {"items": [{"id": 1}]}}))

    df = create_source("api", url=API_URL, records_path="data.items").load()

    assert len(df) == 1


# ---------- errors ----------

def test_api_timeout_raises_error(monkeypatch):
    use_fake_get(monkeypatch, error=requests.Timeout())

    with pytest.raises(DataSourceError, match="did not answer"):
        create_source("api", url=API_URL).load()


def test_api_connection_failure_raises_error(monkeypatch):
    use_fake_get(monkeypatch, error=requests.ConnectionError())

    with pytest.raises(DataSourceError, match="Could not connect"):
        create_source("api", url=API_URL).load()


def test_api_server_error_raises_error(monkeypatch):
    use_fake_get(monkeypatch, FakeResponse(status_code=500))

    with pytest.raises(DataSourceError, match="HTTP 500"):
        create_source("api", url=API_URL).load()


def test_api_invalid_json_raises_error(monkeypatch):
    use_fake_get(monkeypatch, FakeResponse(bad_json=True))

    with pytest.raises(DataSourceError, match="not valid JSON"):
        create_source("api", url=API_URL).load()


def test_api_missing_key_raises_error(monkeypatch):
    use_fake_get(monkeypatch, FakeResponse({"items": []}))

    with pytest.raises(DataSourceError, match="Key 'products' not found"):
        create_source("api", url=API_URL, records_path="products").load()


def test_api_empty_list_raises_error(monkeypatch):
    use_fake_get(monkeypatch, FakeResponse({"products": []}))

    with pytest.raises(DataSourceError, match="no records"):
        create_source("api", url=API_URL, records_path="products").load()


def test_api_not_a_list_raises_error(monkeypatch):
    use_fake_get(monkeypatch, FakeResponse({"products": "oops"}))

    with pytest.raises(DataSourceError, match="Expected a list"):
        create_source("api", url=API_URL, records_path="products").load()