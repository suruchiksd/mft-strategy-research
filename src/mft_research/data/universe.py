"""Canonical current partition universe, explicitly not historical membership."""

from pathlib import Path

import pandas as pd


def discover_symbols(root: Path, expected: int = 120) -> list[str]:
    partitions = sorted(root.glob("symbol=*"))
    symbols = [p.name.removeprefix("symbol=") for p in partitions if p.is_dir()]
    if len(symbols) != expected or len(set(symbols)) != expected:
        raise ValueError(f"Expected {expected} symbol partitions, got {len(symbols)}")
    if any(not list(p.glob("year=*/candles.parquet")) for p in partitions):
        raise ValueError("Empty symbol partition")
    return symbols


def apply_eligibility(daily: pd.DataFrame) -> pd.DataFrame:
    result = daily.copy()
    reasons = pd.Series("", index=result.index)
    conditions = [
        (result.prelisting_minutes.gt(0), "PRELISTING_IDENTITY_CONTAMINATION"),
        (result.invalid_ohlc_minutes.gt(0), "INVALID_OHLC"),
        (result.other_invalid_minutes.gt(0) | result.duplicate_minutes.gt(0), "INSUFFICIENT_SOURCE_QUALITY"),
        (result.session_quality.isin(["PARTIAL_SHARED_MARKET_EVENT", "PARTIAL_SYMBOL_SPECIFIC"]), "PARTIAL_SESSION_UNRESOLVED"),
        (result.session_quality.eq("UNKNOWN_IRREGULAR"), "UNKNOWN_IRREGULAR_SESSION"),
        (result.unexpected_minutes.gt(0), "UNEXPECTED_SESSION_MINUTES"),
        (result.valid_bars.eq(0), "NO_VALID_MINUTES"),
        (result.corporate_action_unresolved, "CORPORATE_ACTION_UNRESOLVED"),
    ]
    for mask, label in conditions:
        reasons.loc[mask] += label + "|"
    result["exclusion_reason"] = reasons.str.rstrip("|")
    result["research_eligible"] = result.exclusion_reason.eq("")
    return result


def build_universe(daily: pd.DataFrame, sectors: pd.DataFrame, config: dict) -> pd.DataFrame:
    if daily.groupby("symbol").instrument_token.nunique().ne(1).any():
        raise ValueError("A current symbol has multiple tokens")
    result = daily.groupby("symbol", sort=True).agg(
        instrument_token=("instrument_token", "first"), first_observed_timestamp=("first_timestamp", "min"),
        last_observed_timestamp=("last_timestamp", "max"), observed_sessions=("date", "size"),
        eligible_sessions=("research_eligible", "sum")).reset_index()
    valid = daily[daily.research_eligible].groupby("symbol").agg(
        first_valid_research_date=("date", "min"), last_valid_research_date=("date", "max")).reset_index()
    result = result.merge(valid, on="symbol", how="left", validate="one_to_one")
    result = result.merge(sectors, on="symbol", how="left", validate="one_to_one")
    result["identity_status"] = "CURRENT_PARTITION_IDENTITY_HISTORICAL_ALIASES_UNVERIFIED"
    result["notes"] = "Current fixed universe; no historical membership or lookback eligibility inferred"
    result["identity_valid_from_rule"] = None
    for symbol, rule in config["identity_rules"].items():
        mask = result.symbol.eq(symbol)
        result.loc[mask, "identity_status"] = "PRELISTING_CONTAMINATION_EXCLUDED"
        result.loc[mask, "identity_valid_from_rule"] = rule["valid_from"]
        result.loc[mask, "notes"] = f"Exclude every observation before {rule['valid_from']}; {rule['evidence']}"
    result["research_scope"] = config["research_scope"]
    return result
