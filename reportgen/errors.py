class ReportGeneratorError(Exception):
    """Base class for all errors raised by this app."""


class DataSourceError(ReportGeneratorError):
    """A data source could not be read (missing file, bad format, API failure)."""


class ReportError(ReportGeneratorError):
    """A report could not be built (for example, no data in the date range)."""


class TemplateError(ReportGeneratorError):
    """The Word template is missing or cannot be opened."""