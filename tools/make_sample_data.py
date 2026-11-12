"""Create the sample input data used by the report generator.

All names and numbers are made up (no real customer data). A fixed random
seed is used, so running this script again always produces the same files.

Creates in data/:
    sales.csv            daily sales orders, Aug-Oct 2026        -> CSV source
    tickets.xlsx         IT support tickets, Aug-Oct 2026        -> Excel source
    sales_targets.pdf    monthly sales target per region (table) -> PDF source
    backup_status.pdf    monthly backup results per client       -> PDF source

Run from the project folder:
    python tools/make_sample_data.py
"""

import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SEED = 2026
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

START = date(2026, 8, 1)
END = date(2026, 10, 31)
MONTHS = ["2026-08", "2026-09", "2026-10"]

REGIONS = ["VIC", "NSW", "QLD", "WA", "SA"]
REGION_WEIGHTS = [30, 28, 18, 12, 12]  # VIC and NSW sell the most

# product_id matches the public test API (dummyjson.com/products/<id>).
# The prices here are our own made-up selling prices.
PRODUCT_PRICES = {
    78: 1999.00,   # laptop
    79: 1799.00,   # laptop
    80: 1399.00,   # laptop
    81: 1099.00,   # laptop
    82: 1499.00,   # laptop
    101: 549.00,   # headphones
    102: 79.00,    # wireless charger
    159: 499.00,   # tablet
    160: 599.00,   # tablet
    161: 349.00,   # tablet
}

CLIENTS = [
    "Bluegum Accounting",
    "Harbourview Dental",
    "Northside Legal",
    "Riverbend Logistics",
    "Southgate Medical",
    "Yarra Valley Wines",
]
CATEGORIES = ["Network", "Hardware", "Software", "Email", "Account Access", "Security"]
PRIORITIES = ["P1", "P2", "P3", "P4"]
PRIORITY_WEIGHTS = [5, 15, 45, 35]
SLA_HOURS = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}


def days_between(start: date, end: date):
    """Yield every date from start to end (inclusive)."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def make_sales(rng: random.Random) -> pd.DataFrame:
    rows = []
    order_number = 10001
    for day in days_between(START, END):
        orders_today = rng.randint(1, 3) if day.weekday() >= 5 else rng.randint(2, 5)
        for _ in range(orders_today):
            product_id = rng.choice(list(PRODUCT_PRICES))
            quantity = rng.randint(1, 4) if PRODUCT_PRICES[product_id] > 1000 else rng.randint(1, 10)
            unit_price = PRODUCT_PRICES[product_id]
            rows.append(
                {
                    "date": day.isoformat(),
                    "order_id": f"SO-{order_number}",
                    "region": rng.choices(REGIONS, weights=REGION_WEIGHTS)[0],
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "amount": round(quantity * unit_price, 2),
                }
            )
            order_number += 1
    return pd.DataFrame(rows)


def make_targets(sales: pd.DataFrame, rng: random.Random) -> list[list[str]]:
    """Monthly target per region, set close to real sales (80%-120% achievement)."""
    month = sales["date"].str[:7]
    actual = sales.groupby([month, "region"])["amount"].sum()
    rows = [["Month", "Region", "Target"]]
    for m in MONTHS:
        for region in REGIONS:
            target = actual.get((m, region), 20000) / rng.uniform(0.8, 1.2)
            target = round(target / 1000) * 1000  # round to the nearest $1,000
            rows.append([m, region, f"${target:,.0f}"])
    return rows


def make_tickets(rng: random.Random) -> pd.DataFrame:
    rows = []
    ticket_number = 5001
    last_moment = datetime(2026, 10, 31, 18, 0)
    for day in days_between(START, END):
        if day.weekday() >= 5:
            count = rng.randint(0, 1)
        else:
            count = rng.randint(2, 4)
        for _ in range(count):
            priority = rng.choices(PRIORITIES, weights=PRIORITY_WEIGHTS)[0]
            sla = SLA_HOURS[priority]
            opened = datetime.combine(day, datetime.min.time()) + timedelta(
                hours=rng.randint(8, 17), minutes=rng.randint(0, 59)
            )
            # About 85% of tickets are solved within the SLA.
            if rng.random() < 0.85:
                hours_taken = rng.uniform(0.2, 0.95) * sla
            else:
                hours_taken = rng.uniform(1.05, 2.5) * sla
            resolved = opened + timedelta(hours=hours_taken)

            still_open = resolved > last_moment or (day >= date(2026, 10, 28) and rng.random() < 0.4)
            if still_open:  # not finished yet at the end of the data period
                status, resolved = "Open", None
            else:
                status = "Resolved"
                resolved = resolved.replace(second=0, microsecond=0)

            rows.append(
                {
                    "ticket_id": f"TCK-{ticket_number}",
                    "client": rng.choice(CLIENTS),
                    "category": rng.choice(CATEGORIES),
                    "priority": priority,
                    "opened": opened,
                    "resolved": resolved,
                    "status": status,
                    "sla_hours": sla,
                }
            )
            ticket_number += 1
    return pd.DataFrame(rows)


def make_backups(rng: random.Random) -> list[list[str]]:
    rows = [["Month", "Client", "Jobs", "Successful", "Failed"]]
    for m in MONTHS:
        for client in CLIENTS:
            jobs = rng.choice([31, 62, 93]) if m != "2026-09" else rng.choice([30, 60, 90])
            failed = rng.choices([0, 1, 2, 3, 5], weights=[40, 25, 15, 12, 8])[0]
            rows.append([m, client, str(jobs), str(jobs - failed), str(failed)])
    return rows


def write_pdf(path: Path, title: str, intro: str, table_rows: list[list[str]]) -> None:
    """Write a simple PDF with a title, a paragraph and a table with grid lines."""
    styles = getSampleStyleSheet()
    table = Table(table_rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),  # lines help pdfplumber find the table
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B5C8A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    doc = SimpleDocTemplate(str(path), pagesize=A4, title=title)
    doc.build(
        [
            Paragraph(title, styles["Title"]),
            Paragraph(intro, styles["Normal"]),
            Spacer(1, 12),
            table,
        ]
    )


def main() -> None:
    rng = random.Random(SEED)
    DATA_DIR.mkdir(exist_ok=True)

    sales = make_sales(rng)
    sales.to_csv(DATA_DIR / "sales.csv", index=False)

    tickets = make_tickets(rng)
    tickets.to_excel(DATA_DIR / "tickets.xlsx", sheet_name="Tickets", index=False)

    write_pdf(
        DATA_DIR / "sales_targets.pdf",
        "Sales Targets by Region - Aug to Oct 2026",
        "Monthly sales targets agreed with each regional manager. "
        "Sample data for the report generator task.",
        make_targets(sales, rng),
    )
    write_pdf(
        DATA_DIR / "backup_status.pdf",
        "Monthly Backup Summary - Aug to Oct 2026",
        "Nightly backup job results for managed clients. "
        "Sample data for the report generator task.",
        make_backups(rng),
    )

    print(f"sales.csv          {len(sales)} rows")
    print(f"tickets.xlsx       {len(tickets)} rows")
    print("sales_targets.pdf  15 rows")
    print("backup_status.pdf  18 rows")
    print(f"Saved to {DATA_DIR}")


if __name__ == "__main__":
    main()
