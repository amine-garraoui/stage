from functools import lru_cache
import logging

import pandas as pd

from core.config import AppConfig, load_config
from core.ingestion import load_sources
from core.transformation import build_dataset


LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def load_dataset_cached(config_path: str = "config.yaml") -> pd.DataFrame:
    config = load_config(config_path)
    tickets, satisfaction, employees = load_sources(config)
    dataset = build_dataset(tickets, satisfaction, employees)
    LOGGER.info("Dataset ready: %s rows", len(dataset))
    return dataset


def load_dataset(config: AppConfig) -> pd.DataFrame:
    tickets, satisfaction, employees = load_sources(config)
    return build_dataset(tickets, satisfaction, employees)
