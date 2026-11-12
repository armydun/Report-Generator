"""Data sources that read local files: CSV and Excel."""

import logging
from pathlib import Path

import pandas as pd

from reportgen.errors import DataSourceError
from reportgen.sources.base import DataSource, register_source

logger = logging.getLogger(__name__)


class FileSource(DataSource):
    """Shared checks for every source that reads a local file."""

    allowed_extensions: tuple[str, ...] = ()

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def check_file(self) -> None:
        """Make sure the file exists, has the right extension and is not empty."""
        if not self.path.is_file():
            raise DataSourceError(f"File not found: {self.path}")
        if self.path.suffix.lower() not in self.allowed_extensions:
            expected = ", ".join(self.allowed_extensions)
            raise DataSourceError(
                f"Wrong file type for '{self.kind}' source: {self.path.name} (expected {expected})"
            )
        if self.path.stat().st_size == 0:
            raise DataSourceError(f"File is empty: {self.path}")

    def check_rows(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reject a table with no data rows, otherwise log the row count."""
        if df.empty:
            raise DataSourceError(f"No data rows in {self.path.name}")
        logger.info("Loaded %d rows from %s", len(df), self.path.name)
        return df


@register_source("csv")
class CsvSource(FileSource):
    """Reads a .csv file."""

    allowed_extensions = (".csv",)

    def load(self) -> pd.DataFrame:
        self.check_file()
        try:
            df = pd.read_csv(self.path)
        except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as error:
            raise DataSourceError(f"Could not read CSV file {self.path.name}: {error}") from error
        return self.check_rows(df)


@register_source("excel")
class ExcelSource(FileSource):
    """Reads one sheet of an .xlsx file."""

    allowed_extensions = (".xlsx",)

    def __init__(self, path: str | Path, sheet: str | int = 0):
        super().__init__(path)
        self.sheet = sheet

    def load(self) -> pd.DataFrame:
        self.check_file()
        try:
            df = pd.read_excel(self.path, sheet_name=self.sheet)
        except Exception as error:  # broken file, not really Excel, or sheet not found
            raise DataSourceError(
                f"Could not read Excel file {self.path.name} (sheet '{self.sheet}'): {error}"
            ) from error
        return self.check_rows(df)