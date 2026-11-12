"""Data sources package.

Importing this package automatically imports every module inside it,
so each @register_source decorator runs and the source is registered.
"""

import importlib
import pkgutil

from reportgen.sources.base import SOURCE_REGISTRY, DataSource, create_source, register_source

for module_info in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{module_info.name}")