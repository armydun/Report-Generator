"""IT Support KPI report (MSP operations).

Data sources:
    tickets   Excel     support tickets with priority and SLA   (required)
    backups   PDF       monthly backup job results per client   (optional)
    holidays  REST API  Australian public holidays (Nager.Date) (optional)
"""

from datetime import date

import pandas as pd

from reportgen.blocks import Block, Bullets, Chart, Heading, Note, Paragraph, Table
from reportgen.charts import bar_chart
from reportgen.errors import ReportError
from reportgen.reports.base import Report, percent, register_report, require_columns

TICKET_COLUMNS = ["ticket_id", "client", "category", "priority", "opened", "resolved", "status", "sla_hours"]
BACKUP_COLUMNS = ["Month", "Client", "Jobs", "Successful", "Failed"]


@register_report("it-support")
class ITSupportKPIReport(Report):
    title = "IT Support KPIs"
    file_prefix = "ITSupportKPI"
    state = "AU-VIC"  # public holidays are counted for Victoria (Melbourne office)
    default_sources = {
        "tickets": {"kind": "excel", "path": "data/tickets.xlsx", "sheet": "Tickets"},
        "backups": {"kind": "pdf", "path": "data/backup_status.pdf"},
        "holidays": {"kind": "api", "url": "https://date.nager.at/api/v3/PublicHolidays/{year}/AU"},
    }

    def build(self) -> list[Block]:
        # 1. Load the data
        tickets = self.load_source("tickets")  # required
        require_columns(tickets, TICKET_COLUMNS, "tickets")
        backups = self.load_backups()          # optional
        holidays = self.load_holidays()        # optional

        # 2. Keep only tickets opened in this period (and the one before)
        current = add_resolution_hours(self.period.filter(tickets, "opened"))
        if current.empty:
            raise ReportError(f"No tickets were opened in {self.period.label}. Try another date range.")
        previous = add_resolution_hours(self.period.previous().filter(tickets, "opened"))

        # 3. Calculate
        days = working_days(self.period.start, self.period.end, holidays)

        # 4. Content blocks
        blocks: list[Block] = [
            Heading(f"{self.title} - {self.period.label}", level=0),
            Paragraph(
                f"Period: {self.period.start:%d %b %Y} to {self.period.end:%d %b %Y}. "
                f"Generated on {date.today():%d %b %Y}."
            ),
        ]
        blocks += [Note(note) for note in self.notes]
        blocks += self.overview(current, previous, days, holidays)
        blocks += self.priority_section(current)
        blocks += self.client_section(current)
        blocks += self.category_section(current)
        blocks += self.backup_section(backups)
        blocks += self.sources_section(current, backups, holidays)
        return blocks

    # ---------- loading the optional sources ----------

    def load_backups(self) -> pd.DataFrame | None:
        """Backup results from the PDF, only for the months in the period."""
        backups = self.load_source("backups", required=False)
        if backups is None:
            return None
        try:
            require_columns(backups, BACKUP_COLUMNS, "backups")
        except ReportError as error:
            self.notes.append(f"{error} Backup results are left out.")
            return None

        in_period = backups[backups["Month"].isin(self.period.months())]
        if in_period.empty:
            self.notes.append(f"No backup results were found for {self.period.label}.")
            return None
        return in_period

    def load_holidays(self) -> pd.DataFrame | None:
        """Public holidays in the period for our state, from the Nager.Date API."""
        url_template = self.sources["holidays"]["url"]
        frames = []
        for year in range(self.period.start.year, self.period.end.year + 1):
            holidays = self.load_source("holidays", required=False, url=url_template.format(year=year))
            if holidays is None:
                return None
            frames.append(holidays)
        holidays = pd.concat(frames, ignore_index=True)

        try:
            require_columns(holidays, ["date", "localName", "global", "counties"], "holidays")
        except ReportError as error:
            self.notes.append(f"{error} Public holidays are not counted.")
            return None

        for_our_state = holidays.apply(
            lambda row: bool(row["global"]) or self.state in (row["counties"] or []), axis=1
        )
        return self.period.filter(holidays[for_our_state], "date")

    # ---------- report sections ----------

    def overview(self, current, previous, days, holidays) -> list[Block]:
        resolved = current[current["status"] == "Resolved"]
        sla_rate = resolved["met_sla"].mean() if len(resolved) else float("nan")

        text = f"{len(current)} tickets were opened in {self.period.label} across {current['client'].nunique()} clients"
        if days:  # a weekend-only period has no working days, so avoid dividing by zero
            text += f", an average of {len(current) / days:.1f} per working day ({days} working days)."
        else:
            text += ", in a period with no working days."
        if len(resolved):
            text += (
                f" {len(resolved)} were resolved, taking {resolved['hours'].mean():.1f} hours on average, "
                f"and {percent(sla_rate)} of them met their SLA."
            )
        else:
            text += " None of them have been resolved yet."

        previous_resolved = previous[previous["status"] == "Resolved"]
        if len(previous) and len(previous_resolved):
            change = (len(current) - len(previous)) / len(previous)
            sla_change = (sla_rate - previous_resolved["met_sla"].mean()) * 100
            text += (
                f" Compared with {self.period.previous().label}, tickets are "
                f"{'up' if change >= 0 else 'down'} {percent(abs(change))} and the SLA rate is "
                f"{'up' if sla_change >= 0 else 'down'} {abs(sla_change):.1f} percentage points."
            )

        busiest = current["category"].value_counts()
        open_tickets = (current["status"] != "Resolved").sum()
        points = [
            f"Busiest category: {busiest.index[0]} ({busiest.iloc[0]} tickets).",
            f"Tickets still open: {open_tickets}.",
        ]
        if holidays is not None:
            if holidays.empty:
                points.append(f"Public holidays in {self.state[-3:]}: none in this period.")
            else:
                names = ", ".join(f"{name} ({day})" for name, day in zip(holidays["localName"], holidays["date"]))
                points.append(f"Public holidays in {self.state[-3:]}: {names}.")

        return [Heading("Overview", level=1), Paragraph(text), Bullets(points)]

    def priority_section(self, current) -> list[Block]:
        rows = []
        for priority, group in current.groupby("priority"):
            resolved = group[group["status"] == "Resolved"]
            rows.append(
                {
                    "Priority": priority,
                    "Tickets": len(group),
                    "SLA target (h)": group["sla_hours"].iloc[0],
                    "Avg hours": f"{resolved['hours'].mean():.1f}" if len(resolved) else "-",
                    "SLA met": percent(resolved["met_sla"].mean()) if len(resolved) else "-",
                }
            )
        return [
            Heading("Tickets by priority", level=1),
            Table(pd.DataFrame(rows), caption="P1 is the most urgent. Hours are from opened to resolved."),
        ]

    def client_section(self, current) -> list[Block]:
        rows = []
        for client, group in current.groupby("client"):
            resolved = group[group["status"] == "Resolved"]
            rows.append(
                {
                    "Client": client,
                    "Tickets": len(group),
                    "Open": int((group["status"] != "Resolved").sum()),
                    "Avg hours": f"{resolved['hours'].mean():.1f}" if len(resolved) else "-",
                    "SLA met": percent(resolved["met_sla"].mean()) if len(resolved) else "-",
                }
            )
        table = pd.DataFrame(rows).sort_values("Tickets", ascending=False)
        return [
            Heading("Tickets by client", level=1),
            Table(table, caption="Clients with the most tickets first"),
        ]

    def category_section(self, current) -> list[Block]:
        counts = current["category"].value_counts()
        chart_path = bar_chart(
            counts,
            f"Tickets by category - {self.period.label}",
            f"tickets_by_category_{self.period.file_tag}.png",
        )
        return [
            Heading("Tickets by category", level=1),
            Chart(chart_path, caption="Number of tickets opened in each category"),
        ]

    def backup_section(self, backups) -> list[Block]:
        if backups is None:
            return []  # the reason is already shown as a note at the top
        summary = backups.groupby("Client")[["Jobs", "Successful", "Failed"]].sum()
        summary["rate"] = summary["Successful"] / summary["Jobs"]
        summary = summary.sort_values("rate")  # worst first, so problems stand out

        table = pd.DataFrame(
            {
                "Client": summary.index,
                "Jobs": summary["Jobs"],
                "Successful": summary["Successful"],
                "Failed": summary["Failed"],
                "Success rate": summary["rate"].map(percent),
            }
        )
        overall = summary["Successful"].sum() / summary["Jobs"].sum()
        return [
            Heading("Backups", level=1),
            Paragraph(
                f"{summary['Jobs'].sum()} backup jobs ran for {len(summary)} clients, "
                f"with an overall success rate of {percent(overall)}."
            ),
            Table(table, caption="Lowest success rate first"),
        ]

    def sources_section(self, current, backups, holidays) -> list[Block]:
        def where(name: str) -> str:
            settings = self.sources[name]
            text = str(settings.get("path") or settings.get("url"))
            return text.replace("{year}", str(self.period.start.year))

        return [
            Heading("Data sources", level=1),
            Bullets(
                [
                    f"Support tickets (Excel): {where('tickets')} - {len(current)} tickets in this period.",
                    f"Backup results (PDF table): {where('backups')} - "
                    + ("used." if backups is not None else "not available."),
                    f"Public holidays (REST API): {where('holidays')} - "
                    + ("used." if holidays is not None else "not available, weekends only."),
                ]
            ),
        ]


# ---------- calculations (plain functions, easy to test) ----------

def add_resolution_hours(tickets: pd.DataFrame) -> pd.DataFrame:
    """Add 'hours' (opened -> resolved) and 'met_sla' (hours within the SLA) columns."""
    tickets = tickets.copy()
    opened = pd.to_datetime(tickets["opened"], errors="coerce")
    resolved = pd.to_datetime(tickets["resolved"], errors="coerce")
    tickets["hours"] = (resolved - opened).dt.total_seconds() / 3600
    tickets["met_sla"] = tickets["hours"] <= tickets["sla_hours"]
    return tickets


def working_days(start: date, end: date, holidays: pd.DataFrame | None) -> int:
    """Monday-to-Friday days in the period, minus public holidays that fall on them."""
    weekdays = pd.bdate_range(start, end)
    if holidays is None or holidays.empty:
        return len(weekdays)
    holiday_dates = pd.to_datetime(holidays["date"])
    return len(weekdays.difference(holiday_dates))