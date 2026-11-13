"""The engine: turns (report name, period, data sources) into a finished report file.

The command line (run.py) calls this, and a future UI or scheduler can call
exactly the same function, so every way of running the app behaves the same.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from reportgen.docx_writer import write_report
from reportgen.errors import ReportError
from reportgen.pdf_export import export_pdf
from reportgen.reports import REPORT_REGISTRY, Period

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# File extension -> data source kind, used when the user points a source at another file
KIND_BY_EXTENSION = {".csv": "csv", ".xlsx": "excel", ".pdf": "pdf"}


@dataclass
class RunResult:
    report_path: Path
    pdf_path: Path | None = None
    notes: list[str] = field(default_factory=list)


def generate_report(
    report_name: str,
    period: Period,
    sources: dict[str, dict] | None = None,
    output_dir: str | Path = OUTPUT_DIR,
    make_pdf: bool = False,
) -> RunResult:
    """Build one report, save it as a Word file in output_dir, and optionally as a PDF too."""
    report_class = REPORT_REGISTRY.get(report_name)
    if report_class is None:
        available = ", ".join(sorted(REPORT_REGISTRY))
        raise ReportError(f"Unknown report '{report_name}'. Available: {available}")

    report = report_class(period, sources)
    logger.info("Building '%s' for %s", report.title, period.label)
    blocks = report.build()
    path = write_report(blocks, Path(output_dir) / report.output_filename())
    result = RunResult(report_path=path, notes=report.notes)

    if make_pdf:
        result.pdf_path = export_pdf(path)
    return result


def source_override(report_name: str, source_name: str, location: str) -> dict:
    """Settings that point one of a report's sources at another file or URL.

    The kind of source is worked out from the location:
    .csv -> csv, .xlsx -> excel, .pdf -> pdf, http(s)://... -> api
    """
    report_class = REPORT_REGISTRY[report_name]
    defaults = report_class.default_sources.get(source_name)
    if defaults is None:
        names = ", ".join(report_class.default_sources)
        raise ReportError(f"Report '{report_name}' has no source called '{source_name}'. Its sources are: {names}")

    if location.startswith(("http://", "https://")):
        return {**defaults, "kind": "api", "url": location}

    kind = KIND_BY_EXTENSION.get(Path(location).suffix.lower())
    if kind is None:
        raise ReportError(f"Cannot tell the type of '{location}'. Use a .csv, .xlsx or .pdf file, or a URL.")

    settings = {"kind": kind, "path": str(Path(location).resolve())}  # relative to where the command runs
    if kind == defaults["kind"]:
        settings = {**defaults, **settings}  # same type of file: keep options such as the Excel sheet
    return settings
