"""Chronological and influence validation of the accepted Phase-3 CSRS panel."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


def rank_average(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranked = np.empty(len(values), dtype=float)
    sorted_values = values[order]
    start = 0
    while start < len(values):
        stop = start + 1
        while stop < len(values) and sorted_values[stop] == sorted_values[start]:
            stop += 1
        ranked[order[start:stop]] = (start + 1 + stop) / 2
        start = stop
    return ranked


def correlation(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def deciles_from_order(order_values: np.ndarray) -> np.ndarray:
    ranks = rank_average(order_values)
    return np.floor((ranks - 1) * 10 / len(ranks)).astype(int) + 1


def daily_pair_statistics(panel: pd.DataFrame, formation: int, future: int) -> pd.DataFrame:
    valid = panel[f"valid_ret_{formation}"] & panel[f"valid_future_{future}"]
    cols = ["date", "symbol", f"csrs_rank_{formation}", f"future_ret_{future}",
            f"cross_section_count_{formation}"]
    rows = []
    for day, group in panel.loc[valid, cols].groupby("date", sort=True):
        factor = group[f"csrs_rank_{formation}"].to_numpy(float)
        outcome = group[f"future_ret_{future}"].to_numpy(float)
        decile = deciles_from_order(factor) if len(group) >= 10 else np.zeros(len(group), dtype=int)
        spread = (outcome[decile == 10].mean() - outcome[decile == 1].mean()
                  if len(group) >= 10 else np.nan)
        row = {"date": day, "ic": correlation(rank_average(factor), rank_average(outcome)),
               "daily_spread": spread,
               "observations": len(group), "cross_section_count": int(group.iloc[0, -1])}
        for q in range(1, 11):
            selected = outcome[decile == q]
            row[f"q{q}_sum"] = selected.sum()
            row[f"q{q}_count"] = len(selected)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_daily(daily: pd.DataFrame) -> dict[str, float | int]:
    if daily.empty:
        return {"mean_ic": np.nan, "median_ic": np.nan, "mean_daily_d10_d1_spread": np.nan,
                "pooled_d10_d1_spread": np.nan, "decile_monotonicity": np.nan,
                "valid_dates": 0, "observation_count": 0}
    means = []
    for q in range(1, 11):
        count = daily[f"q{q}_count"].sum()
        means.append(daily[f"q{q}_sum"].sum() / count if count else np.nan)
    pooled_spread = means[9] - means[0]
    monotonicity = correlation(np.arange(1, 11, dtype=float), rank_average(np.array(means)))
    return {"mean_ic": daily.ic.mean(), "median_ic": daily.ic.median(),
            "mean_daily_d10_d1_spread": daily.daily_spread.mean(),
            "pooled_d10_d1_spread": pooled_spread, "decile_monotonicity": monotonicity,
            "valid_dates": int(daily.ic.notna().sum()),
            "observation_count": int(daily.observations.sum())}


def build_daily_cache(panel: pd.DataFrame, formations: tuple[int, ...], futures: tuple[int, ...]) -> dict[tuple[int, int], pd.DataFrame]:
    return {(f, h): daily_pair_statistics(panel, f, h) for f in formations for h in futures}


def expanding_window(cache: dict, years: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for evaluation_year in years:
        for (f, h), daily in cache.items():
            train = daily[daily.date.map(lambda d: d.year < evaluation_year)]
            evaluation = daily[daily.date.map(lambda d: d.year == evaluation_year)]
            rows.append({"evaluation_year": evaluation_year, "history_end_year": evaluation_year - 1,
                         "formation_horizon": f, "future_horizon": h,
                         **{f"history_{k}": v for k, v in summarize_daily(train).items()},
                         **{f"evaluation_{k}": v for k, v in summarize_daily(evaluation).items()}})
    return pd.DataFrame(rows)


def fixed_periods(cache: dict, periods: list[dict]) -> pd.DataFrame:
    rows = []
    for period in periods:
        start, end = pd.Timestamp(period["start"]).date(), pd.Timestamp(period["end"]).date()
        for (f, h), daily in cache.items():
            selected = daily[daily.date.between(start, end)]
            rows.append({"period": period["name"], "calendar_start": start, "calendar_end": end,
                         "actual_first_date": selected.date.min(), "actual_last_date": selected.date.max(),
                         "formation_horizon": f, "future_horizon": h, **summarize_daily(selected)})
    return pd.DataFrame(rows)


def leave_one_year_out(cache: dict, years: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for omitted in years:
        for (f, h), daily in cache.items():
            selected = daily[daily.date.map(lambda d: d.year != omitted)]
            rows.append({"omitted_year": omitted, "formation_horizon": f, "future_horizon": h,
                         **summarize_daily(selected)})
    return pd.DataFrame(rows)


def nonoverlap(cache: dict, calendar_dates: list, futures: tuple[int, ...]) -> pd.DataFrame:
    position = {day: i for i, day in enumerate(calendar_dates)}
    rows = []
    for (f, h), daily in cache.items():
        offset_rows = []
        positions = daily.date.map(position).to_numpy()
        for offset in range(h):
            selected = daily[positions % h == offset]
            stats = summarize_daily(selected)
            row = {"formation_horizon": f, "future_horizon": h, "offset": offset, **stats}
            rows.append(row); offset_rows.append(row)
        frame = pd.DataFrame(offset_rows)
        for row in rows[-h:]:
            row["offset_mean_ic"] = frame.mean_ic.mean()
            row["offset_min_ic"] = frame.mean_ic.min()
            row["offset_max_ic"] = frame.mean_ic.max()
            row["offset_mean_spread"] = frame.mean_daily_d10_d1_spread.mean()
            row["offset_min_spread"] = frame.mean_daily_d10_d1_spread.min()
            row["offset_max_spread"] = frame.mean_daily_d10_d1_spread.max()
    return pd.DataFrame(rows)


def moving_block_bootstrap(values: np.ndarray, block_length: int, replications: int,
                           seed: int, confidence: float) -> tuple[float, float, float]:
    values = values[np.isfinite(values)]
    n = len(values)
    if n == 0:
        return np.nan, np.nan, np.nan
    length = min(block_length, n)
    blocks = math.ceil(n / length)
    rng = np.random.default_rng(seed)
    means = np.empty(replications)
    offsets = np.arange(length)
    for i in range(replications):
        starts = rng.integers(0, n, size=blocks)
        indices = ((starts[:, None] + offsets) % n).ravel()[:n]
        means[i] = values[indices].mean()
    alpha = (1 - confidence) / 2
    return float(values.mean()), float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha))


def uncertainty_intervals(cache: dict, replications: int, seed: int, confidence: float) -> pd.DataFrame:
    rows = []
    for (f, h), daily in cache.items():
        block = max(10, 2 * h)
        for index, (stat, column) in enumerate((("MEAN_RANK_IC", "ic"), ("MEAN_DAILY_D10_D1_SPREAD", "daily_spread"))):
            estimate, lower, upper = moving_block_bootstrap(
                daily[column].to_numpy(float), block, replications, seed + f * 1000 + h * 10 + index, confidence)
            rows.append({"formation_horizon": f, "future_horizon": h, "statistic": stat,
                         "estimate": estimate, "ci_lower": lower, "ci_upper": upper,
                         "confidence_level": confidence, "block_length_sessions": block,
                         "replications": replications, "seed": seed + f * 1000 + h * 10 + index,
                         "method": "CIRCULAR_MOVING_BLOCK_BOOTSTRAP_DAILY_STATISTIC",
                         "valid_dates": int(daily[column].notna().sum())})
    return pd.DataFrame(rows)


def year_stability(cache: dict, years: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for (f, h), daily in cache.items():
        yearly = []
        for year in years:
            stats = summarize_daily(daily[daily.date.map(lambda d: d.year == year)])
            yearly.append((year, stats["mean_ic"], stats["mean_daily_d10_d1_spread"], stats["valid_dates"]))
        frame = pd.DataFrame(yearly, columns=["year", "ic", "spread", "dates"]).dropna(subset=["ic"])
        best_ic, worst_ic = frame.loc[frame.ic.idxmax()], frame.loc[frame.ic.idxmin()]
        best_spread, worst_spread = frame.loc[frame.spread.idxmax()], frame.loc[frame.spread.idxmin()]
        rows.append({"formation_horizon": f, "future_horizon": h,
                     "positive_ic_years": int(frame.ic.gt(0).sum()), "negative_ic_years": int(frame.ic.lt(0).sum()),
                     "ic_positive_fraction": frame.ic.gt(0).mean(), "median_yearly_ic": frame.ic.median(),
                     "yearly_ic_std": frame.ic.std(ddof=1), "best_ic_year": int(best_ic.year), "best_year_ic": best_ic.ic,
                     "worst_ic_year": int(worst_ic.year), "worst_year_ic": worst_ic.ic,
                     "positive_spread_years": int(frame.spread.gt(0).sum()),
                     "negative_spread_years": int(frame.spread.lt(0).sum()),
                     "spread_positive_fraction": frame.spread.gt(0).mean(),
                     "median_yearly_spread": frame.spread.median(), "yearly_spread_std": frame.spread.std(ddof=1),
                     "best_spread_year": int(best_spread.year), "best_year_spread": best_spread.spread,
                     "worst_spread_year": int(worst_spread.year), "worst_year_spread": worst_spread.spread,
                     "years_available": len(frame), "summed_valid_dates": int(frame.dates.sum())})
    return pd.DataFrame(rows)


def cross_section_sensitivity(cache: dict, thresholds: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for (f, h), daily in cache.items():
        baseline = summarize_daily(daily)
        for threshold in thresholds:
            selected = daily if threshold == 0 else daily[daily.cross_section_count >= threshold]
            stats = summarize_daily(selected)
            rows.append({"formation_horizon": f, "future_horizon": h, "minimum_cross_section": threshold,
                         "removed_dates": baseline["valid_dates"] - stats["valid_dates"], **stats,
                         "mean_ic_change": stats["mean_ic"] - baseline["mean_ic"],
                         "mean_daily_spread_change": stats["mean_daily_d10_d1_spread"] - baseline["mean_daily_d10_d1_spread"],
                         "factor_reranked": False})
    return pd.DataFrame(rows)


def subset_daily_statistics(panel: pd.DataFrame, formation: int, future: int,
                            symbols: set[str]) -> pd.DataFrame:
    return daily_pair_statistics(panel[panel.symbol.isin(symbols)], formation, future)


def coverage_quality_sensitivity(panel: pd.DataFrame, formations: tuple[int, ...], futures: tuple[int, ...],
                                 bands: dict) -> pd.DataFrame:
    rows = []
    observed = panel.groupby("symbol").size()
    for f in formations:
        retained = 100 * panel.groupby("symbol")[f"valid_ret_{f}"].sum() / observed
        low = float(retained.quantile(bands["low_quantile"]))
        high = float(retained.quantile(bands["high_quantile"]))
        labels = bands["labels"]
        selections = ((labels[0], retained <= low),
                      (labels[1], (retained > low) & (retained < high)),
                      (labels[2], retained >= high))
        for name, selection in selections:
            symbols = set(retained[selection].index)
            for h in futures:
                stats = summarize_daily(subset_daily_statistics(panel, f, h, symbols)) if symbols else summarize_daily(pd.DataFrame())
                rows.append({"formation_horizon": f, "future_horizon": h, "coverage_band": name,
                             "lower_quartile_boundary_pct": low, "upper_quartile_boundary_pct": high,
                             "symbol_count": len(symbols), "symbols": "|".join(sorted(symbols)), **stats})
    return pd.DataFrame(rows)


def deletion_statistics(group: pd.DataFrame, factor_col: str, outcome_col: str) -> tuple[np.ndarray, np.ndarray]:
    """Exact daily Spearman and re-deciled spread after deleting each row."""
    factor = group[factor_col].to_numpy(float)
    outcome = group[outcome_col].to_numpy(float)
    n = len(group)
    if n < 3:
        return np.full(n, np.nan), np.full(n, np.nan)
    x = rank_average(factor); y = rank_average(outcome)
    xp = np.broadcast_to(x, (n, n)).copy() - (x[None, :] > x[:, None])
    yp = np.broadcast_to(y, (n, n)).copy()
    yp -= (outcome[None, :] > outcome[:, None])
    yp -= 0.5 * ((outcome[None, :] == outcome[:, None]) & (~np.eye(n, dtype=bool)))
    mask = ~np.eye(n, dtype=bool)
    xp[~mask] = np.nan; yp[~mask] = np.nan
    xm = np.nanmean(xp, axis=1); ym = np.nanmean(yp, axis=1)
    covariance = np.nansum((xp - xm[:, None]) * (yp - ym[:, None]), axis=1)
    denominator = np.sqrt(np.nansum((xp - xm[:, None]) ** 2, axis=1) *
                          np.nansum((yp - ym[:, None]) ** 2, axis=1))
    ic = np.divide(covariance, denominator, out=np.full(n, np.nan), where=denominator > 0)
    if n < 11:
        return ic, np.full(n, np.nan)
    ranks_after = xp
    deciles = np.floor((ranks_after - 1) * 10 / (n - 1)) + 1
    outcome_matrix = np.broadcast_to(outcome, (n, n)).copy(); outcome_matrix[~mask] = np.nan
    top = np.nanmean(np.where(deciles == 10, outcome_matrix, np.nan), axis=1)
    bottom = np.nanmean(np.where(deciles == 1, outcome_matrix, np.nan), axis=1)
    return ic, top - bottom


def leave_one_symbol_out(panel: pd.DataFrame, cache: dict, formations: tuple[int, ...], futures: tuple[int, ...]) -> pd.DataFrame:
    all_symbols = sorted(panel.symbol.unique())
    rows = []
    for f in formations:
        for h in futures:
            valid = panel[f"valid_ret_{f}"] & panel[f"valid_future_{h}"]
            work = panel.loc[valid, ["date", "symbol", f"csrs_rank_{f}", f"future_ret_{h}"]]
            ic_sum = dict.fromkeys(all_symbols, 0.0); ic_count = dict.fromkeys(all_symbols, 0)
            spread_sum = dict.fromkeys(all_symbols, 0.0); spread_count = dict.fromkeys(all_symbols, 0)
            for _, group in work.groupby("date", sort=True):
                ic, spread = deletion_statistics(group, f"csrs_rank_{f}", f"future_ret_{h}")
                for symbol, iv, sv in zip(group.symbol, ic, spread):
                    if np.isfinite(iv): ic_sum[symbol] += iv; ic_count[symbol] += 1
                    if np.isfinite(sv): spread_sum[symbol] += sv; spread_count[symbol] += 1
            base = summarize_daily(cache[(f, h)])
            total_ic_sum = cache[(f, h)].ic.sum(); total_dates = cache[(f, h)].ic.notna().sum()
            total_spread_sum = cache[(f, h)].daily_spread.sum(); total_spread_dates = cache[(f, h)].daily_spread.notna().sum()
            for symbol in all_symbols:
                # Dates without the symbol retain their baseline statistic; dates
                # with it use the exact delete-one value computed above.
                symbol_dates = work.loc[work.symbol.eq(symbol), "date"]
                old = cache[(f, h)].set_index("date").reindex(symbol_dates)
                ic_denominator = total_dates - old.ic.notna().sum() + ic_count[symbol]
                spread_denominator = total_spread_dates - old.daily_spread.notna().sum() + spread_count[symbol]
                new_ic = (total_ic_sum - old.ic.sum() + ic_sum[symbol]) / ic_denominator
                new_spread = ((total_spread_sum - old.daily_spread.sum() + spread_sum[symbol]) /
                              spread_denominator if spread_denominator else np.nan)
                rows.append({"formation_horizon": f, "future_horizon": h, "excluded_symbol": symbol,
                             "baseline_mean_ic": base["mean_ic"], "excluded_mean_ic": new_ic,
                             "mean_ic_change": new_ic - base["mean_ic"],
                             "baseline_mean_daily_spread": base["mean_daily_d10_d1_spread"],
                             "excluded_mean_daily_spread": new_spread,
                             "mean_daily_spread_change": new_spread - base["mean_daily_d10_d1_spread"],
                             "symbol_present_dates": len(symbol_dates), "removed_only_intended_symbol": True})
    return pd.DataFrame(rows)


def sector_influence(panel: pd.DataFrame, universe: pd.DataFrame, cache: dict,
                     formations: tuple[int, ...], futures: tuple[int, ...]) -> pd.DataFrame:
    unique = universe[universe.sector_mapping_status.eq("UNIQUE")]
    sectors = {sector: set(group.symbol) for sector, group in unique.groupby("sector", sort=True)}
    all_symbols = set(panel.symbol.unique())
    rows = []
    for sector, excluded in sectors.items():
        retained = all_symbols - excluded
        for f in formations:
            for h in futures:
                base = summarize_daily(cache[(f, h)])
                stats = summarize_daily(subset_daily_statistics(panel, f, h, retained))
                rows.append({"formation_horizon": f, "future_horizon": h, "excluded_sector": sector,
                             "excluded_symbol_count": len(excluded), "excluded_symbols": "|".join(sorted(excluded)),
                             "baseline_mean_ic": base["mean_ic"], "excluded_mean_ic": stats["mean_ic"],
                             "mean_ic_change": stats["mean_ic"] - base["mean_ic"],
                             "baseline_mean_daily_spread": base["mean_daily_d10_d1_spread"],
                             "excluded_mean_daily_spread": stats["mean_daily_d10_d1_spread"],
                             "mean_daily_spread_change": stats["mean_daily_d10_d1_spread"] - base["mean_daily_d10_d1_spread"],
                             "valid_dates": stats["valid_dates"], "mapping_status_used": "UNIQUE_ONLY"})
    return pd.DataFrame(rows)


def classify_formations(full_summary: pd.DataFrame, fixed: pd.DataFrame, stability: pd.DataFrame,
                        uncertainty: pd.DataFrame, nonoverlap_frame: pd.DataFrame,
                        formations: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for f in formations:
        full = full_summary[full_summary.formation_horizon.eq(f)]
        holdout = fixed[(fixed.formation_horizon.eq(f)) & fixed.period.eq("OUT_OF_SAMPLE_HOLDOUT")]
        stable = stability[stability.formation_horizon.eq(f)]
        ci = uncertainty[(uncertainty.formation_horizon.eq(f)) & uncertainty.statistic.eq("MEAN_RANK_IC")]
        non = nonoverlap_frame[nonoverlap_frame.formation_horizon.eq(f)].drop_duplicates("future_horizon")
        full_pos = int(full.mean_ic.gt(0).sum()); hold_pos = int(holdout.mean_ic.gt(0).sum())
        full_neg = int(full.mean_ic.lt(0).sum()); hold_neg = int(holdout.mean_ic.lt(0).sum())
        year_majority = int(stable.ic_positive_fraction.ge(0.5).sum())
        positive_ci = int(ci.ci_lower.gt(0).sum()); negative_ci = int(ci.ci_upper.lt(0).sum())
        non_pos = int(non.offset_mean_ic.gt(0).sum()); non_neg = int(non.offset_mean_ic.lt(0).sum())
        if full_pos >= 5 and hold_pos >= 5 and year_majority >= 5 and positive_ci >= 4:
            label = "ROBUST"
        elif full_neg >= 5 and hold_neg >= 4 and non_neg >= 5:
            label = "REVERSAL-LIKE"
        elif full_pos >= 4 and hold_pos >= 4:
            label = "PROMISING BUT UNSTABLE"
        elif max(full_pos, full_neg, hold_pos, hold_neg) < 4:
            label = "NO EVIDENCE"
        else:
            label = "INCONCLUSIVE"
        rows.append({"formation_horizon": f, "classification": label,
                     "positive_full_pairs": full_pos, "negative_full_pairs": full_neg,
                     "positive_holdout_pairs": hold_pos, "negative_holdout_pairs": hold_neg,
                     "pairs_with_positive_year_majority": year_majority,
                     "positive_ic_confidence_intervals": positive_ci,
                     "negative_ic_confidence_intervals": negative_ci,
                     "positive_nonoverlap_pair_means": non_pos, "negative_nonoverlap_pair_means": non_neg,
                     "holdout_mean_ic_across_outcomes": holdout.mean_ic.mean(),
                     "holdout_mean_daily_spread_across_outcomes": holdout.mean_daily_d10_d1_spread.mean()})
    return pd.DataFrame(rows)
