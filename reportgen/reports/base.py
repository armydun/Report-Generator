"""Common frame for every report type, plus a registry of report names."""

import calendar
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from reportgen.blocks import Block
from reportgen.errors import DataSourceError, ReportError
from reportgen.sources import create_source

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Name tag -> class, e.g. {"sales": SalesSummaryReport}
REPORT_REGISTRY: dict[str, type] = {}


def register_report(name: str):
    """Class decorator that adds a report class to the registry."""

    def decorator(cls):
        if name in REPORT_REGISTRY:
            raise ValueError(f"Report '{name}' is already registered")
        REPORT_REGISTRY[name] = cls
        cls.key = name
        return cls

    return decorator


# ---------- the reporting period ----------

@dataclass
class Period:
    """A date range, start and end included."""

    start: date
    end: date

    def __post_init__(self):
        if self.start > self.end:
            raise ReportError(f"Start date {self.start} is after end date {self.end}")

    @classmethod
    def month(cls, year: int, month: int) -> "Period":
        last_day = calendar.monthrange(year, month)[1]
        return cls(date(year, month, 1), date(year, month, last_day))

    def is_full_month(self) -> bool:
        return self == Period.month(self.start.year, self.start.month)

    @property
    def label(self) -> str:
        """Text for the report, e.g. 'October 2026' or '1 Oct 2026 to 15 Oct 2026'."""
        if self.is_full_month():
            return self.start.strftime("%B %Y")
        return f"{self.start:%d %b %Y} to {self.end:%d %b %Y}"

    @property
    def file_tag(self) -> str:
        """Text for file names, e.g. '2026-10' or '2026-10-01_to_2026-10-15'."""
        if self.is_full_month():
            return self.start.strftime("%Y-%m")
        return f"{self.start.isoformat()}_to_{self.end.isoformat()}"

    def previous(self) -> "Period":
        """The period just before this one (the previous month for a full month)."""
        if self.is_full_month():
            day_before = self.start - timedelta(days=1)
            return Period.month(day_before.year, day_before.month)
        length = self.end - self.start
        new_end = self.start - timedelta(days=1)
        return Period(new_end - length, new_end)

    def months(self) -> list[str]:
        """Every month touched by the period, as 'YYYY-MM' text."""
        months = pd.period_range(self.start, self.end, freq="M")
        return [str(month) for month in months]

    def filter(self, df: pd.DataFrame, column: str) -> pd.DataFrame:
        """Keep only the rows whose date in `column` is inside the period."""
        dates = pd.to_datetime(df[column], errors="coerce")
        first_moment = pd.Timestamp(self.start)
        after_last_day = pd.Timestamp(self.end) + pd.Timedelta(days=1)
        return df[(dates >= first_moment) & (dates < after_last_day)]


# ---------- the report frame ----------

class Report(ABC):
    """Base class for every report.

    A report loads its data sources, does its calculations, and returns a
    list of content blocks. It never touches Word directly.
    """

    key: str = "base"
    title: str = "Report"
    file_prefix: str = "Report"
    default_sources: dict[str, dict] = {}

    def __init__(self, period: Period, sources: dict[str, dict] | None = None):
        self.period = period
        self.sources = {**self.default_sources, **(sources or {})}
        self.notes: list[str] = []  # problems to mention inside the report

    @abstractmethod
    def build(self) -> list[Block]:
        """Return the report content as a list of blocks."""

    def output_filename(self) -> str:
        return f"{self.file_prefix}_{self.period.file_tag}.docx"

    def load_source(self, name: str, required: bool = True, **overrides) -> pd.DataFrame | None:
        """Load one named data source.

        required=True : a failure stops the report (DataSourceError).
        required=False: a failure is logged and noted, and None is returned,
                        so the report can still be made from the other sources.
        overrides     : one-off changes to the settings, e.g. url=... for a given year.
        """
        if name not in self.sources:
            raise ReportError(f"Report '{self.key}' has no data source called '{name}'")

        settings = {**self.sources[name], **overrides}  # a new dict, so the original is not changed
        kind = settings.pop("kind")
        if "path" in settings:
            settings["path"] = resolve_path(settings["path"])

        try:
            return create_source(kind, **settings).load()
        except DataSourceError as error:
            if required:
                raise
            logger.warning("Optional source '%s' failed: %s", name, error)
            self.notes.append(f"The {name} data could not be loaded, so it is left out ({error}).")
            return None


# ---------- small helpers for reports ----------

def resolve_path(path: str | Path) -> Path:
    """Relative paths are read from the project folder, wherever the app is started."""
    path = Path(path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def require_columns(df: pd.DataFrame, columns: list[str], source_name: str) -> None:
    """Stop with a clear message if a data source is missing a column the report needs."""
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ReportError(
            f"The {source_name} data is missing column(s): {', '.join(missing)}. "
            f"Found: {', '.join(map(str, df.columns))}"
        )


def money(value: float) -> str:
    """12345.6 -> '$12,346'"""
    return f"${value:,.0f}"


def percent(value: float) -> str:
    """0.1234 -> '12.3%'"""
    return f"{value:.1%}"