"""Independent CSRS rankings for each approved formation horizon."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rank_one_date(rows: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """Unique ordinal: weaker first; exact ties break by symbol ascending."""
    ranked = rows.sort_values([value_col, "symbol"], kind="stable").copy()
    count = len(ranked)
    ranked["_rank"] = np.arange(1, count + 1, dtype=np.int64)
    ranked["_pct"] = (ranked._rank - 1) / (count - 1) if count > 1 else 0.5
    ranked["_count"] = count
    return ranked


def add_cross_sectional_ranks(panel: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    result = panel.copy()
    for horizon in horizons:
        valid = result[f"valid_ret_{horizon}"]
        ranked_parts = [rank_one_date(rows, f"ret_{horizon}")
                        for _, rows in result.loc[valid, ["date", "symbol", f"ret_{horizon}"]].groupby("date", sort=True)]
        ranks = pd.concat(ranked_parts).sort_index() if ranked_parts else pd.DataFrame()
        result[f"csrs_rank_{horizon}"] = pd.array([pd.NA] * len(result), dtype="Int64")
        result[f"csrs_pct_{horizon}"] = np.nan
        result[f"cross_section_count_{horizon}"] = pd.array([pd.NA] * len(result), dtype="Int64")
        if not ranks.empty:
            result.loc[ranks.index, f"csrs_rank_{horizon}"] = pd.array(ranks._rank, dtype="Int64")
            result.loc[ranks.index, f"csrs_pct_{horizon}"] = ranks._pct
            result.loc[ranks.index, f"cross_section_count_{horizon}"] = pd.array(ranks._count, dtype="Int64")
    return result


def assign_deciles(frame: pd.DataFrame, rank_col: str, count_col: str, minimum: int = 10) -> pd.Series:
    result = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    valid = frame[rank_col].notna() & frame[count_col].ge(minimum)
    result.loc[valid] = (((frame.loc[valid, rank_col].astype(int) - 1) * 10
                          // frame.loc[valid, count_col].astype(int)) + 1).astype("Int64")
    return result


def side_masks(frame: pd.DataFrame, rank_col: str, count_col: str, fraction: float) -> tuple[pd.Series, pd.Series]:
    count = frame[count_col].astype("Int64")
    k = np.ceil(count.astype(float) * fraction)
    valid = frame[rank_col].notna() & count.notna()
    bottom = valid & frame[rank_col].astype("Int64").le(pd.Series(k, index=frame.index).astype("Int64"))
    top = valid & frame[rank_col].astype("Int64").gt(count - pd.Series(k, index=frame.index).astype("Int64"))
    return top.fillna(False), bottom.fillna(False)
