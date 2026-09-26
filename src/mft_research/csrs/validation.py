"""Acceptance checks for the derived CSRS factor panel."""

from __future__ import annotations

import numpy as np
import pandas as pd


def validate_factor_panel(
    panel: pd.DataFrame,
    formation_horizons: tuple[int, ...],
    future_horizons: tuple[int, ...],
    coverage_cutoff: str,
) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []

    def record(name: str, passed: bool, detail: object) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    record("panel_row_count_matches_phase2", len(panel) == 188_451, len(panel))
    record("canonical_symbol_count", panel.symbol.nunique() == 120, panel.symbol.nunique())
    duplicate_count = int(panel.duplicated(["symbol", "date"]).sum())
    record("unique_symbol_date", duplicate_count == 0, duplicate_count)
    ordered = panel.sort_values(["date", "symbol"], kind="mergesort").index.equals(panel.index)
    record("deterministic_row_order", ordered, "date,symbol")
    forbidden = [column for column in panel if "weighted" in column.lower() or "combined" in column.lower()]
    record("no_combined_or_weighted_csrs", not forbidden, forbidden)

    cutoff = pd.Timestamp(coverage_cutoff).date()
    for horizon in formation_horizons:
        valid = panel[f"valid_ret_{horizon}"]
        values = panel[f"ret_{horizon}"]
        ranks = panel[f"csrs_rank_{horizon}"]
        pct = panel[f"csrs_pct_{horizon}"]
        counts = panel[f"cross_section_count_{horizon}"]
        record(f"formation_{horizon}_valid_has_values", values[valid].notna().all(), int(valid.sum()))
        record(f"formation_{horizon}_invalid_is_null", values[~valid].isna().all(), int((~valid).sum()))
        record(f"formation_{horizon}_rank_only_when_valid", ranks.notna().equals(valid), int(ranks.notna().sum()))
        bounds = pct[valid].between(0.0, 1.0).all()
        record(f"formation_{horizon}_percentile_bounds", bounds,
               [float(pct[valid].min()), float(pct[valid].max())])
        expected = panel.loc[valid].groupby("date")["symbol"].transform("size")
        count_match = (counts[valid].astype(int).to_numpy() == expected.to_numpy()).all()
        record(f"formation_{horizon}_cross_section_counts", count_match,
               int(panel.loc[valid, "date"].nunique()))
        cutoff_ok = not panel.loc[panel.date > cutoff, f"valid_ret_{horizon}"].any()
        record(f"formation_{horizon}_coverage_cutoff", cutoff_ok, coverage_cutoff)

    for horizon in future_horizons:
        valid = panel[f"valid_future_{horizon}"]
        values = panel[f"future_ret_{horizon}"]
        record(f"future_{horizon}_valid_has_values", values[valid].notna().all(), int(valid.sum()))
        record(f"future_{horizon}_invalid_is_null", values[~valid].isna().all(), int((~valid).sum()))

    return_columns = ([f"ret_{h}" for h in formation_horizons]
                      + [f"future_ret_{h}" for h in future_horizons])
    finite = all(np.isfinite(panel[column].dropna()).all() for column in return_columns)
    record("all_derived_returns_finite", finite, return_columns)
    return checks


def assert_acceptance(checks: list[dict[str, object]]) -> None:
    failures = [check for check in checks if not check["passed"]]
    if failures:
        names = ", ".join(str(check["check"]) for check in failures)
        raise AssertionError(f"CSRS panel acceptance failed: {names}")
