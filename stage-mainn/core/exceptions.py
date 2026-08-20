class KpiError(Exception):
    """Base exception for the KPI application."""


class DataSourceError(KpiError):
    """Raised when a data source cannot be read."""


class SchemaError(KpiError):
    """Raised when a data file does not match the expected schema."""
