"""Draw report charts with matplotlib and save them as PNG files in figures/."""

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw straight to files, never open a window
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import StrMethodFormatter

from reportgen.errors import ReportError

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = PROJECT_ROOT / "figures"

BAR_COLOR = "#1B5C8A"     # company dark blue: one colour for one series
TARGET_COLOR = "#D95926"  # orange dashed line marks the target (stands out on blue and white)
TEXT_COLOR = "#333333"
GRID_COLOR = "#DDDDDD"
BAR_WIDTH = 0.5


def bar_chart(
    values: pd.Series,
    title: str,
    filename: str,
    horizontal: bool = False,
    output_dir: Path = FIGURES_DIR,
) -> Path:
    """One bar per item. The Series index gives the labels, the values give the bar lengths."""
    check_values(values, title)
    labels = [str(label) for label in values.index]
    fig, ax = new_chart(title)

    if horizontal:  # better when labels are long, e.g. product names
        ax.barh(labels, values.to_numpy(), height=BAR_WIDTH, color=BAR_COLOR)
        ax.invert_yaxis()  # first item at the top
        style_axes(ax, value_axis="x")
    else:
        ax.bar(labels, values.to_numpy(), width=BAR_WIDTH, color=BAR_COLOR)
        style_axes(ax, value_axis="y")

    return save_chart(fig, filename, output_dir)


def bar_with_target_chart(
    actual: pd.Series,
    target: pd.Series,
    title: str,
    filename: str,
    output_dir: Path = FIGURES_DIR,
) -> Path:
    """Bars for the actual values, with a dashed line across each bar marking its target."""
    check_values(actual, title)
    target = target.reindex(actual.index)  # put the targets in the same order as the bars
    labels = [str(label) for label in actual.index]
    positions = range(len(labels))  # 0, 1, 2, ... one position per bar
    fig, ax = new_chart(title)

    ax.bar(positions, actual.to_numpy(), width=BAR_WIDTH, color=BAR_COLOR)
    for x, target_value in zip(positions, target.to_numpy()):
        if pd.notna(target_value):  # a region with no target gets no line
            draw_dashed_line(ax, target_value, x - BAR_WIDTH / 2, x + BAR_WIDTH / 2)
    ax.set_xticks(positions, labels)
    style_axes(ax, value_axis="y")

    legend_items = [
        Patch(color=BAR_COLOR, label="Actual"),
        Line2D([], [], color=TARGET_COLOR, linewidth=3, linestyle=(0, (2, 1)), label="Target"),
    ]
    ax.legend(handles=legend_items, frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.1))

    return save_chart(fig, filename, output_dir)


# ---------- shared helpers ----------

def draw_dashed_line(ax, y: float, left: float, right: float, dashes: int = 4) -> None:
    """Draw a dashed line from left to right that starts and ends with a full dash.

    We draw the dashes ourselves (instead of linestyle="--") so the line fits
    the bar width exactly, with no cut-off dash at the end.
    """
    gap_ratio = 0.5  # each gap is half as long as a dash
    dash_length = (right - left) / (dashes + (dashes - 1) * gap_ratio)
    for i in range(dashes):
        start = left + i * dash_length * (1 + gap_ratio)
        ax.hlines(y, start, start + dash_length, colors=TARGET_COLOR, linewidth=3, zorder=3)


def check_values(values: pd.Series, title: str) -> None:
    if values.empty:
        raise ReportError(f"No data to draw the chart '{title}'")
    if not pd.api.types.is_numeric_dtype(values):
        raise ReportError(f"Chart '{title}' needs numbers, got {values.dtype}")


def new_chart(title: str):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=TEXT_COLOR, pad=14)
    return fig, ax


def style_axes(ax, value_axis: str) -> None:
    """Quiet axes: light grid on the value axis, thousands separators, no box."""
    baseline = "bottom" if value_axis == "y" else "left"
    for side in ["top", "right", "bottom", "left"]:
        ax.spines[side].set_visible(side == baseline)
    ax.spines[baseline].set_color("#999999")

    ax.tick_params(colors=TEXT_COLOR, length=0)
    value_axis_obj = ax.yaxis if value_axis == "y" else ax.xaxis
    value_axis_obj.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.grid(axis=value_axis, color=GRID_COLOR, linewidth=0.8)
    ax.set_axisbelow(True)  # grid lines behind the bars


def save_chart(fig, filename: str, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    try:
        fig.savefig(path, dpi=200, bbox_inches="tight")
    except OSError as error:
        raise ReportError(f"Could not save chart {filename}: {error}") from error
    finally:
        plt.close(fig)  # free the memory, even if saving failed

    logger.info("Saved chart %s", path.name)
    return path