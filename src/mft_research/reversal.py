"""Preregistered stock-level cross-sectional reversal helpers for Phase 10."""

from __future__ import annotations

import numpy as np
import pandas as pd

CANDIDATES = ("REV05", "REV20")
FUTURES = (1, 2, 3, 5, 10, 20)
FORMULAS = {"REV05": ("price_return_5", -1.0), "REV20": ("price_return_20", -1.0)}
UNIVERSES = ("BASIC_LIQUID", "MODERATE_LIQUID")


def validate_registry(registry: pd.DataFrame, config: dict) -> None:
    if tuple(registry.candidate_id) != CANDIDATES or tuple(config["candidates"]) != CANDIDATES:
        raise ValueError("Phase-10 candidates must remain exactly REV05 and REV20")
    if tuple(config["future_horizons"]) != FUTURES:
        raise ValueError("Phase-10 outcomes changed")
    if (config["primary_universe"], config["sensitivity_universe"]) != UNIVERSES:
        raise ValueError("Phase-10 universe contract changed")
    expected = {candidate: f"-1 * {source}" for candidate, (source, _) in FORMULAS.items()}
    if config["candidate_formulas"] != expected:
        raise ValueError("Phase-10 formula changed")
    if dict(zip(registry.candidate_id, registry.formula)) != expected:
        raise ValueError("Registry formula changed")


def reversal_values(frame: pd.DataFrame, candidate: str) -> pd.Series:
    source, multiplier = FORMULAS[candidate]
    return multiplier * frame[source]


def rank_signal(frame: pd.DataFrame, value_column: str, signal_valid: pd.Series) -> pd.DataFrame:
    """Rank only the signal-valid same-date universe; outcome fields are irrelevant."""
    work = frame.loc[signal_valid & frame[value_column].notna(), ["date", "symbol", value_column]].copy()
    work = work.sort_values(["date", value_column, "symbol"], kind="stable")
    work["rank"] = work.groupby("date", sort=False).cumcount() + 1
    work["cross_section_count"] = work.groupby("date", sort=False).symbol.transform("size")
    work["percentile"] = np.where(work.cross_section_count.gt(1),
                                  (work["rank"] - 1) / (work.cross_section_count - 1), .5)
    return work.sort_index()


def attach_outcomes_after_ranking(ranked: pd.DataFrame, outcomes: pd.DataFrame,
                                  valid_column: str, return_column: str) -> pd.DataFrame:
    """Outcome availability filters already-fixed ranks and cannot change them."""
    result = ranked.join(outcomes[[valid_column, return_column]], how="left")
    return result.loc[result[valid_column].fillna(False)].copy()


def leave_one_date_out(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    baseline = daily.ic.mean()
    for day in sorted(daily.date.unique()):
        estimate = daily.loc[daily.date.ne(day), "ic"].mean()
        rows.append({"excluded_date": day, "baseline_mean_ic": baseline,
                     "leave_one_date_out_mean_ic": estimate,
                     "change": estimate - baseline,
                     "sign_flip": bool(np.sign(estimate) != np.sign(baseline))})
    return pd.DataFrame(rows)
