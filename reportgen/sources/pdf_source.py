"""Data source that reads a table (and plain text) from a PDF file."""

import logging
from pathlib import Path

import pandas as pd
import pdfplumber

from reportgen.errors import DataSourceError
from reportgen.sources.base import register_source
from reportgen.sources.file_source import FileSource

logger = logging.getLogger(__name__)


def to_number_if_possible(column: pd.Series) -> pd.Series:
    """Turn text like '$85,000' into the number 85000.

    A column is only converted when every value in it is a number,
    so text columns such as 'Region' or '2026-08' stay as text.
    """
    cleaned = column.astype(str).str.replace(r"[$,\s]", "", regex=True)
    numbers = pd.to_numeric(cleaned, errors="coerce")
    if numbers.notna().all():
        return numbers
    return column


@register_source("pdf")
class PdfTableSource(FileSource):
    """Reads one table from a PDF. The first row of the table is the header."""

    allowed_extensions = (".pdf",)

    def __init__(self, path: str | Path, table_index: int = 0):
        super().__init__(path)
        self.table_index = table_index

    def load(self) -> pd.DataFrame:
        self.check_file()
        tables = self._extract_tables()

        if self.table_index >= len(tables):
            raise DataSourceError(
                f"{self.path.name} has {len(tables)} table(s), "
                f"so table_index {self.table_index} does not exist"
            )

        rows = tables[self.table_index]
        header = [str(cell).strip() for cell in rows[0]]
        data = [row for row in rows[1:] if any(cell not in (None, "") for cell in row)]

        df = pd.DataFrame(data, columns=header)
        df = df.apply(to_number_if_possible)
        return self.check_rows(df)

    def text(self) -> str:
        """Return all the text in the PDF (titles, paragraphs and table text)."""
        self.check_file()
        try:
            with pdfplumber.open(self.path) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as error:
            raise DataSourceError(f"Could not read PDF file {self.path.name}: {error}") from error

    def _extract_tables(self) -> list[list[list]]:
        """Collect every table on every page, in order."""
        try:
            with pdfplumber.open(self.path) as pdf:
                tables = []
                for page in pdf.pages:
                    tables.extend(page.extract_tables())
        except Exception as error:  # not a real PDF, damaged file, etc.
            raise DataSourceError(f"Could not read PDF file {self.path.name}: {error}") from error

        if not tables:
            raise DataSourceError(f"No tables found in {self.path.name}")
        return tables