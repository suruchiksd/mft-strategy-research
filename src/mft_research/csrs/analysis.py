"""Descriptive CSRS outcome analysis; outcomes are labels, never portfolio P&L."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .factor import assign_deciles, side_masks


def spearman_manual(x: pd.Series, y: pd.Series) -> float:
    if len(x) < 2 or x.nunique() < 2 or y.nunique() < 2:
        return np.nan
    xr = x.rank(method="average").to_numpy(dtype=float)
    yr = y.rank(method="average").to_numpy(dtype=float)
    return float(np.corrcoef(xr, yr)[0, 1])


def rank_ic(panel: pd.DataFrame, formations: tuple[int, ...], futures: tuple[int, ...],
            minimum: int = 2) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for formation in formations:
        for future in futures:
            valid = panel[f"valid_ret_{formation}"] & panel[f"valid_future_{future}"]
            columns = ["date", f"csrs_pct_{formation}", f"future_ret_{future}"]
            for day, group in panel.loc[valid, columns].dropna().groupby("date", sort=True):
                n = len(group)
                rows.append({"date": day, "formation_horizon": formation, "future_horizon": future,
                             "cross_section_count": n,
                             "rank_ic": spearman_manual(group.iloc[:, 1], group.iloc[:, 2]) if n >= minimum else np.nan,
                             "minimum_cross_section": minimum})
    daily = pd.DataFrame(rows)
    summaries = []
    for (formation, future), group in daily.groupby(["formation_horizon", "future_horizon"], sort=True):
        values = group.rank_ic.dropna()
        n = len(values)
        std = values.std(ddof=1)
        summaries.append({"formation_horizon": formation, "future_horizon": future,
                          "mean_ic": values.mean(), "median_ic": values.median(), "ic_std": std,
                          "ic_positive_pct": 100 * values.gt(0).mean(), "ic_negative_pct": 100 * values.lt(0).mean(),
                          "valid_dates": n, "mean_over_std_ic": values.mean() / std if std > 0 else np.nan,
                          "naive_t_stat": values.mean() / (std / math.sqrt(n)) if std > 0 and n else np.nan,
                          "inference_warning": "naive_descriptive_only_overlapping_returns_and_serial_dependence"})
    return daily, pd.DataFrame(summaries)


def quantile_analysis(panel: pd.DataFrame, formations: tuple[int, ...], futures: tuple[int, ...],
                      minimum: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    results, horizon = [], []
    for formation in formations:
        deciles = assign_deciles(panel, f"csrs_rank_{formation}", f"cross_section_count_{formation}", minimum)
        for future in futures:
            valid = panel[f"valid_ret_{formation}"] & panel[f"valid_future_{future}"] & deciles.notna()
            work = pd.DataFrame({"decile": deciles[valid], "outcome": panel.loc[valid, f"future_ret_{future}"]})
            grouped = work.groupby("decile", sort=True).outcome
            decile_rows = []
            for decile, values in grouped:
                row = {"formation_horizon": formation, "future_horizon": future, "group": f"D{decile}",
                       "decile": int(decile), "observation_count": len(values),
                       "mean_future_return": values.mean(), "median_future_return": values.median(),
                       "std_future_return": values.std(ddof=1), "positive_return_pct": 100 * values.gt(0).mean(),
                       "minimum_cross_section": minimum}
                results.append(row); decile_rows.append(row)
            by_decile = pd.DataFrame(decile_rows).set_index("decile") if decile_rows else pd.DataFrame()
            if 1 in by_decile.index and 10 in by_decile.index:
                spread = by_decile.loc[10, "mean_future_return"] - by_decile.loc[1, "mean_future_return"]
                median_spread = by_decile.loc[10, "median_future_return"] - by_decile.loc[1, "median_future_return"]
                means = by_decile.mean_future_return.sort_index()
                monotonic_corr = spearman_manual(pd.Series(means.index), means.reset_index(drop=True))
                upward = int((means.diff().dropna() > 0).sum())
                results.append({"formation_horizon": formation, "future_horizon": future, "group": "D10-D1",
                                "decile": pd.NA, "observation_count": min(int(by_decile.loc[1, "observation_count"]), int(by_decile.loc[10, "observation_count"])),
                                "mean_future_return": spread, "median_future_return": median_spread,
                                "std_future_return": np.nan, "positive_return_pct": np.nan,
                                "minimum_cross_section": minimum})
                horizon.append({"formation_horizon": formation, "future_horizon": future,
                                "top_decile_mean_return": by_decile.loc[10, "mean_future_return"],
                                "bottom_decile_mean_return": by_decile.loc[1, "mean_future_return"],
                                "top_bottom_spread": spread, "decile_mean_spearman": monotonic_corr,
                                "upward_adjacent_decile_steps": upward, "possible_adjacent_steps": 9,
                                "decile_observations": len(work)})
    result = pd.DataFrame(results)
    result["decile"] = result.decile.astype("Int64")
    return result, pd.DataFrame(horizon)


def side_analysis(panel: pd.DataFrame, formations: tuple[int, ...], futures: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for formation in formations:
        for fraction in (0.05, 0.10, 0.20):
            top, bottom = side_masks(panel, f"csrs_rank_{formation}", f"cross_section_count_{formation}", fraction)
            for future in futures:
                outcome_valid = panel[f"valid_future_{future}"] & panel[f"valid_ret_{formation}"]
                stats = {}
                for name, mask in (("TOP", top), ("BOTTOM", bottom)):
                    values = panel.loc[outcome_valid & mask, f"future_ret_{future}"].dropna()
                    stats[name] = values.mean()
                    rows.append({"formation_horizon": formation, "future_horizon": future,
                                 "tail_fraction": fraction, "group": name,
                                 "observation_count": len(values), "mean_future_return": values.mean(),
                                 "median_future_return": values.median(),
                                 "positive_return_pct": 100 * values.gt(0).mean()})
                rows.append({"formation_horizon": formation, "future_horizon": future,
                             "tail_fraction": fraction, "group": "TOP-BOTTOM",
                             "observation_count": np.nan, "mean_future_return": stats["TOP"] - stats["BOTTOM"],
                             "median_future_return": np.nan, "positive_return_pct": np.nan})
    return pd.DataFrame(rows)


def yearly_analysis(panel: pd.DataFrame, ic_daily: pd.DataFrame, formations: tuple[int, ...],
                    futures: tuple[int, ...], minimum_decile: int = 10) -> pd.DataFrame:
    rows = []
    years = sorted({d.year for d in panel.date})
    for formation in formations:
        decile = assign_deciles(panel, f"csrs_rank_{formation}", f"cross_section_count_{formation}", minimum_decile)
        for future in futures:
            valid = panel[f"valid_ret_{formation}"] & panel[f"valid_future_{future}"] & decile.notna()
            for year in years:
                ic = ic_daily[(ic_daily.formation_horizon == formation) & (ic_daily.future_horizon == future)
                              & ic_daily.date.map(lambda d: d.year == year)].rank_ic.dropna()
                mask = valid & panel.date.map(lambda d: d.year == year)
                top = panel.loc[mask & decile.eq(10), f"future_ret_{future}"].dropna()
                bottom = panel.loc[mask & decile.eq(1), f"future_ret_{future}"].dropna()
                rows.append({"year": year, "period": f"{year}{' YTD' if year == max(years) else ''}",
                             "formation_horizon": formation, "future_horizon": future,
                             "mean_ic": ic.mean(), "median_ic": ic.median(),
                             "ic_positive_pct": 100 * ic.gt(0).mean() if len(ic) else np.nan,
                             "valid_ic_dates": len(ic), "valid_factor_outcome_observations": int(mask.sum()),
                             "top_decile_observations": len(top), "bottom_decile_observations": len(bottom),
                             "top_decile_mean_return": top.mean(), "bottom_decile_mean_return": bottom.mean(),
                             "top_bottom_spread": top.mean() - bottom.mean()})
    return pd.DataFrame(rows)


def coverage_tables(panel: pd.DataFrame, formations: tuple[int, ...], futures: tuple[int, ...],
                    focus_symbols: tuple[str, ...]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary, reasons, symbols = [], [], []
    specs = [("FORMATION", h, f"valid_ret_{h}", f"ret_{h}_invalid_reason") for h in formations]
    specs += [("FUTURE", h, f"valid_future_{h}", f"future_invalid_reason_{h}") for h in futures]
    for kind, horizon, valid_col, reason_col in specs:
        valid = panel[valid_col]
        valid_rows = panel[valid]
        summary.append({"interval_type": kind, "horizon_sessions": horizon, "total_rows": len(panel),
                        "valid_observations": int(valid.sum()), "invalid_observations": int((~valid).sum()),
                        "valid_pct": 100 * valid.mean(), "first_valid_date": valid_rows.date.min(),
                        "last_valid_date": valid_rows.date.max()})
        invalid = panel.loc[~valid, reason_col]
        exploded = invalid.str.split("|").explode()
        primary = invalid.str.split("|").str[0]
        for reason, count in exploded.value_counts().items():
            reasons.append({"interval_type": kind, "horizon_sessions": horizon, "reason": reason,
                            "reason_count_overlapping": int(count),
                            "primary_reason_count_exclusive": int(primary.eq(reason).sum())})
        for symbol in focus_symbols:
            mask = panel.symbol.eq(symbol)
            symbols.append({"symbol": symbol, "interval_type": kind, "horizon_sessions": horizon,
                            "observed_rows": int(mask.sum()), "valid_observations": int((mask & valid).sum()),
                            "invalid_observations": int((mask & ~valid).sum()),
                            "first_valid_date": panel.loc[mask & valid, "date"].min(),
                            "last_valid_date": panel.loc[mask & valid, "date"].max()})
    return pd.DataFrame(summary), pd.DataFrame(reasons), pd.DataFrame(symbols)


def cross_section_distribution(panel: pd.DataFrame, formations: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for h in formations:
        counts = panel.loc[panel[f"valid_ret_{h}"], ["date", f"cross_section_count_{h}"]].drop_duplicates().iloc[:, 1].astype(float)
        rows.append({"formation_horizon": h, "dates_with_valid_factor": len(counts), "minimum": counts.min(),
                     "p05": counts.quantile(.05), "median": counts.median(), "mean": counts.mean(),
                     "p95": counts.quantile(.95), "maximum": counts.max()})
    return pd.DataFrame(rows)


def combine_horizon_summary(ic: pd.DataFrame, quantile: pd.DataFrame) -> pd.DataFrame:
    return ic.merge(quantile, on=["formation_horizon", "future_horizon"], validate="one_to_one")
