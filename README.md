# Report Generator (Stage 1)

Creates TechInnovate-branded Word reports (and optional PDFs) from three kinds of data source:
**CSV/Excel files, PDF tables and REST APIs**. Reports use the company Word template, keep its
logo, fonts, header and footer, and never change the original template.

```powershell
python run.py --report sales --month 2026-10 --pdf
```

Two reports are included:

| Report | Name in the CLI | Data sources |
|---|---|---|
| **Sales Summary** | `sales` | sales orders (CSV), sales targets (PDF table), product names (REST API: dummyjson.com) |
| **IT Support KPIs** | `it-support` | support tickets (Excel), backup results (PDF table), public holidays (REST API: Nager.Date) |

Sample reports are in [`outputs/`](outputs/): `SalesSummary_2026-10` and `ITSupportKPI_2026-10` (`.docx` and `.pdf`).

---

## Quick start (about 10 minutes)

**You need:** Python 3.11 or newer (tested on 3.13) and Git.
Microsoft Word or LibreOffice is only needed for the optional `--pdf` export.

```powershell
# 1. Get the code
git clone https://github.com/armydun/Report-Generator.git
cd Report-Generator

# 2. Create and turn on a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate           # macOS / Linux

# 3. Install the packages
python -m pip install -r requirements.txt

# 4. Check that everything works (about 5 seconds, no internet needed)
python -m pytest

# 5. Create the two reports
python run.py --report sales --month 2026-10
python run.py --report it-support --month 2026-10 --pdf
```

The reports are saved in `outputs/`, for example `outputs/SalesSummary_2026-10.docx`.
The sample data covers **August to October 2026**, so use one of those months.

> On Windows, if PowerShell blocks `Activate.ps1`, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

---

## Using the command line

```powershell
python run.py --list                                    # show the reports and their data sources
python run.py --report sales --month 2026-10            # a whole month
python run.py --report sales --from 2026-10-01 --to 2026-10-15   # any date range
python run.py --report sales                            # no dates = the last full month
python run.py --report sales --month 2026-10 --pdf      # also save a PDF
python run.py --report sales --month 2026-10 --source sales=other_sales.csv   # use another file
```

| Option | What it does |
|---|---|
| `--report NAME` | Which report to create (`sales`, `it-support`). New reports appear here automatically. |
| `--month YYYY-MM` | A whole month. |
| `--from YYYY-MM-DD --to YYYY-MM-DD` | Any date range (both ends included). |
| `--last-month` | The last full month. This is also the default when no dates are given. |
| `--source NAME=FILE_OR_URL` | Use another file or URL for one of the report's data sources. The kind is worked out from the extension (`.csv`, `.xlsx`, `.pdf`) or from `http(s)://`. Can be used more than once. |
| `--pdf` | Also save a PDF next to the `.docx` (uses Microsoft Word, or LibreOffice if Word is not available). |
| `--output-dir DIR` | Where to save the reports (default: `outputs/`). |
| `--list` | Show the available reports and their data sources. |

**File names** follow the report and the period: `SalesSummary_2026-10.docx`,
`ITSupportKPI_2026-10.pdf`, `SalesSummary_2026-10-01_to_2026-10-15.docx`.

**Logs** are written to the console and to `logs/reportgen.log`.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Everything asked for was created. The path of each new file is printed on its own line (the `.docx`, then the `.pdf`), so the last line is the newest file. |
| `1` | The report could not be created. The reason is shown and logged (for example, no data for the period). |
| `2` | The command itself was wrong (unknown report, bad date format, `--from` without `--to`, ...). |

Log messages go to *stderr* and only the file paths go to *stdout*, so a script or scheduler can read the paths easily.

---

## What is in each report

**Sales Summary** (`sales`)
- Overview: total sales, number of orders, average order value, change against the previous period
- Sales by region: table with share, **target from the PDF**, achievement and status, plus a chart of actual sales against target
- Sales by product: table and chart, with **product names and categories from the REST API**
- Data sources used

**IT Support KPIs** (`it-support`)
- Overview: tickets opened, tickets per working day, average resolution time, SLA rate, change against the previous period
- Working days exclude **Victorian public holidays from the Nager.Date API** (for example, the AFL Grand Final Friday in September 2026)
- Tables by priority (with SLA targets) and by client, and a chart by category
- Backup results from the PDF, lowest success rate first
- Data sources used

Every table grows or shrinks with the data, and every report starts with a note if an optional source could not be used.

---

## Data sources

| Kind | Class | Options |
|---|---|---|
| `csv` | `CsvSource` | `path` |
| `excel` | `ExcelSource` | `path`, `sheet` (name or number, default: first sheet) |
| `pdf` | `PdfTableSource` | `path`, `table_index` (default: first table). Text like `$75,000` becomes the number 75000. `text()` returns all the text in the PDF. |
| `api` | `RestApiSource` | `url`, `params`, `records_path` (where the list is in the JSON, e.g. `products` or `data.items`), `timeout` (default 10 s), `headers` |

Every source has the same method, `load()`, which returns a pandas `DataFrame`. Reports only use
`load()`, so they do not need to know where the data comes from.

### Sample data

All data in `data/` is made up (no real customer data). It covers August to October 2026.

| File | Contents |
|---|---|
| `data/sales.csv` | 277 sales orders |
| `data/tickets.xlsx` | 207 support tickets (sheet `Tickets`) |
| `data/sales_targets.pdf` | monthly sales target per region (table + text) |
| `data/backup_status.pdf` | monthly backup results per client (table + text) |

To create the same files again: `python tools/make_sample_data.py` (it uses a fixed random seed).

The APIs are public and need no key: [dummyjson.com](https://dummyjson.com) returns demo product data,
and [Nager.Date](https://date.nager.at) returns real public holidays. Both are *optional* sources:
if an API cannot be reached, the report is still created and says what is missing.

---

## Error handling

The app never stops with a crash for an expected problem. It shows a short message, writes it to
the log and, where possible, still creates the report.

| Situation | What happens |
|---|---|
| A required file is missing, empty, the wrong type or damaged | Clear message, exit code 1 |
| The data has no rows for the chosen period | `No sales data for January 2025. Try another date range.`, exit code 1 |
| A file is missing columns the report needs | The message lists the missing and the found columns, exit code 1 |
| An optional source fails (API timeout, no internet, HTTP error, bad JSON, missing PDF) | The report is still created, with a note at the top; product IDs are shown instead of names |
| The template is missing or damaged | Clear message, exit code 1 |
| The report is open in Word, so it cannot be saved | `Is it open in Word? Close it and try again.`, exit code 1 |
| `--pdf` but neither Word nor LibreOffice is installed | The `.docx` is kept and the message explains what to install, exit code 1 |
| A real bug | Full details go to `logs/reportgen.log` so it can be fixed, exit code 1 |

---

## Design

```
 data sources              reports                       output
 ------------              -------                       ------
 CSV / Excel  ─┐                                       ┌─► Word (.docx) in the company template
 PDF tables   ─┼─► load() → DataFrame ─► build() ─► blocks ─► docx_writer
 REST API     ─┘                          │                └─► PDF (optional)
                                          └─► charts (matplotlib → PNG)

 run.py (CLI) ──► engine.generate_report() ◄── (later: a UI or a scheduler)
```

Main ideas:

1. **One interface for every data source.** Every source implements `load() -> DataFrame`.
2. **Registries.** Sources and reports register themselves with a decorator
   (`@register_source("csv")`, `@register_report("sales")`). The `sources` and `reports` packages
   import every module in their folder automatically, so **a new source or report is a new file,
   with no change to existing code**. New reports also appear in `run.py --list` and `--help`.
3. **Content is separate from layout.** A report only returns a list of content blocks
   (`Heading`, `Paragraph`, `Bullets`, `Note`, `Table`, `Chart`). `docx_writer` turns them into Word,
   using the template's own styles (Title, Heading 1, List Bullet, Caption, ...).
4. **The template is read-only.** The writer opens `templates/company_template.docx`, adds the content
   and always saves to a new file. A test compares the template's SHA-256 hash before and after
   a report is made, and the writer refuses to save over the template.
5. **Optional sources do not stop a report.** `load_source(name, required=False)` turns a failure into
   a note in the report.
6. **One engine for every entry point.** `run.py` is a thin layer over `reportgen/engine.py`, so a UI
   or a scheduler can call the same function and get the same result.
7. **No AI/LLM in the numbers.** All figures are calculated with pandas, so they are exact, repeatable and testable.

The template in `templates/` is a sample made from TechInnovate's branding (agreed with TechInnovate),
because the real company template was not available.

---

## Adding a new data source

Create one file in `reportgen/sources/`. Nothing else needs to change. For example, a JSON file source:

```python
# reportgen/sources/json_source.py
import pandas as pd

from reportgen.errors import DataSourceError
from reportgen.sources.base import register_source
from reportgen.sources.file_source import FileSource


@register_source("json")
class JsonFileSource(FileSource):
    """Reads a .json file that holds a list of records."""

    allowed_extensions = (".json",)

    def load(self) -> pd.DataFrame:
        self.check_file()  # exists, right extension, not empty
        try:
            df = pd.read_json(self.path)
        except ValueError as error:
            raise DataSourceError(f"Could not read JSON file {self.path.name}: {error}") from error
        return self.check_rows(df)  # not empty, and logs the row count
```

Any report can now use `{"kind": "json", "path": "data/something.json"}` in its `default_sources`.
To also choose it with `--source` by file extension, add `".json": "json"` to `KIND_BY_EXTENSION`
in `reportgen/engine.py`.

## Adding a new report

Create one file in `reportgen/reports/`. It appears in `run.py --list` straight away:

```python
# reportgen/reports/backup_report.py
from reportgen.blocks import Block, Heading, Paragraph, Table
from reportgen.reports.base import Report, register_report


@register_report("backups")
class BackupReport(Report):
    title = "Backup Report"
    file_prefix = "BackupReport"
    default_sources = {"backups": {"kind": "pdf", "path": "data/backup_status.pdf"}}

    def build(self) -> list[Block]:
        backups = self.load_source("backups")
        in_period = backups[backups["Month"].isin(self.period.months())]
        return [
            Heading(f"{self.title} - {self.period.label}", level=0),
            Paragraph(f"{in_period['Jobs'].sum()} backup jobs ran for {len(in_period)} clients."),
            Table(in_period, caption="Backup results by client"),
        ]
```

```powershell
python run.py --report backups --month 2026-10      # -> outputs/BackupReport_2026-10.docx
```

`Report` gives every report `self.period` (with `label`, `file_tag`, `previous()`, `months()` and
`filter(df, column)`), `self.load_source()` and `self.notes`. Charts can be added with
`reportgen.charts.bar_chart()` or `bar_with_target_chart()` and a `Chart` block.

---

## Tests

```powershell
python -m pytest
```

92 tests, which run in a few seconds and **do not need the internet** (the APIs are replaced with
fake responses):

- every data source, including missing, empty, wrong-type and damaged files, and API timeouts, connection errors, HTTP errors and bad JSON
- the Word writer: all block types, header and footer kept, **template never changed**
- both reports: totals checked against the source files, optional sources failing, no data for the period
- **end-to-end runs of the command line** for both reports, exit codes and the PDF option

---

## Project structure

```
Report-Generator/
├── run.py                      # command line
├── requirements.txt
├── pytest.ini
├── templates/company_template.docx   # the company template (read only)
├── data/                       # sample input data
├── outputs/                    # created reports (.docx / .pdf)
├── figures/                    # chart images made while building reports (not in Git)
├── logs/                       # reportgen.log (not in Git)
├── tools/make_sample_data.py   # recreates the sample data
├── reportgen/
│   ├── engine.py               # generate_report(): the one entry point for CLI, UI or scheduler
│   ├── errors.py               # ReportGeneratorError, DataSourceError, ReportError, TemplateError
│   ├── logging_setup.py        # console + logs/reportgen.log
│   ├── blocks.py               # Heading, Paragraph, Bullets, Note, Table, Chart
│   ├── docx_writer.py          # writes blocks into the template
│   ├── charts.py               # bar charts with matplotlib
│   ├── pdf_export.py           # .docx -> .pdf (Word or LibreOffice)
│   ├── sources/                # base.py, file_source.py, pdf_source.py, api_source.py
│   └── reports/                # base.py, sales_summary.py, it_support_kpi.py
└── tests/
```

---

## Stage 2: running on a schedule

The app is ready to be called by a scheduler without any changes: one command, no questions asked,
clear exit codes, and the new file paths printed on stdout. With no dates, it uses the last full
month, so a job that runs on the 1st of each month always reports on the month before.

**Windows Task Scheduler** (7:00 am on the 1st of every month):
```powershell
schtasks /Create /SC MONTHLY /D 1 /ST 07:00 /TN "TechInnovate Sales Report" `
  /TR "C:\path\to\Report-Generator\.venv\Scripts\python.exe C:\path\to\Report-Generator\run.py --report sales --pdf"
```

**Linux cron:**
```
0 7 1 * *  cd /path/to/Report-Generator && .venv/bin/python run.py --report sales --pdf
```

**n8n:** a *Schedule Trigger* → *Execute Command* (`python run.py --report sales --pdf`) →
*If* `exitCode == 0` → email or upload the file from the last line of `stdout`; otherwise send an
alert with `stderr`. (The Execute Command node needs a self-hosted n8n.)

---

Made by Sanghun (Sean) Shin for the TechInnovate intern task, November 2026.
