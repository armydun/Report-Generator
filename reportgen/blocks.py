"""Content blocks: the building pieces of a report.

A report only says WHAT to show (a heading, a paragraph, a table, a chart).
The Word writer decides HOW each block looks in the company template.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class Heading:
    text: str
    level: int = 1  # 0 = document title, 1 = section, 2 = sub-section


@dataclass
class Paragraph:
    text: str


@dataclass
class Bullets:
    items: list[str]


@dataclass
class Note:
    """A highlighted remark, e.g. 'Product names unavailable: the API did not answer.'"""

    text: str


@dataclass
class Table:
    data: pd.DataFrame
    caption: str = ""


@dataclass
class Chart:
    image_path: Path
    caption: str = ""
    width_cm: float = 16.0


# Any one of the blocks above
Block = Heading | Paragraph | Bullets | Note | Table | Chart