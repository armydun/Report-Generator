"""Report types package.

Importing this package automatically imports every module inside it,
so each @register_report decorator runs and the report is registered.
"""

import importlib
import pkgutil

from reportgen.reports.base import REPORT_REGISTRY, Period, Report, register_report

for module_info in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{module_info.name}")