"""Write content blocks into a copy of the company Word template.

The original template is only OPENED, never saved. The finished report
is always saved as a new file, so the template can never be changed.
"""

import logging
import re
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, RGBColor

from reportgen.blocks import Block, Bullets, Chart, Heading, Note, Paragraph, Table
from reportgen.errors import ReportError, TemplateError

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TEMPLATE = PROJECT_ROOT / "templates" / "company_template.docx"

BRAND_DARK_BLUE = "1B5C8A"
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
NOTE_COLOR = RGBColor(0x1B, 0x5C, 0x8A)
NUMBER_LIKE = re.compile(r"[-+]?\$?[\d,]+(\.\d+)?%?")  # e.g. 1,200  $85,000  -3.5%
TABLE_WIDTH_CM = 16.5  # page width minus the template margins


def write_report(
    blocks: list[Block], output_path: str | Path, template_path: str | Path = DEFAULT_TEMPLATE
) -> Path:
    """Open the template, add every block to the body, and save as a NEW file."""
    template_path = Path(template_path)
    output_path = Path(output_path)

    if output_path.resolve() == template_path.resolve():
        raise TemplateError("The output file cannot be the template itself")

    document = open_template(template_path)
    for block in blocks:
        add_block(document, block)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        document.save(output_path)
    except PermissionError as error:
        raise ReportError(
            f"Could not save {output_path.name}. Is it open in Word? Close it and try again."
        ) from error

    logger.info("Saved report to %s", output_path)
    return output_path


def open_template(template_path: Path):
    """Open the Word template (read only - we never call save on this path)."""
    if not template_path.is_file():
        raise TemplateError(f"Template not found: {template_path}")
    try:
        return Document(str(template_path))
    except Exception as error:  # not a real .docx, damaged file, etc.
        raise TemplateError(f"Could not open template {template_path.name}: {error}") from error


def add_block(document, block: Block) -> None:
    """Add one content block, using the template's own styles."""
    if isinstance(block, Heading):
        document.add_heading(block.text, level=block.level)  # level 0 = "Title" style

    elif isinstance(block, Paragraph):
        document.add_paragraph(block.text)

    elif isinstance(block, Bullets):
        for item in block.items:
            document.add_paragraph(item, style="List Bullet")

    elif isinstance(block, Note):
        paragraph = document.add_paragraph()
        label = paragraph.add_run("Note: ")
        label.bold = True
        text = paragraph.add_run(block.text)
        text.italic = True
        for run in (label, text):
            run.font.color.rgb = NOTE_COLOR

    elif isinstance(block, Table):
        add_table(document, block)

    elif isinstance(block, Chart):
        add_chart(document, block)

    else:
        raise ReportError(f"Unknown block type: {type(block).__name__}")


def add_table(document, block: Table) -> None:
    """Add a table: one header row plus one row per DataFrame row."""
    df = block.data
    if df.empty:
        document.add_paragraph("No data for this period.")
        return

    table = document.add_table(rows=1, cols=len(df.columns))
    table.style = "Table Grid"

    # Header row: column names, dark blue background, white bold text
    for cell, column_name in zip(table.rows[0].cells, df.columns):
        cell.text = str(column_name)
        shade_cell(cell, BRAND_DARK_BLUE)
        run = cell.paragraphs[0].runs[0]
        run.bold = True
        run.font.color.rgb = WHITE

    # Data rows: the number of rows changes with the data
    for values in df.itertuples(index=False):
        row_cells = table.add_row().cells
        for cell, value in zip(row_cells, values):
            text = "" if pd.isna(value) else str(value)
            cell.text = text
            if NUMBER_LIKE.fullmatch(text):
                cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Give wide columns (e.g. long product names) more room than short ones
    table.autofit = False
    for column, width in zip(table.columns, column_widths(df)):
        column.width = width       # the table's column grid
        for cell in column.cells:
            cell.width = width     # each cell (Word reads this)

    if block.caption:
        document.add_paragraph(block.caption, style="Caption")


def column_widths(df: pd.DataFrame) -> list[Cm]:
    """Share the table width between columns by how long their text is."""
    lengths = []
    for column in df.columns:
        longest = max([len(str(column))] + [len(str(value)) for value in df[column]])
        lengths.append(min(max(longest, 5), 30) + 3)  # 5 to 30 characters, plus room for cell padding
    total = sum(lengths)
    return [Cm(TABLE_WIDTH_CM * length / total) for length in lengths]


def add_chart(document, block: Chart) -> None:
    """Add a chart image, centred, with an optional caption."""
    image_path = Path(block.image_path)
    if not image_path.is_file():
        raise ReportError(f"Chart image not found: {image_path}")

    document.add_picture(str(image_path), width=Cm(block.width_cm))
    document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    if block.caption:
        caption = document.add_paragraph(block.caption, style="Caption")
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER


def shade_cell(cell, hex_color: str) -> None:
    """Fill a table cell with a background colour.

    python-docx has no simple function for this, so we add the
    <w:shd> setting directly to the cell's XML.
    """
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), hex_color)
    cell._tc.get_or_add_tcPr().append(shading)