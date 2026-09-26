"""Deterministic valid-minute OHLCV aggregation, preserving every observed date."""

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .sessions import SessionRules


REQUIRED = ["timestamp", "open", "high", "low", "close", "volume", "symbol", "instrument_token"]


def aggregate_minutes(frame: pd.DataFrame, symbol: str, rules: SessionRules, config: dict,
                      source_file: str = "fixture") -> tuple[pd.DataFrame, pd.DataFrame]:
    if set(frame.columns) != set(REQUIRED):
        raise ValueError(f"Unexpected minute schema: {frame.columns.tolist()}")
    if str(frame.timestamp.dt.tz) != config["timezone"]:
        raise ValueError("Minute timestamps must be Asia/Kolkata aware")
    if frame.timestamp.isna().any() or frame.symbol.ne(symbol).any():
        raise ValueError("Missing timestamp or partition symbol mismatch")
    if frame.instrument_token.isna().any() or frame.instrument_token.nunique() != 1:
        raise ValueError("Ambiguous instrument token")
    d = frame.sort_values("timestamp", kind="stable").reset_index(drop=True).copy()
    d["_day"] = d.timestamp.dt.tz_localize(None).dt.normalize()
    d["_minute"] = d.timestamp.dt.hour * 60 + d.timestamp.dt.minute
    prices = d[["open", "high", "low", "close"]]
    bad_ohlc = (~np.isfinite(prices)).any(axis=1) | prices.le(0).any(axis=1)
    bad_ohlc |= d.high.lt(prices[["open", "low", "close"]].max(axis=1))
    bad_ohlc |= d.low.gt(prices[["open", "high", "close"]].min(axis=1))
    off_minute = d.timestamp.ne(d.timestamp.dt.floor("min"))
    bad_other = ~np.isfinite(d.volume) | d.volume.lt(0) | d.volume.mod(1).ne(0) | off_minute
    duplicate = d.timestamp.duplicated(keep=False)
    identity = pd.Series(False, index=d.index)
    rule = config["identity_rules"].get(symbol)
    if rule:
        identity = d._day.lt(pd.Timestamp(rule["valid_from"]))
    # Vectorized usual grid, with explicit date overrides. No future rows are consulted.
    within = d._minute.isin(rules.normal)
    known = pd.Series(True, index=d.index)
    specs = {}
    for day in d._day.unique():
        spec = rules.for_date(pd.Timestamp(day).date())
        specs[pd.Timestamp(day)] = spec
        if spec.expected != rules.normal:
            mask = d._day.eq(day)
            if spec.expected is None:
                known.loc[mask] = False
                within.loc[mask] = True  # audit aggregation only; unknown sessions are ineligible
            else:
                within.loc[mask] = d.loc[mask, "_minute"].isin(spec.expected)
    outside = known & ~within
    good = ~(bad_ohlc | bad_other | duplicate | identity | outside)
    d["_invalid_ohlc"] = bad_ohlc.astype("int64")
    d["_other_invalid"] = bad_other.astype("int64")
    d["_duplicate"] = duplicate.astype("int64")
    d["_prelisting"] = identity.astype("int64")
    d["_zero_volume"] = d.volume.eq(0).astype("int64")
    d["_unexpected"] = outside.astype("int64")
    d["_off_minute"] = off_minute.astype("int64")
    base = d.groupby("_day", sort=True).agg(
        observed_bars=("timestamp", "size"), observed_unique_minutes=("timestamp", "nunique"),
        first_timestamp=("timestamp", "first"), last_timestamp=("timestamp", "last"),
        invalid_ohlc_minutes=("_invalid_ohlc", "sum"), other_invalid_minutes=("_other_invalid", "sum"),
        duplicate_minutes=("_duplicate", "sum"), prelisting_minutes=("_prelisting", "sum"),
        zero_volume_minutes=("_zero_volume", "sum"), unexpected_minutes=("_unexpected", "sum"),
        off_minute_rows=("_off_minute", "sum"))
    # Exact-minute counts are separate from distinct timestamps for malformed fractional labels.
    base["observed_unique_minutes"] = d.assign(_floor=d.timestamp.dt.floor("min")).groupby("_day")._floor.nunique()
    valid = d.loc[good].groupby("_day", sort=True).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"), valid_bars=("timestamp", "size"),
        first_valid_timestamp=("timestamp", "first"), last_valid_timestamp=("timestamp", "last"))
    base = base.join(valid)
    base["volume"] = base.volume.fillna(0).astype("int64")
    base["valid_bars"] = base.valid_bars.fillna(0).astype("int64")
    covered = d.loc[within & ~off_minute].groupby("_day")._minute.nunique()
    missing, session_types, open_true, close_true = [], [], [], []
    for day, row in base.iterrows():
        spec = specs[day]
        session_types.append(spec.session_type)
        missing.append(len(spec.expected) - int(covered.get(day, 0)) if spec.expected is not None else None)
        start = pd.Timestamp(day, tz=config["timezone"])
        open_true.append(bool(spec.expected is not None and pd.notna(row.first_valid_timestamp)
                              and row.first_valid_timestamp == start + pd.Timedelta(minutes=min(spec.expected))))
        close_true.append(bool(spec.expected is not None and pd.notna(row.last_valid_timestamp)
                               and row.last_valid_timestamp == start + pd.Timedelta(minutes=max(spec.expected))))
    base["missing_expected_minutes"] = pd.array(missing, dtype="Int64")
    base["session_type"] = session_types
    base["open_is_scheduled_first_minute"] = open_true
    base["close_is_scheduled_last_minute"] = close_true
    base["open_is_first_observed_minute"] = base.first_valid_timestamp.eq(base.first_timestamp)
    base["open_quality"] = np.where(base.valid_bars.eq(0), "NO_VALID_MINUTES",
        np.where(base.open_is_scheduled_first_minute, "SCHEDULED_FIRST_MINUTE", "LATER_OR_UNVERIFIED_OBSERVED_OPEN"))
    base["bar_available_at"] = base.last_timestamp + pd.Timedelta(minutes=1)
    for day in base.index:
        spec = specs[day]
        if spec.expected:
            end = pd.Timestamp(day, tz=config["timezone"]) + pd.Timedelta(minutes=max(spec.expected) + 1)
            base.loc[day, "bar_available_at"] = max(base.loc[day, "bar_available_at"], end)
    base["excluded_minutes"] = base.observed_bars - base.valid_bars
    base["symbol"] = symbol
    base["instrument_token"] = int(d.instrument_token.iloc[0])
    base["source_file"] = source_file
    base["source_price_basis"] = config["source_price_basis"]
    base["date"] = base.index.date
    base = base.reset_index(drop=True)
    excluded = d.loc[~good, REQUIRED].copy()
    reason = pd.Series("", index=d.index)
    for mask, label in [(identity, "PRELISTING_IDENTITY_CONTAMINATION"), (bad_ohlc, "INVALID_OHLC"),
                        (bad_other, "INVALID_VOLUME_OR_TIMESTAMP"), (duplicate, "DUPLICATE_TIMESTAMP"),
                        (outside, "OUTSIDE_KNOWN_SESSION")]:
        reason.loc[mask] += label + "|"
    excluded["exclusion_reason"] = reason.loc[~good].str.rstrip("|")
    excluded["source_file"] = source_file
    return base, excluded


def build_daily(files: list[dict], rules: SessionRules, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    bars, exclusions = [], []
    partitions = [f for f in files if f["kind"] == "ohlcv"]
    for number, record in enumerate(partitions, start=1):
        path = Path(record["path"])
        symbol = path.parent.parent.name.removeprefix("symbol=")
        frame = pq.ParquetFile(path).read().to_pandas()
        if frame.empty:
            raise ValueError(f"Empty partition: {path}")
        if frame.timestamp.dt.year.ne(int(path.parent.name.removeprefix("year="))).any():
            raise ValueError(f"Wrong partition year: {path}")
        daily, excluded = aggregate_minutes(frame, symbol, rules, config, str(path))
        bars.append(daily)
        if not excluded.empty:
            exclusions.append(excluded)
        if number % 70 == 0 or number == len(partitions):
            print(f"Aggregated {number}/{len(partitions)} yearly partitions", flush=True)
    result = pd.concat(bars, ignore_index=True).sort_values(["symbol", "date"]).reset_index(drop=True)
    if result.duplicated(["symbol", "date"]).any():
        raise ValueError("Overlapping symbol/date partitions")
    ex = pd.concat(exclusions, ignore_index=True) if exclusions else pd.DataFrame(
        columns=REQUIRED + ["exclusion_reason", "source_file"])
    return result, ex
