"""Command line for the report generator.

Examples:
    python run.py --list
    python run.py --report sales --month 2026-10
    python run.py --report it-support --from 2026-09-01 --to 2026-09-30
    python run.py --report sales                      (no dates = last full month)
    python run.py --report sales --month 2026-10 --source sales=other_sales.csv
    python run.py --report sales --month 2026-10 --pdf

Exit codes (for a scheduler such as n8n):
    0  everything asked for was created; the path of each new file is printed
       (the .docx, then the .pdf with --pdf), so the last line is the newest file
    1  something could not be created (the reason is printed and logged)
    2  the command itself was wrong (unknown option, bad date format, ...)
"""

import argparse
import logging
import sys
from datetime import date, timedelta

from reportgen.engine import OUTPUT_DIR, generate_report, source_override
from reportgen.errors import ReportGeneratorError
from reportgen.logging_setup import setup_logging
from reportgen.reports import REPORT_REGISTRY, Period

logger = logging.getLogger("run")


# ---------- reading the command line ----------

def parse_month(text: str) -> Period:
    """'2026-10' -> the whole of October 2026."""
    try:
        year, month = (int(part) for part in text.split("-"))
        return Period.month(year, month)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a month like 2026-10")


def parse_date(text: str) -> date:
    """'2026-10-01' -> date(2026, 10, 1)."""
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a date like 2026-10-01")


def last_month(today: date) -> Period:
    """The last full month before today."""
    last_day_of_previous_month = today.replace(day=1) - timedelta(days=1)
    return Period.month(last_day_of_previous_month.year, last_day_of_previous_month.month)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a TechInnovate report (.docx) from CSV/Excel, PDF and REST API data.",
        epilog="If no dates are given, the last full month is used.",
    )
    parser.add_argument("--report", choices=sorted(REPORT_REGISTRY), help="which report to create")
    parser.add_argument("--list", action="store_true", help="show the available reports and their data sources")

    dates = parser.add_mutually_exclusive_group()
    dates.add_argument("--month", type=parse_month, help="a whole month, e.g. 2026-10")
    dates.add_argument("--from", dest="start", type=parse_date, help="first day, e.g. 2026-10-01 (use with --to)")
    dates.add_argument("--last-month", action="store_true", help="the last full month (the default)")
    parser.add_argument("--to", dest="end", type=parse_date, help="last day, e.g. 2026-10-31 (use with --from)")

    parser.add_argument(
        "--source", action="append", default=[], metavar="NAME=FILE_OR_URL",
        help="use another file or URL for one data source, e.g. sales=data/other_sales.csv",
    )
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="where to save the report (default: outputs/)")
    parser.add_argument("--pdf", action="store_true", help="also save a PDF copy (needs Microsoft Word or LibreOffice)")
    return parser


def choose_period(args, parser) -> Period:
    if args.month:
        return args.month
    if args.start or args.end:
        if not (args.start and args.end):
            parser.error("--from and --to must be used together")
        return Period(args.start, args.end)
    return last_month(date.today())


def print_report_list() -> None:
    for name, report_class in sorted(REPORT_REGISTRY.items()):
        print(f"{name}: {report_class.title}")
        for source_name, settings in report_class.default_sources.items():
            where = settings.get("path") or settings.get("url")
            print(f"    {source_name:<10} {settings['kind']:<6} {where}")


# ---------- running ----------

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        print_report_list()
        return 0
    if not args.report:
        parser.error("--report is required (use --list to see the reports)")

    setup_logging()
    try:
        period = choose_period(args, parser)
        sources = {}
        for item in args.source:
            name, _, location = item.partition("=")
            if not location:
                parser.error(f"--source must look like NAME=FILE_OR_URL, not '{item}'")
            sources[name] = source_override(args.report, name, location)

        result = generate_report(args.report, period, sources, output_dir=args.output_dir, make_pdf=args.pdf)

    except ReportGeneratorError as error:  # an expected problem: clear message, no traceback
        logger.error("Failed: %s", error)
        return 1
    except Exception:  # a bug: keep the full details in the log so it can be fixed
        logger.exception("Failed because of an unexpected error")
        return 1

    for note in result.notes:
        logger.warning("Note in the report: %s", note)
    logger.info("Report created: %s", result.report_path)
    print(result.report_path)  # file paths go to stdout, so a scheduler can pick them up
    if result.pdf_path:
        print(result.pdf_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
