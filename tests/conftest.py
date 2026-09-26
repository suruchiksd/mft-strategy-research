from pathlib import Path

import pandas as pd
import pytest
import yaml

from mft_research.data.sessions import SessionRules


PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config():
    return yaml.safe_load((PROJECT / "config/research_data.yaml").read_text())


@pytest.fixture
def rules(config):
    return SessionRules(config, PROJECT)


def minutes(day="2024-06-24", symbol="ABB", start="09:15", periods=375):
    timestamp = pd.date_range(f"{day} {start}", periods=periods, freq="min", tz="Asia/Kolkata")
    return pd.DataFrame({"timestamp": timestamp, "open": 100.0, "high": 103.0, "low": 99.0,
                         "close": 102.0, "volume": 10, "symbol": symbol, "instrument_token": 3329})
