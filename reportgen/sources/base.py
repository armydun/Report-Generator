import pandas as pd
from abc import ABC, abstractmethod
from reportgen.errors import DataSourceError

SOURCE_REGISTRY: dict[str, type] = {}  ##Name tag -> class

class DataSource(ABC):
    """base class for all data sources (csv, excel, pdf, api)"""
    kind: str = "base"
    
    @abstractmethod
    def load(self) -> pd.DataFrame:
        """read data return it table"""

def register_source(name: str):
    """ class decorator to register a data source class with a name """
    
    def decorator(cls):
        if name in SOURCE_REGISTRY:
            raise ValueError(f"data source '{name}' is already registered")
        SOURCE_REGISTRY[name] = cls
        cls.kind = name
        return cls
    return decorator

def create_source(kind: str, **options) -> DataSource:
    """Build a data source by its registered name.Example: create_source("csv", path="data/sales.csv")"""
    source_class = SOURCE_REGISTRY.get(kind)
    
    if source_class is None:
        available = ", ".join(sorted(SOURCE_REGISTRY)) or "none"
        raise DataSourceError(f"Unknown data source '{kind}'. Available: {available}")

    try:
        return source_class(**options)
    except TypeError as error:
        raise DataSourceError(f"Wrong options for '{kind}' source: {error}") from error