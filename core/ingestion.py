from pathlib import Path
import logging

import pandas as pd

from core.config import AppConfig, resolve_path
from core.exceptions import DataSourceError


LOGGER = logging.getLogger(__name__)


def load_tabular(source, required: bool = True) -> pd.DataFrame:
    """Load a CSV, CSV.GZ, XLS or XLSX file."""
    if source is None:
        if required:
            raise DataSourceError("No data source provided.")
        return pd.DataFrame()

    name = getattr(source, "name", str(source))
    suffixes = "".join(Path(name).suffixes).lower()

    if hasattr(source, "seek"):
        source.seek(0)

    try:
        if suffixes.endswith(".csv") or suffixes.endswith(".csv.gz"):
            last_error = None
            compression = "gzip" if suffixes.endswith(".gz") else "infer"
            for encoding in ["utf-8-sig", "cp1252", "latin1"]:
                try:
                    if hasattr(source, "seek"):
                        source.seek(0)
                    return pd.read_csv(
                        source,
                        sep=None,
                        engine="python",
                        encoding=encoding,
                        compression=compression,
                        index_col=False,
                    )
                except UnicodeDecodeError as exc:
                    last_error = exc
            raise last_error if last_error else DataSourceError(f"Cannot read file {name}")
        if suffixes.endswith(".xlsx") or suffixes.endswith(".xls"):
            return pd.read_excel(source)
    except Exception as exc:
        raise DataSourceError(f"Cannot read file {name}: {exc}") from exc

    raise DataSourceError(f"Unsupported file format: {name}")


def load_sources(config: AppConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tickets_path = resolve_path(config.data.tickets_path)
    satisfaction_path = resolve_path(config.data.satisfaction_path)
    employees_path = resolve_path(config.data.employees_path)

    if tickets_path is None or not tickets_path.exists():
        raise DataSourceError(f"Tickets file not found: {tickets_path}")

    LOGGER.info("Loading tickets from %s", tickets_path)
    tickets = load_tabular(tickets_path)

    satisfaction = pd.DataFrame()
    if satisfaction_path and satisfaction_path.exists():
        LOGGER.info("Loading satisfaction from %s", satisfaction_path)
        satisfaction = load_tabular(satisfaction_path, required=False)
    else:
        LOGGER.warning("Satisfaction file not found or not configured: %s", satisfaction_path)

    employees = pd.DataFrame()
    if employees_path and employees_path.exists():
        LOGGER.info("Loading employees from %s", employees_path)
        employees = load_tabular(employees_path, required=False)
    else:
        LOGGER.warning("Employees file not found or not configured: %s", employees_path)

    return tickets, satisfaction, employees
