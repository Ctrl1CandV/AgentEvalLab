"""Configuration: stockroom.toml in the working directory, overridden by environment variables (see README.md)."""
import os
import tomllib
from dataclasses import dataclass


@dataclass
class Config:
    database: str
    timezone: str
    strict: bool
    low_stock_threshold: int
    cache_dir: str


def load(path="stockroom.toml"):
    with open(path, "rb") as handle:
        values = tomllib.load(handle)["stockroom"]
    config = Config(database=values["database"], timezone=values["timezone"], strict=values["strict"],
                    low_stock_threshold=values["low_stock_threshold"], cache_dir=values["cache_dir"])
    if "STOCKROOM_DATABASE" in os.environ:
        config.database = os.environ["STOCKROOM_DATABASE"]
    if "STOCKROOM_TZ" in os.environ:
        config.timezone = os.environ["STOCKROOM_TZ"]
    if "STOCKROOM_STRICT" in os.environ:
        config.strict = bool(os.environ["STOCKROOM_STRICT"])
    if "STOCKROOM_THRESHOLD" in os.environ:
        config.low_stock_threshold = int(os.environ["STOCKROOM_THRESHOLD"])
    return config
