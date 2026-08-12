from dataclasses import dataclass, field
from pathlib import Path
import glob
import logging
from typing import Any

import yaml


LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class DataConfig:
    tickets_path: str = "data/tickets_mock.csv"
    satisfaction_path: str | None = None
    employees_path: str | None = None
    exports_dir: str = "data/exports"


@dataclass(frozen=True)
class ThresholdConfig:
    anomaly_std_multiplier: float = 1.5
    anomaly_window_months: int = 6
    recurrent_requester_min: int = 5


@dataclass(frozen=True)
class AppConfig:
    data: DataConfig = field(default_factory=DataConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    api_title: str = "RSI KPI API"
    company_name: str = "Sagemcom RSI"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def _resolve_value(value: str | None) -> Path | None:
    if not value:
        return None

    raw = value.strip().strip('"').strip("'")
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = BASE_DIR / candidate

    if any(char in str(candidate) for char in ["*", "?"]):
        matches = sorted(glob.glob(str(candidate)))
        return Path(matches[0]) if matches else candidate

    return candidate


def resolve_path(value: str | None) -> Path | None:
    return _resolve_value(value)


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = BASE_DIR / config_path

    if not config_path.exists():
        LOGGER.warning("Config file not found, using defaults: %s", config_path)
        return AppConfig()

    with config_path.open("r", encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle) or {}

    data_raw = raw.get("data", {})
    thresholds_raw = raw.get("thresholds", {})

    return AppConfig(
        data=DataConfig(
            tickets_path=data_raw.get("tickets_path", DataConfig.tickets_path),
            satisfaction_path=data_raw.get("satisfaction_path", DataConfig.satisfaction_path),
            employees_path=data_raw.get("employees_path", DataConfig.employees_path),
            exports_dir=data_raw.get("exports_dir", DataConfig.exports_dir),
        ),
        thresholds=ThresholdConfig(
            anomaly_std_multiplier=float(
                thresholds_raw.get("anomaly_std_multiplier", ThresholdConfig.anomaly_std_multiplier)
            ),
            anomaly_window_months=int(
                thresholds_raw.get("anomaly_window_months", ThresholdConfig.anomaly_window_months)
            ),
            recurrent_requester_min=int(
                thresholds_raw.get("recurrent_requester_min", ThresholdConfig.recurrent_requester_min)
            ),
        ),
        api_title=raw.get("api_title", AppConfig.api_title),
        company_name=raw.get("company_name", AppConfig.company_name),
    )
