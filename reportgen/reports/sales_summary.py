"""Sales Summary report.

Uses all three kinds of data source:
    sales     CSV       daily sales orders                 (required)
    targets   PDF       monthly sales target per region    (optional)
    products  REST API  product names and categories       (optional)
"""

from datetime import date, timedelta

import pandas as pd

from reportgen.blocks import Block, Bullets, Chart, Heading, Note, Paragraph, Table
from reportgen.charts import bar_chart, bar_with_target_chart
from reportgen.errors import ReportError
from reportgen.reports.base import Report, money, percent, register_report, require_columns

SALES_COLUMNS = ["date", "order_id", "region", "product_id", "quantity", "amount"]


@register_report("sales")
class SalesSummaryReport(Report):
    title = "Sales Summary"
    file_prefix = "SalesSummary"
    default_sources = {
        "sales": {"kind": "csv", "path": "data/sales.csv"},
        "targets": {"kind": "pdf", "path": "data/sales_targets.pdf"},
        "products": {
            "kind": "api",
            "url": "https://dummyjson.com/products",
            "params": {"limit": 0, "select": "title,category,price"},
            "records_path": "products",
        },
    }

    def build(self) -> list[Block]:
        # 1. Load the data
        sales = self.load_source("sales")  # required: no sales, no report
        require_columns(sales, SALES_COLUMNS, "sales")
        targets = self.load_targets()      # optional: None if unavailable
        products = self.load_products()    # optional: None if unavailable

        # 2. Keep only this period (and the one before, for comparison)
        current = self.period.filter(sales, "date")
        if current.empty:
            raise ReportError(f"No sales data for {self.period.label}. Try another date range.")
        previous = self.period.previous().filter(sales, "date")

        # 3. Calculate
        regions = sales_by_region(current, targets)
        product_sales = sales_by_product(current, products)

        # 4. Turn the results into content blocks
        blocks: list[Block] = [
            Heading(f"{self.title} - {self.period.label}", level=0),
            Paragraph(
                f"Period: {self.period.start:%d %b %Y} to {self.period.end:%d %b %Y}. "
                f"Generated on {date.today():%d %b %Y}."
            ),
        ]
        blocks += [Note(note) for note in self.notes]
        blocks += self.overview(current, previous, regions, product_sales)
        blocks += self.region_section(regions)
        blocks += self.product_section(product_sales)
        blocks += self.sources_section(current, targets, products)
        return blocks

    # ---------- loading the optional sources ----------

    def load_targets(self) -> pd.Series | None:
        """Monthly targets from the PDF, added up per region for the months in the period."""
        targets = self.load_source("targets", required=False)
        if targets is None:
            return None
        try:
            require_columns(targets, ["Month", "Region", "Target"], "targets")
        except ReportError as error:
            self.notes.append(f"{error} Targets are left out.")
            return None

        in_period = targets[targets["Month"].isin(self.period.months())]
        if in_period.empty:
            self.notes.append(f"No sales targets were found for {self.period.label}.")
            return None
        if not covers_whole_months(self.period.start, self.period.end):
            self.notes.append(
                "The selected dates do not cover whole months, "
                "so the monthly targets are only a rough guide."
            )
        return in_period.groupby("Region")["Target"].sum()

    def load_products(self) -> pd.DataFrame | None:
        """Product names and categories from the REST API, indexed by product id."""
        products = self.load_source("products", required=False)
        if products is None:
            return None
        try:
            require_columns(products, ["id", "title", "category"], "products")
        except ReportError as error:
            self.notes.append(f"{error} Product IDs are shown instead of names.")
            return None
        return products.set_index("id")[["title", "category"]]

    # ---------- report sections ----------

    def overview(self, current, previous, regions, product_sales) -> list[Block]:
        total = current["amount"].sum()
        orders = current["order_id"].nunique()
        text = (
            f"Total sales for {self.period.label} were {money(total)} from {orders} orders, "
            f"an average of {money(total / orders)} per order."
        )

        previous_label = self.period.previous().label
        previous_total = previous["amount"].sum()
        if previous_total > 0:
            change = (total - previous_total) / previous_total
            direction = "up" if change >= 0 else "down"
            text += f" This is {direction} {percent(abs(change))} on {previous_label} ({money(previous_total)})."
        else:
            text += f" There is no sales data for {previous_label} to compare with."

        points = [
            f"Top region: {regions.index[0]} with {money(regions['sales'].iloc[0])} "
            f"({percent(regions['share'].iloc[0])} of all sales).",
            f"Best-selling product: {product_sales['name'].iloc[0]} "
            f"with {money(product_sales['sales'].iloc[0])}.",
        ]
        if "target" in regions:
            has_target = regions["target"].notna()
            on_target = (regions.loc[has_target, "sales"] >= regions.loc[has_target, "target"]).sum()
            points.append(f"Regions on target: {on_target} of {has_target.sum()}.")

        return [Heading("Overview", level=1), Paragraph(text), Bullets(points)]

    def region_section(self, regions: pd.DataFrame) -> list[Block]:
        table = pd.DataFrame(
            {
                "Region": regions.index,
                "Sales": regions["sales"].map(money),
                "Share": regions["share"].map(percent),
            }
        )
        if "target" in regions:
            table["Target"] = regions["target"].map(lambda v: money(v) if pd.notna(v) else "-")
            table["Achieved"] = regions["achievement"].map(lambda v: percent(v) if pd.notna(v) else "-")
            table["Status"] = regions["achievement"].map(target_status)
            chart_path = bar_with_target_chart(
                regions["sales"], regions["target"],
                f"Sales vs target by region - {self.period.label}",
                f"sales_by_region_{self.period.file_tag}.png",
            )
        else:
            chart_path = bar_chart(
                regions["sales"],
                f"Sales by region - {self.period.label}",
                f"sales_by_region_{self.period.file_tag}.png",
            )

        return [
            Heading("Sales by region", level=1),
            Table(table, caption="Sales by region, highest first"),
            Chart(chart_path, caption="Bars show actual sales; dashed lines show the target"
                  if "target" in regions else "Sales by region"),
        ]

    def product_section(self, product_sales: pd.DataFrame) -> list[Block]:
        table = pd.DataFrame(
            {
                "Product": product_sales["name"],
                "Category": product_sales["category"],
                "Units": product_sales["units"].map("{:,}".format),
                "Sales": product_sales["sales"].map(money),
                "Share": product_sales["share"].map(percent),
            }
        )
        chart_path = bar_chart(
            product_sales.set_index("name")["sales"],
            f"Sales by product - {self.period.label}",
            f"sales_by_product_{self.period.file_tag}.png",
            horizontal=True,
        )
        return [
            Heading("Sales by product", level=1),
            Table(table, caption="Sales by product, highest first"),
            Chart(chart_path, caption="Sales by product"),
        ]

    def sources_section(self, current, targets, products) -> list[Block]:
        def where(name: str) -> str:
            settings = self.sources[name]
            return str(settings.get("path") or settings.get("url"))

        return [
            Heading("Data sources", level=1),
            Bullets(
                [
                    f"Sales orders (CSV): {where('sales')} - {len(current)} orders in this period.",
                    f"Sales targets (PDF table): {where('targets')} - "
                    + ("used." if targets is not None else "not available."),
                    f"Product names (REST API): {where('products')} - "
                    + ("used." if products is not None else "not available, product IDs shown."),
                ]
            ),
        ]


# ---------- calculations (plain functions, easy to test) ----------

def sales_by_region(current: pd.DataFrame, targets: pd.Series | None) -> pd.DataFrame:
    """Total sales per region (highest first), with target and achievement if known."""
    regions = (
        current.groupby("region")["amount"].sum()
        .sort_values(ascending=False)
        .to_frame("sales")
    )
    regions["share"] = regions["sales"] / regions["sales"].sum()
    if targets is not None:
        regions["target"] = targets.reindex(regions.index)
        regions["achievement"] = regions["sales"] / regions["target"]
    return regions


def sales_by_product(current: pd.DataFrame, products: pd.DataFrame | None) -> pd.DataFrame:
    """Units and sales per product (highest sales first), with names from the API if known."""
    result = (
        current.groupby("product_id")
        .agg(units=("quantity", "sum"), sales=("amount", "sum"))
        .sort_values("sales", ascending=False)
    )
    result["share"] = result["sales"] / result["sales"].sum()

    names, categories = [], []
    for product_id in result.index:
        if products is not None and product_id in products.index:
            names.append(products.loc[product_id, "title"])
            categories.append(products.loc[product_id, "category"])
        else:  # API failed or does not know this id
            names.append(f"Product {product_id}")
            categories.append("-")
    result["name"] = names
    result["category"] = categories
    return result


def target_status(achievement: float) -> str:
    if pd.isna(achievement):
        return "No target"
    return "On target" if achievement >= 1 else "Below target"


def covers_whole_months(start: date, end: date) -> bool:
    """True when start is the 1st of a month and end is the last day of a month."""
    return start.day == 1 and (end + timedelta(days=1)).day == 1