"""Data source that reads records from a REST API that returns JSON."""

import logging

import pandas as pd
import requests

from reportgen.errors import DataSourceError
from reportgen.sources.base import DataSource, register_source

logger = logging.getLogger(__name__)


@register_source("api")
class RestApiSource(DataSource):
    """Calls a REST API (HTTP GET) and turns the JSON records into a table.

    records_path says where the list of records is inside the JSON answer.
    Example: for {"products": [...], "total": 194} use records_path="products".
    Use dots for deeper lists, e.g. "data.items".
    """

    def __init__(
        self,
        url: str,
        params: dict | None = None,
        records_path: str = "",
        timeout: float = 10,
        headers: dict | None = None,
    ):
        self.url = url
        self.params = params or {}
        self.records_path = records_path
        self.timeout = timeout
        self.headers = headers or {}

    def load(self) -> pd.DataFrame:
        payload = self._get_json()
        records = self._find_records(payload)
        if not records:
            raise DataSourceError(f"API returned no records: {self.url}")

        df = pd.DataFrame(records)
        logger.info("Loaded %d records from %s", len(df), self.url)
        return df

    def _get_json(self):
        """Send the request and return the decoded JSON."""
        try:
            response = requests.get(
                self.url, params=self.params, headers=self.headers, timeout=self.timeout
            )
            response.raise_for_status()  # turns 4xx / 5xx answers into an HTTPError
        except requests.Timeout as error:
            raise DataSourceError(
                f"API did not answer within {self.timeout} seconds: {self.url}"
            ) from error
        except requests.ConnectionError as error:
            raise DataSourceError(
                f"Could not connect to the API (check the internet connection): {self.url}"
            ) from error
        except requests.HTTPError as error:
            raise DataSourceError(
                f"API returned HTTP {error.response.status_code}: {self.url}"
            ) from error
        except requests.RequestException as error:  # any other problem, e.g. a bad URL
            raise DataSourceError(f"API request failed: {error}") from error

        try:
            return response.json()
        except ValueError as error:
            raise DataSourceError(f"API response is not valid JSON: {self.url}") from error

    def _find_records(self, payload) -> list:
        """Follow records_path (e.g. "data.items") down to the list of records."""
        data = payload
        if self.records_path:
            for key in self.records_path.split("."):
                if not isinstance(data, dict) or key not in data:
                    raise DataSourceError(f"Key '{key}' not found in the API response from {self.url}")
                data = data[key]

        if not isinstance(data, list):
            where = self.records_path or "the top level"
            raise DataSourceError(
                f"Expected a list of records at {where}, but got {type(data).__name__}"
            )
        return data