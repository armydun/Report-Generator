"""Turn a finished Word report into a PDF (a bonus feature).

Two ways are tried, in this order:
    1. Microsoft Word, through the docx2pdf package (Windows or macOS with Word installed)
    2. LibreOffice in "headless" mode (no window), on any system where it is installed
"""

import logging
import shutil
import subprocess
from pathlib import Path

from reportgen.errors import ReportError

logger = logging.getLogger(__name__)

# Usual install places, in case LibreOffice is not on the PATH
LIBREOFFICE_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


def export_pdf(docx_path: str | Path) -> Path:
    """Save a PDF copy of the report next to the .docx file and return its path."""
    docx_path = Path(docx_path)
    pdf_path = docx_path.with_suffix(".pdf")

    try:
        pdf_path.unlink(missing_ok=True)  # remove an old PDF, so we never return a stale one
    except PermissionError as error:
        raise ReportError(f"Could not replace {pdf_path.name}. Is it open? Close it and try again.") from error

    problems = []
    for name, convert in [("Microsoft Word", convert_with_word), ("LibreOffice", convert_with_libreoffice)]:
        try:
            convert(docx_path, pdf_path)
        except Exception as error:  # this converter is missing or failed, so try the next one
            problems.append(f"{name}: {error}")
            continue
        if pdf_path.exists():
            logger.info("Saved PDF to %s (using %s)", pdf_path, name)
            return pdf_path
        problems.append(f"{name}: no PDF was produced")

    raise ReportError(
        f"The Word report was saved, but the PDF could not be created. "
        f"Install Microsoft Word or LibreOffice to use --pdf. Details: {'; '.join(problems)}"
    )


def convert_with_word(docx_path: Path, pdf_path: Path) -> None:
    from docx2pdf import convert  # imported here: only needed (and only installed) on Windows

    convert(str(docx_path), str(pdf_path))


def convert_with_libreoffice(docx_path: Path, pdf_path: Path) -> None:
    soffice = find_libreoffice()
    if soffice is None:
        raise FileNotFoundError("LibreOffice is not installed")
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pdf_path.parent), str(docx_path)],
        check=True, capture_output=True, timeout=120,
    )


def find_libreoffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)  # looks through the folders on the PATH
        if found:
            return found
    for path in LIBREOFFICE_PATHS:
        if Path(path).exists():
            return path
    return None
