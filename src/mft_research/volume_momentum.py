"""Outcome-blind Volume + Momentum foundation research."""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from mft_research.csrs.phase5 import blocking_event_map, interval_crosses

VOLUME_BASELINES = (20, 60)
PRICE_HORIZONS = (5, 20)
UNIVERSES = ("BROAD_EQ", "BASIC_LIQUID", "MODERATE_LIQUID", "STRICT_SENSITIVITY")
PRIMARY_UNIVERSE = "BASIC_LIQUID"
SENSITIVITY_UNIVERSE = "MODERATE_LIQUID"
CANDIDATE_IDS = tuple(f"VM{i:02d}" for i in range(1, 8))
FORBIDDEN = ("future_", "outcome", "pnl", "portfolio", "sharpe", "hit_rate", "sector_momentum", "csrs")


def validate_config(config: dict) -> None:
    assert tuple(config["volume_baseline_horizons"]) == VOLUME_BASELINES
    assert tuple(config["price_return_horizons"]) == PRICE_HORIZONS
    assert tuple(config["audit_universes"]) == UNIVERSES
    assert config["primary_universe"] == PRIMARY_UNIVERSE
    assert config["sensitivity_universe"] == SENSITIVITY_UNIVERSE
    assert config["baseline_current_day_policy"] == "exclude_current_day"
    assert config["candidate_count_limits"] == [4, 8]


def _reason(valid: pd.Series, conditions: list[tuple[pd.Series, str]]) -> pd.Series:
    reason = pd.Series("", index=valid.index, dtype="string")
    unresolved = ~valid
    for condition, label in conditions:
        selected = unresolved & condition & reason.eq("")
        reason.loc[selected] = label
    reason.loc[unresolved & reason.eq("")] = "OTHER_UNSAFE_INTERVAL"
    return reason


def _rank(frame: pd.DataFrame, value: str, mask: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    work = frame.loc[mask & frame[value].notna(), ["date", "symbol", value]].copy()
    work = work.sort_values(["date", value, "symbol"], kind="stable")
    work["_rank"] = work.groupby("date", sort=False).cumcount() + 1
    work["_count"] = work.groupby("date", sort=False).symbol.transform("size")
    work["_pct"] = np.where(work._count.gt(1), (work._rank - 1) / (work._count - 1), 1.0)
    rank = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    count = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    pct = pd.Series(np.nan, index=frame.index, dtype=float)
    rank.loc[work.index] = work._rank.astype("int64")
    count.loc[work.index] = work._count.astype("int64")
    pct.loc[work.index] = work._pct
    return rank, pct, count


def _winsor_same_date(frame: pd.DataFrame, value: str, mask: pd.Series,
                       lower: float, upper: float) -> pd.Series:
    selected = frame.loc[mask & frame[value].notna(), ["date", value]]
    if selected.empty:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    limits = selected.groupby("date", sort=False)[value].quantile([lower, upper]).unstack()
    lo = frame.date.map(limits[lower]); hi = frame.date.map(limits[upper])
    result = frame[value].clip(lo, hi)
    return result.where(mask & frame[value].notna())


def candidate_registry() -> pd.DataFrame:
    rows = [
        ("VM01", "PRICE_RETURN_5_CONTROL", "price_return_5", "price_return_5", "NONE", 0,
         "NONE", "DIRECTIONAL_PRICE", "NONE", 6,
         "Short-horizon price-move control isolates the price component.",
         "Not a CSRS rank and may contain reversal or continuation behavior.", "CONTROL_PRICE"),
        ("VM02", "PRICE_RETURN_20_CONTROL", "price_return_20", "price_return_20", "NONE", 0,
         "NONE", "DIRECTIONAL_PRICE", "NONE", 21,
         "One-month price-move control isolates the price component.",
         "Not a CSRS rank and may contain reversal or continuation behavior.", "CONTROL_PRICE"),
        ("VM03", "LOG_VOLUME_SURPRISE_20_CONTROL", "log_volume_surprise_20", "NONE",
         "log_volume_surprise_20", 20, "PRIOR_LOG_MEAN", "NON_DIRECTIONAL_VOLUME", "NONE", 21,
         "Log scaling controls the extreme right tail while retaining abnormal-volume ordering.",
         "Volume alone has no price direction and corporate actions can disturb the baseline.", "CONTROL_VOLUME"),
        ("VM04", "LOG_VOLUME_SURPRISE_60_CONTROL", "log_volume_surprise_60", "NONE",
         "log_volume_surprise_60", 60, "PRIOR_LOG_MEAN", "NON_DIRECTIONAL_VOLUME", "NONE", 61,
         "A longer prior-only baseline tests slower volume normalization without adding more horizons.",
         "Highly correlated with the 20-session volume control.", "CONTROL_VOLUME"),
        ("VM05", "PRICE5_X_HIGH_VOLUME20", "price_return_5 * max(winsor(log_volume_surprise_20), 0)",
         "price_return_5", "log_volume_surprise_20", 20, "PRIOR_LOG_MEAN", "SIGNED_BY_PRICE_MAGNITUDE",
         "SAME_DATE_1PCT_99PCT_VOLUME_COMPONENT", 21,
         "Tests whether above-baseline volume amplifies the magnitude and direction of a short price move.",
         "Multiplication can remain heavy-tailed and zeroes below-baseline volume intensity.", "INTERACTION"),
        ("VM06", "PRICE20_X_HIGH_VOLUME20", "price_return_20 * max(winsor(log_volume_surprise_20), 0)",
         "price_return_20", "log_volume_surprise_20", 20, "PRIOR_LOG_MEAN", "SIGNED_BY_PRICE_MAGNITUDE",
         "SAME_DATE_1PCT_99PCT_VOLUME_COMPONENT", 21,
         "Tests abnormal volume as an amplifier of a one-month price move.",
         "Price and volume windows overlap and the product can remain heavy-tailed.", "INTERACTION"),
        ("VM07", "SIGNED_HIGH_VOLUME20_60", "sign(price_return_20) * max(winsor(log_volume_surprise_60), 0)",
         "sign(price_return_20)", "log_volume_surprise_60", 60, "PRIOR_LOG_MEAN", "UP_VERSUS_DOWN",
         "SAME_DATE_1PCT_99PCT_VOLUME_COMPONENT", 61,
         "Longer-window directional abnormal volume contrasts with the short interaction.",
         "Discards price-move magnitude and uses a highly persistent volume baseline.", "INTERACTION"),
    ]
    columns = ["candidate_id", "name", "formula", "price_component", "volume_component",
               "baseline_horizon", "normalization", "directionality", "winsorization_rule",
               "required_history", "scientific_rationale", "known_limitation", "role"]
    result = pd.DataFrame(rows, columns=columns)
    result["cross_sectional_transformation"] = "PERCENTILE_RANK_SAME_DATE_WITHIN_SELECTED_UNIVERSE"
    result["primary_universe"] = PRIMARY_UNIVERSE
    result["sensitivity_universe"] = SENSITIVITY_UNIVERSE
    return result


def build_foundation(daily: pd.DataFrame, actions: pd.DataFrame, config: dict) -> pd.DataFrame:
    validate_config(config)
    columns = ["date", "symbol", "source_format", "source_file", "session_position",
               "first_observed_date", "history_sessions", "close", "volume", "turnover_rupees",
               "research_quality_status", "corporate_action_status", "corporate_action_coverage_status",
               "universe_broad_eq", "universe_basic_liquid", "universe_moderate_liquid",
               "universe_strict_sensitivity"]
    frame = daily[columns].copy().sort_values(["symbol", "date"], kind="stable").reset_index(drop=True)
    for column in ("session_position", "history_sessions", "close", "volume", "turnover_rupees"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    grouped = frame.groupby("symbol", sort=False)
    events = blocking_event_map(actions, {"corporate_action_policy": {
        "primary_blocking_impacts": config["corporate_action_blocking_impacts"]}})
    coverage_start = pd.Timestamp(config["corporate_action_coverage_start"]).date()
    coverage_end = pd.Timestamp(config["corporate_action_coverage_end"]).date()
    quality = frame.research_quality_status.eq("VALID_REPORTED_EQ_ROW")
    nonnegative = frame.volume.notna() & frame.volume.ge(0)
    frame["zero_volume_observation"] = frame.volume.eq(0)
    frame["negative_volume_observation"] = frame.volume.lt(0)
    frame["missing_volume_observation"] = frame.volume.isna()
    log_volume = np.log1p(frame.volume.astype(float).where(nonnegative))

    for horizon in VOLUME_BASELINES:
        shifted_volume = grouped.volume.shift(1)
        prior_log = log_volume.groupby(frame.symbol, sort=False).shift(1)
        prior_quality = quality.groupby(frame.symbol, sort=False).shift(1)
        start_date = grouped.date.shift(horizon)
        start_position = grouped.session_position.shift(horizon)
        contiguous = (frame.session_position - start_position).eq(horizon)
        prior_quality_count = (prior_quality.groupby(frame.symbol, sort=False)
                               .rolling(horizon, min_periods=horizon).sum().reset_index(level=0, drop=True))
        mean = (shifted_volume.groupby(frame.symbol, sort=False).rolling(horizon, min_periods=horizon)
                .mean().reset_index(level=0, drop=True))
        median = (shifted_volume.groupby(frame.symbol, sort=False).rolling(horizon, min_periods=horizon)
                  .median().reset_index(level=0, drop=True))
        log_mean = (prior_log.groupby(frame.symbol, sort=False).rolling(horizon, min_periods=horizon)
                    .mean().reset_index(level=0, drop=True))
        crossing = interval_crosses(frame.symbol, start_date, frame.date, events)
        coverage = start_date.ge(coverage_start) & frame.date.le(coverage_end)
        valid = (quality & nonnegative & mean.gt(0) & median.gt(0) & log_mean.notna() & contiguous &
                 prior_quality_count.eq(horizon) & ~crossing & coverage)
        frame[f"volume_mean_{horizon}_prior"] = mean
        frame[f"volume_median_{horizon}_prior"] = median
        frame[f"volume_log_mean_{horizon}_prior"] = log_mean
        frame[f"valid_volume_baseline_{horizon}"] = valid
        frame[f"volume_baseline_{horizon}_invalid_reason"] = _reason(valid, [
            (frame.volume.isna(), "UNAVAILABLE_SOURCE_VOLUME"),
            (frame.volume.lt(0), "NEGATIVE_VOLUME"),
            (~quality, "INVALID_SOURCE_ROW"),
            (start_date.isna(), "INSUFFICIENT_HISTORY"),
            (~contiguous & start_date.notna(), "MISSING_OR_UNSAFE_SESSION_INTERVAL"),
            (prior_quality_count.ne(horizon) & start_date.notna(), "UNSAFE_PRIOR_OBSERVATION"),
            (pd.Series(crossing, index=frame.index), "CORPORATE_ACTION_INTERVAL"),
            (~coverage & start_date.notna(), "CORPORATE_ACTION_COVERAGE_UNCERTIFIED"),
            (mean.le(0) | median.le(0), "ZERO_PRIOR_VOLUME_BASELINE"),
        ])
        frame[f"volume_ratio_{horizon}"] = (frame.volume / mean).where(valid)
        frame[f"volume_median_ratio_{horizon}"] = (frame.volume / median).where(valid)
        frame[f"log_volume_surprise_{horizon}"] = (log_volume - log_mean).where(valid)

    for horizon in PRICE_HORIZONS:
        start_close = grouped.close.shift(horizon)
        start_date = grouped.date.shift(horizon)
        start_position = grouped.session_position.shift(horizon)
        interval_quality = (quality.groupby(frame.symbol, sort=False).rolling(horizon + 1, min_periods=horizon + 1)
                            .sum().reset_index(level=0, drop=True))
        contiguous = (frame.session_position - start_position).eq(horizon)
        crossing = interval_crosses(frame.symbol, start_date, frame.date, events)
        coverage = start_date.ge(coverage_start) & frame.date.le(coverage_end)
        valid = (quality & start_close.gt(0) & contiguous & interval_quality.eq(horizon + 1) &
                 ~crossing & coverage)
        frame[f"valid_price_return_{horizon}"] = valid
        frame[f"price_return_{horizon}_invalid_reason"] = _reason(valid, [
            (~quality, "INVALID_SOURCE_ROW"),
            (start_date.isna(), "INSUFFICIENT_HISTORY"),
            (~contiguous & start_date.notna(), "MISSING_OR_UNSAFE_SESSION_INTERVAL"),
            (interval_quality.ne(horizon + 1) & start_date.notna(), "UNSAFE_PRIOR_OBSERVATION"),
            (pd.Series(crossing, index=frame.index), "CORPORATE_ACTION_INTERVAL"),
            (~coverage & start_date.notna(), "CORPORATE_ACTION_COVERAGE_UNCERTIFIED"),
            (start_close.le(0), "INVALID_PRICE_ENDPOINT"),
        ])
        frame[f"price_return_{horizon}"] = (frame.close / start_close - 1).where(valid)

    lower, upper = map(float, config["cross_sectional_winsorization"])
    universe_columns = {name: f"universe_{name.lower()}" for name in UNIVERSES}
    for horizon in VOLUME_BASELINES:
        value = f"log_volume_surprise_{horizon}"
        for name, universe_column in universe_columns.items():
            suffix = name.lower()
            mask = frame[universe_column].fillna(False) & frame[f"valid_volume_baseline_{horizon}"]
            rank, pct, count = _rank(frame, value, mask)
            frame[f"log_volume_surprise_{horizon}_rank_{suffix}"] = rank
            frame[f"log_volume_surprise_{horizon}_pct_{suffix}"] = pct
            frame[f"log_volume_surprise_{horizon}_count_{suffix}"] = count
        for name in (PRIMARY_UNIVERSE, SENSITIVITY_UNIVERSE):
            suffix = name.lower(); universe_column = universe_columns[name]
            mask = frame[universe_column].fillna(False) & frame[f"valid_volume_baseline_{horizon}"]
            frame[f"log_volume_surprise_{horizon}_winsor_{suffix}"] = _winsor_same_date(
                frame, value, mask, lower, upper)

    # Independent controls are retained exactly. Interaction values are built separately for
    # primary and sensitivity universes because winsorization is contemporaneous and universe-specific.
    frame["candidate_vm01"] = frame.price_return_5
    frame["candidate_vm02"] = frame.price_return_20
    frame["candidate_vm03"] = frame.log_volume_surprise_20
    frame["candidate_vm04"] = frame.log_volume_surprise_60
    for name in (PRIMARY_UNIVERSE, SENSITIVITY_UNIVERSE):
        suffix = name.lower(); eligible = frame[f"universe_{suffix}"].fillna(False)
        v20 = frame[f"log_volume_surprise_20_winsor_{suffix}"].clip(lower=0)
        v60 = frame[f"log_volume_surprise_60_winsor_{suffix}"].clip(lower=0)
        frame[f"candidate_vm05_{suffix}"] = (frame.price_return_5 * v20).where(eligible)
        frame[f"candidate_vm06_{suffix}"] = (frame.price_return_20 * v20).where(eligible)
        frame[f"candidate_vm07_{suffix}"] = (np.sign(frame.price_return_20) * v60).where(eligible)
        sources = {"vm01": "candidate_vm01", "vm02": "candidate_vm02", "vm03": "candidate_vm03",
                   "vm04": "candidate_vm04", "vm05": f"candidate_vm05_{suffix}",
                   "vm06": f"candidate_vm06_{suffix}", "vm07": f"candidate_vm07_{suffix}"}
        for key, value in sources.items():
            mask = eligible & frame[value].notna()
            rank, pct, count = _rank(frame, value, mask)
            frame[f"candidate_{key}_rank_{suffix}"] = rank
            frame[f"candidate_{key}_pct_{suffix}"] = pct
            frame[f"candidate_{key}_count_{suffix}"] = count

    return frame.sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def distribution(values: pd.Series) -> dict:
    values = pd.to_numeric(values, errors="coerce").dropna().astype(float)
    if values.empty:
        return {key: np.nan for key in ("count", "mean", "median", "std", "p01", "p05", "p10",
                                                  "p25", "p75", "p90", "p95", "p99", "min", "max", "skew")}
    q = values.quantile([.01, .05, .10, .25, .75, .90, .95, .99])
    return {"count": len(values), "mean": values.mean(), "median": values.median(), "std": values.std(),
            "p01": q.loc[.01], "p05": q.loc[.05], "p10": q.loc[.10], "p25": q.loc[.25],
            "p75": q.loc[.75], "p90": q.loc[.90], "p95": q.loc[.95], "p99": q.loc[.99],
            "min": values.min(), "max": values.max(), "skew": values.skew()}


def feature_correlations(panel: pd.DataFrame, features: list[str], universe_column: str) -> pd.DataFrame:
    rows = []
    base = panel[panel[universe_column].fillna(False)]
    for year, subset in [("ALL", base), *[(str(year), group) for year, group in base.groupby(pd.to_datetime(base.date).dt.year)]]:
        for left, right in combinations(features, 2):
            pair = subset[[left, right]].dropna()
            ranked = pair.rank(method="average")
            rows.append({"year": year, "feature_left": left, "feature_right": right,
                         "observations": len(pair), "pearson": pair[left].corr(pair[right]),
                         "spearman": ranked[left].corr(ranked[right])})
    return pd.DataFrame(rows)


def assert_outcome_blind(frame: pd.DataFrame) -> None:
    prohibited = [column for column in frame.columns if any(token in column.lower() for token in FORBIDDEN)]
    if prohibited:
        raise AssertionError(f"Outcome/trading/other-factor columns are prohibited in Phase 8: {prohibited}")
