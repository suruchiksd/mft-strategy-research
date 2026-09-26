"""Pure Sector Relative Momentum factor research.

Mappings are static/current and have no historical effective dates. This
module creates sector-level factor outcomes only; it contains no trading or
portfolio logic and does not combine factors.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pandas as pd

from mft_research.csrs.phase4 import correlation, deletion_statistics, moving_block_bootstrap, rank_average
from mft_research.csrs.phase5 import adjust_pvalues, interval_crosses

FORMATIONS = (5, 10, 20, 40, 60)
FUTURES = (1, 2, 3, 5, 10, 20)
MAPPING_TIERS = ("STABLE_IDENTITY_BASIC_LIQUID", "STABLE_IDENTITY_MODERATE_LIQUID",
                 "STABLE_IDENTITY_BROAD", "STATIC_UNIQUE_BROAD")
SIZE_THRESHOLDS = (3, 5, 10)
PRIMARY_TIER = "STABLE_IDENTITY_BASIC_LIQUID"
PRIMARY_SIZE = 5


def validate_config(config: dict) -> None:
    if tuple(config["formation_horizons"]) != FORMATIONS or tuple(config["future_horizons"]) != FUTURES:
        raise ValueError("Frozen Phase-7 horizon grid changed")
    if tuple(config["mapping_universe_tiers"]) != MAPPING_TIERS:
        raise ValueError("Frozen mapping/universe tiers changed")
    if tuple(config["sector_size_sensitivities"]) != SIZE_THRESHOLDS:
        raise ValueError("Frozen sector-size thresholds changed")
    if config["primary_tier"] != PRIMARY_TIER or config["primary_minimum_sector_size"] != PRIMARY_SIZE:
        raise ValueError("Primary tier or sector-size floor changed")
    if config["quintile_minimum_sector_count"] != 15:
        raise ValueError("Quintile feasibility threshold changed")


def blocking_event_map(actions: pd.DataFrame, phase5_config: dict) -> dict[str, np.ndarray]:
    impacts = set(phase5_config["corporate_action_policy"]["primary_blocking_impacts"])
    selected = actions[actions.series.eq("EQ") & actions.research_impact.isin(impacts)]
    return {symbol: np.array(sorted(pd.Timestamp(day).to_datetime64() for day in group.date.unique()))
            for symbol, group in selected.groupby("symbol", sort=False)}


def stock_daily_returns(daily: pd.DataFrame, actions: pd.DataFrame, phase5_config: dict) -> pd.DataFrame:
    """One-session returns with both endpoints and accepted Phase-5 interval rules."""
    frame = daily.sort_values(["symbol", "date"], kind="stable").reset_index(drop=True).copy()
    grouped = frame.groupby("symbol", sort=False)
    previous_close = grouped.close.shift(1)
    previous_date = grouped.date.shift(1)
    previous_position = grouped.session_position.shift(1)
    previous_quality = grouped.research_quality_status.shift(1).eq("VALID_REPORTED_EQ_ROW")
    current_quality = frame.research_quality_status.eq("VALID_REPORTED_EQ_ROW")
    contiguous = (frame.session_position - previous_position).eq(1)
    crossing = interval_crosses(frame.symbol, previous_date, frame.date,
                                blocking_event_map(actions, phase5_config))
    coverage_start = pd.Timestamp(phase5_config["corporate_action_coverage_start"]).date()
    coverage_end = pd.Timestamp(phase5_config["corporate_action_coverage_end"]).date()
    certified = previous_date.ge(coverage_start) & frame.date.le(coverage_end)
    valid = previous_close.notna() & previous_quality & current_quality & contiguous & ~crossing & certified
    frame["stock_daily_return"] = np.where(valid, frame.close / previous_close - 1, np.nan)
    frame["valid_stock_daily_return"] = valid
    frame["stock_return_invalid_reason"] = np.select(
        [~frame.date.le(coverage_end) | (previous_date.notna() & ~previous_date.ge(coverage_start)),
         previous_close.isna(), ~contiguous, crossing, ~(previous_quality & current_quality)],
        ["CORPORATE_ACTION_COVERAGE_UNCERTIFIED", "UNAVAILABLE_ENDPOINT",
         "MISSING_TRADING_SESSION_ENDPOINT", "CORPORATE_ACTION_INTERVAL_BLOCKED",
         "UNSAFE_SOURCE_ENDPOINT"], default="")
    return frame


def tier_membership(frame: pd.DataFrame, mapping: pd.DataFrame, spec: dict) -> pd.Series:
    merged = frame[["symbol"]].merge(mapping[["symbol", "mapping_status", "identity_ambiguous"]],
                                      on="symbol", how="left", validate="many_to_one")
    eligible = frame[spec["universe_column"]].fillna(False).to_numpy(dtype=bool)
    if spec["require_unique_mapping"]:
        eligible &= merged.mapping_status.eq("STATIC_CURRENT_UNIQUE").to_numpy()
    if spec["require_stable_identity"]:
        eligible &= ~merged.identity_ambiguous.fillna(True).to_numpy()
    return pd.Series(eligible, index=frame.index)


def aggregate_sector_daily(frame: pd.DataFrame, mapping: pd.DataFrame, spec: dict,
                           tier: str, minimum_size: int) -> pd.DataFrame:
    """Equal-weight same-day sector return from valid contemporaneous members."""
    mapping_columns = ["symbol", "sector", "sector_code", "mapping_status", "identity_ambiguous"]
    work = frame.merge(mapping[mapping_columns], on="symbol", how="left", validate="many_to_one")
    eligible = work[spec["universe_column"]].fillna(False)
    if spec["require_unique_mapping"]:
        eligible &= work.mapping_status.eq("STATIC_CURRENT_UNIQUE")
    if spec["require_stable_identity"]:
        eligible &= ~work.identity_ambiguous.fillna(True)
    work = work.loc[eligible & work.sector.notna(),
                    ["date", "session_position", "symbol", "sector", "sector_code",
                     "stock_daily_return", "valid_stock_daily_return"]].copy()
    work["valid_return_value"] = work.stock_daily_return.where(work.valid_stock_daily_return)
    grouped = work.groupby(["date", "session_position", "sector", "sector_code"], sort=True, observed=True)
    result = grouped.agg(eligible_constituent_count=("symbol", "size"),
                         constituent_count=("valid_stock_daily_return", "sum"),
                         sector_daily_return=("valid_return_value", "mean")).reset_index()
    result["invalid_constituent_count"] = result.eligible_constituent_count - result.constituent_count
    result["valid_sector_daily_return"] = result.constituent_count.ge(minimum_size) & result.sector_daily_return.notna()
    result.loc[~result.valid_sector_daily_return, "sector_daily_return"] = np.nan
    result["sector_daily_invalid_reason"] = np.where(result.valid_sector_daily_return, "",
                                                       "INSUFFICIENT_VALID_CONSTITUENTS")
    result["research_tier"] = tier
    result["minimum_sector_size"] = minimum_size
    result["mapping_provenance"] = "STATIC_CURRENT_NO_EFFECTIVE_DATES"
    return result.sort_values(["date", "sector_code"], kind="stable").reset_index(drop=True)


def _compound(frame: pd.DataFrame, value_columns: list[str]) -> pd.Series:
    if not value_columns:
        return pd.Series(np.nan, index=frame.index)
    values = frame[value_columns]
    return (1 + values).prod(axis=1) - 1


def build_factor_panel(sector_daily: pd.DataFrame, formations=FORMATIONS, futures=FUTURES) -> pd.DataFrame:
    """Build independent sector formation returns, ranks, and future labels."""
    panel = sector_daily.sort_values(["sector_code", "date"], kind="stable").reset_index(drop=True).copy()
    grouped = panel.groupby("sector_code", sort=False)
    for horizon in formations:
        shifted_returns = [grouped.sector_daily_return.shift(k) for k in range(horizon)]
        shifted_positions = [grouped.session_position.shift(k) for k in range(horizon)]
        values = pd.concat(shifted_returns, axis=1)
        positions = pd.concat(shifted_positions, axis=1)
        valid = values.notna().all(axis=1)
        for k in range(horizon):
            valid &= positions.iloc[:, k].eq(panel.session_position - k)
        panel[f"sector_ret_{horizon}"] = np.where(valid, (1 + values).prod(axis=1) - 1, np.nan)
        panel[f"valid_sector_ret_{horizon}"] = valid
        enough_calendar = panel.session_position.ge(horizon - 1)
        panel[f"sector_ret_{horizon}_invalid_reason"] = np.where(
            valid, "", np.where(~enough_calendar, "INSUFFICIENT_SECTOR_HISTORY",
                                 "MISSING_OR_INVALID_SECTOR_DAILY_RETURN_INTERVAL"))
    for horizon in futures:
        shifted_returns = [grouped.sector_daily_return.shift(-k) for k in range(1, horizon + 1)]
        shifted_positions = [grouped.session_position.shift(-k) for k in range(1, horizon + 1)]
        values = pd.concat(shifted_returns, axis=1)
        positions = pd.concat(shifted_positions, axis=1)
        valid = values.notna().all(axis=1)
        for k in range(1, horizon + 1):
            valid &= positions.iloc[:, k - 1].eq(panel.session_position + k)
        panel[f"future_sector_ret_{horizon}"] = np.where(valid, (1 + values).prod(axis=1) - 1, np.nan)
        panel[f"valid_future_sector_ret_{horizon}"] = valid
        panel[f"future_sector_ret_{horizon}_invalid_reason"] = np.where(
            valid, "", "MISSING_OR_INVALID_FUTURE_SECTOR_DAILY_RETURN_INTERVAL")
    for horizon in formations:
        valid = panel[f"valid_sector_ret_{horizon}"]
        ranked = panel.loc[valid, ["date", "sector_code", f"sector_ret_{horizon}"]].copy()
        ranked = ranked.sort_values(["date", f"sector_ret_{horizon}", "sector_code"], kind="stable")
        ranked["ordinal"] = ranked.groupby("date", sort=False).cumcount() + 1
        ranked["count"] = ranked.groupby("date", sort=False).sector_code.transform("size")
        ranked["percentile"] = np.where(ranked["count"].gt(1),
                                         (ranked.ordinal - 1) / (ranked["count"] - 1), .5)
        for name in (f"sector_rank_{horizon}", f"sector_pct_{horizon}", f"eligible_sector_count_{horizon}"):
            panel[name] = np.nan
        panel.loc[ranked.index, f"sector_rank_{horizon}"] = ranked.ordinal
        panel.loc[ranked.index, f"sector_pct_{horizon}"] = ranked.percentile
        panel.loc[ranked.index, f"eligible_sector_count_{horizon}"] = ranked["count"]
    return panel.sort_values(["date", "sector_code"], kind="stable").reset_index(drop=True)


def pair_work(panel: pd.DataFrame, formation: int, future: int) -> pd.DataFrame:
    valid = panel[f"valid_sector_ret_{formation}"] & panel[f"valid_future_sector_ret_{future}"]
    columns = ["date", "session_position", "sector", "sector_code", f"sector_ret_{formation}",
               f"sector_rank_{formation}", f"sector_pct_{formation}",
               f"eligible_sector_count_{formation}", f"future_sector_ret_{future}"]
    work = panel.loc[valid, columns].copy()
    work.columns = ["date", "session_position", "sector", "sector_code", "factor", "rank",
                    "percentile", "eligible_sector_count", "outcome"]
    count = work.eligible_sector_count
    work["quintile"] = np.where(count.ge(15), ((work["rank"] - 1) * 5 // count) + 1, 0).astype(int)
    top_n = np.ceil(count * .20)
    work["top20"] = work["rank"].gt(count - top_n)
    work["bottom20"] = work["rank"].le(top_n)
    work["top3"] = count.ge(6) & work["rank"].gt(count - 3)
    work["bottom3"] = count.ge(6) & work["rank"].le(3)
    return work


def daily_pair_statistics(work: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for day, group in work.groupby("date", sort=True):
        factor = group["rank"].to_numpy(float)
        outcome = group.outcome.to_numpy(float)
        row = {"date": day, "session_position": int(group.session_position.iloc[0]),
               "ic": correlation(rank_average(factor), rank_average(outcome)),
               "observations": len(group), "eligible_sector_count": int(group.eligible_sector_count.iloc[0]),
               "quantile_available": bool(group.eligible_sector_count.iloc[0] >= 15)}
        for quintile in range(1, 6):
            values = group.loc[group.quintile.eq(quintile), "outcome"]
            row[f"q{quintile}_sum"] = values.sum(); row[f"q{quintile}_count"] = len(values)
            row[f"q{quintile}_mean"] = values.mean()
        row["q5_q1_spread"] = row["q5_mean"] - row["q1_mean"] if row["q5_count"] and row["q1_count"] else np.nan
        for label in ("top20", "bottom20", "top3", "bottom3"):
            values = group.loc[group[label], "outcome"]
            row[f"{label}_sum"] = values.sum(); row[f"{label}_count"] = len(values); row[f"{label}_mean"] = values.mean()
        row["top20_bottom20_spread"] = row["top20_mean"] - row["bottom20_mean"]
        row["top3_bottom3_spread"] = row["top3_mean"] - row["bottom3_mean"]
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_daily(daily: pd.DataFrame) -> dict:
    if daily.empty:
        return {"mean_ic": np.nan, "median_ic": np.nan, "ic_std": np.nan,
                "ic_positive_pct": np.nan, "ic_negative_pct": np.nan, "valid_dates": 0,
                "sector_observations": 0, "median_eligible_sector_count": np.nan,
                "mean_q5_q1_spread": np.nan, "mean_top20_bottom20_spread": np.nan,
                "mean_top3_bottom3_spread": np.nan}
    return {"mean_ic": daily.ic.mean(), "median_ic": daily.ic.median(), "ic_std": daily.ic.std(ddof=1),
            "ic_positive_pct": 100 * daily.ic.gt(0).mean(), "ic_negative_pct": 100 * daily.ic.lt(0).mean(),
            "valid_dates": int(daily.ic.notna().sum()), "sector_observations": int(daily.observations.sum()),
            "median_eligible_sector_count": daily.eligible_sector_count.median(),
            "mean_q5_q1_spread": daily.q5_q1_spread.mean(),
            "mean_top20_bottom20_spread": daily.top20_bottom20_spread.mean(),
            "mean_top3_bottom3_spread": daily.top3_bottom3_spread.mean()}


def pooled_bucket(work: pd.DataFrame, mask: pd.Series) -> dict:
    values = work.loc[mask, "outcome"]
    return {"observation_count": len(values), "mean_future_return": values.mean(),
            "median_future_return": values.median(), "std_future_return": values.std(ddof=1),
            "positive_return_pct": 100 * values.gt(0).mean() if len(values) else np.nan}


def analyze_panel(panel: pd.DataFrame, config: dict) -> tuple[dict[str, pd.DataFrame], dict]:
    rank_daily=[]; rank_summary=[]; quantiles=[]; tails=[]; yearly=[]; expanding=[]; fixed=[]; nonoverlap=[]; uncertainty=[]
    caches={}; works={}
    uc=config["uncertainty"]
    for formation in FORMATIONS:
        for future in FUTURES:
            work=pair_work(panel,formation,future); works[(formation,future)]=work
            daily=daily_pair_statistics(work); caches[(formation,future)]=daily
            tagged=daily.copy(); tagged.insert(0,"future_horizon",future); tagged.insert(0,"formation_horizon",formation); rank_daily.append(tagged)
            rank_summary.append({"formation_horizon":formation,"future_horizon":future,**summarize_daily(daily)})
            quintile_means=[]
            for q in range(1,6):
                stats=pooled_bucket(work,work.quintile.eq(q)); quintile_means.append(stats["mean_future_return"])
                quantiles.append({"formation_horizon":formation,"future_horizon":future,"bucket":f"Q{q}",**stats})
            qdaily=daily.q5_q1_spread.dropna()
            quantiles.append({"formation_horizon":formation,"future_horizon":future,"bucket":"Q5_MINUS_Q1",
                "observation_count":len(qdaily),"mean_future_return":qdaily.mean(),"median_future_return":qdaily.median(),
                "std_future_return":qdaily.std(ddof=1),"positive_return_pct":100*qdaily.gt(0).mean(),
                "monotonicity":correlation(np.arange(1,6,dtype=float),rank_average(np.asarray(quintile_means,float)))})
            for label in ("top20","bottom20","top3","bottom3"):
                tails.append({"formation_horizon":formation,"future_horizon":future,"group":label.upper(),
                              **pooled_bucket(work,work[label])})
            for label,column in (("TOP20_MINUS_BOTTOM20","top20_bottom20_spread"),("TOP3_MINUS_BOTTOM3","top3_bottom3_spread")):
                values=daily[column].dropna(); tails.append({"formation_horizon":formation,"future_horizon":future,"group":label,
                    "observation_count":len(values),"mean_future_return":values.mean(),"median_future_return":values.median(),
                    "std_future_return":values.std(ddof=1),"positive_return_pct":100*values.gt(0).mean()})
            years=pd.to_datetime(daily.date).dt.year if len(daily) else pd.Series(dtype=int)
            for year in config["evaluation_years"]:
                selected=daily[years.eq(year)]; st=summarize_daily(selected)
                yearly.append({"year":year,"formation_horizon":formation,"future_horizon":future,**st})
            for year in config["expanding_evaluation_years"]:
                history=daily[years.lt(year)]; evaluation=daily[years.eq(year)]
                expanding.append({"evaluation_year":year,"history_end_year":year-1,
                    "history_actual_last_date":history.date.max() if len(history) else pd.NaT,
                    "evaluation_actual_first_date":evaluation.date.min() if len(evaluation) else pd.NaT,
                    "evaluation_actual_last_date":evaluation.date.max() if len(evaluation) else pd.NaT,
                    "formation_horizon":formation,"future_horizon":future,
                    **{f"history_{k}":v for k,v in summarize_daily(history).items()},
                    **{f"evaluation_{k}":v for k,v in summarize_daily(evaluation).items()}})
            for period in config["fixed_periods"]:
                start=pd.Timestamp(period["start"]).date(); end=pd.Timestamp(period["end"]).date()
                selected=daily[daily.date.between(start,end)]
                fixed.append({"period":period["name"],"calendar_start":start,"calendar_end":end,
                    "actual_first_date":selected.date.min() if len(selected) else pd.NaT,
                    "actual_last_date":selected.date.max() if len(selected) else pd.NaT,
                    "formation_horizon":formation,"future_horizon":future,**summarize_daily(selected)})
            for offset in range(future):
                selected=daily[daily.session_position.mod(future).eq(offset)]
                positions=np.sort(selected.session_position.unique())
                minimum_spacing=int(np.diff(positions).min()) if len(positions)>1 else np.nan
                nonoverlap.append({"formation_horizon":formation,"future_horizon":future,"offset":offset,
                    "minimum_signal_spacing_sessions":minimum_spacing,
                    "spacing_valid":bool(pd.isna(minimum_spacing) or minimum_spacing>=future),**summarize_daily(selected)})
            block=max(10,2*future)
            for index,(stat,column) in enumerate((("MEAN_RANK_IC","ic"),("MEAN_Q5_Q1_SPREAD","q5_q1_spread"))):
                values=daily[column].dropna().to_numpy(float); seed=uc["seed"]+formation*1000+future*10+index
                estimate,lower,upper=moving_block_bootstrap(values,block,uc["replications"],seed,uc["confidence_level"])
                pvalue=block_bootstrap_pvalue(values,block,uc["replications"],seed+500000)
                uncertainty.append({"formation_horizon":formation,"future_horizon":future,"statistic":stat,
                    "estimate":estimate,"ci_lower":lower,"ci_upper":upper,"raw_p_value":pvalue,
                    "block_length_sessions":block,"replications":uc["replications"],"seed":seed,
                    "method":"CIRCULAR_MOVING_BLOCK_BOOTSTRAP_DAILY_STATISTIC","valid_dates":len(values)})
    non=pd.DataFrame(nonoverlap)
    grouped=non.groupby(["formation_horizon","future_horizon"],sort=True)
    non["offset_mean_ic"]=grouped.mean_ic.transform("mean")
    non["offset_positive_fraction"]=grouped.mean_ic.transform(lambda x:x.gt(0).mean())
    non["offset_mean_q5_q1_spread"]=grouped.mean_q5_q1_spread.transform("mean")
    return ({"rank_ic_daily":pd.concat(rank_daily,ignore_index=True),"rank_ic_summary":pd.DataFrame(rank_summary),
             "quintile_returns":pd.DataFrame(quantiles),"top_bottom_analysis":pd.DataFrame(tails),
             "yearly_analysis":pd.DataFrame(yearly),"expanding_window_results":pd.DataFrame(expanding),
             "fixed_period_results":pd.DataFrame(fixed),"nonoverlap_results":non,
             "uncertainty_intervals":pd.DataFrame(uncertainty)}, {"daily":caches,"work":works})


def block_bootstrap_pvalue(values: np.ndarray, block_length: int, replications: int, seed: int) -> float:
    values=values[np.isfinite(values)]
    if len(values)==0: return np.nan
    centered=values-values.mean(); n=len(values); length=min(block_length,n); blocks=math.ceil(n/length)
    offsets=np.arange(length); rng=np.random.default_rng(seed); observed=abs(values.mean()); exceed=0
    for _ in range(replications):
        starts=rng.integers(0,n,size=blocks); sample=centered[((starts[:,None]+offsets)%n).ravel()[:n]]
        exceed += abs(sample.mean()) >= observed
    return (exceed+1)/(replications+1)


def multiple_testing(uncertainty: pd.DataFrame, alpha: float) -> pd.DataFrame:
    result=uncertainty[uncertainty.statistic.eq("MEAN_RANK_IC")].copy()
    if len(result)!=30: raise ValueError("Primary Rank-IC multiple-testing family must contain 30 tests")
    for method in ("BENJAMINI_HOCHBERG","HOLM"):
        label=method.lower(); result[f"{label}_p_value"]=adjust_pvalues(result.raw_p_value,method)
        result[f"{label}_reject_{alpha}"]=result[f"{label}_p_value"].le(alpha)
    result["direction"] = np.where(result.estimate.gt(0),"POSITIVE_CONTINUATION",
                                    np.where(result.estimate.lt(0),"NEGATIVE_RELATIONSHIP","ZERO"))
    result["test_family"]="30_PRIMARY_RANK_IC_HYPOTHESES"
    return result


def signal_decay(summary: pd.DataFrame, quintiles: pd.DataFrame, tails: pd.DataFrame) -> pd.DataFrame:
    q=quintiles.pivot_table(index=["formation_horizon","future_horizon"],columns="bucket",values="mean_future_return").reset_index()
    t=tails.pivot_table(index=["formation_horizon","future_horizon"],columns="group",values="mean_future_return").reset_index()
    result=summary.merge(q,on=["formation_horizon","future_horizon"]).merge(t,on=["formation_horizon","future_horizon"])
    def label(group):
        values=group.sort_values("future_horizon").mean_ic.to_numpy()
        if np.all(values>0): return "APPEARS_OR_PERSISTS" if values[-1]>=values[0]*.75 else "DECAYS"
        if np.all(values<0): return "REVERSES"
        return "MIXED_OR_UNSTABLE"
    result["decay_description"]=result.groupby("formation_horizon",sort=False).apply(label,include_groups=False).reindex(result.formation_horizon).to_numpy()
    return result


def cross_section_size(panel: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for formation in FORMATIONS:
        values=(panel.loc[panel[f"valid_sector_ret_{formation}"],["date",f"eligible_sector_count_{formation}"]]
                .drop_duplicates("date")[f"eligible_sector_count_{formation}"])
        rows.append({"formation_horizon":formation,"dates":len(values),"minimum":values.min(),"p05":values.quantile(.05),
                     "median":values.median(),"mean":values.mean(),"p95":values.quantile(.95),"maximum":values.max(),
                     "dates_quintile_feasible":int(values.ge(15).sum()),"quintile_feasible_pct":100*values.ge(15).mean()})
    return pd.DataFrame(rows)


def summarize_panel_grid(panel: pd.DataFrame) -> pd.DataFrame:
    """Compact 30-pair summary used by prespecified sensitivity tiers."""
    rows=[]
    for formation in FORMATIONS:
        for future in FUTURES:
            daily=daily_pair_statistics(pair_work(panel,formation,future))
            stats=summarize_daily(daily)
            yearly=(daily.assign(year=pd.to_datetime(daily.date).dt.year).groupby("year").ic.mean()
                    if len(daily) else pd.Series(dtype=float))
            rows.append({"formation_horizon":formation,"future_horizon":future,**stats,
                         "positive_year_fraction":yearly.gt(0).mean() if len(yearly) else np.nan})
    return pd.DataFrame(rows)


def sensitivity_summary(analyses: dict[tuple[str,int],pd.DataFrame], primary_key=(PRIMARY_TIER,PRIMARY_SIZE)) -> tuple[pd.DataFrame,pd.DataFrame]:
    baseline=analyses[primary_key].set_index(["formation_horizon","future_horizon"])
    size_rows=[]; universe_rows=[]
    for (tier,size),summary in analyses.items():
        for row in summary.itertuples(index=False):
            base=baseline.loc[(row.formation_horizon,row.future_horizon)]
            record={"research_tier":tier,"minimum_sector_size":size,"formation_horizon":row.formation_horizon,
                    "future_horizon":row.future_horizon,"mean_ic":row.mean_ic,"mean_q5_q1_spread":row.mean_q5_q1_spread,
                    "valid_dates":row.valid_dates,"sector_observations":row.sector_observations,
                    "median_eligible_sector_count":row.median_eligible_sector_count,
                    "positive_year_fraction":row.positive_year_fraction,
                    "mean_ic_change_vs_primary":row.mean_ic-base.mean_ic,
                    "spread_change_vs_primary":row.mean_q5_q1_spread-base.mean_q5_q1_spread,
                    "year_stability_change_vs_primary":row.positive_year_fraction-base.positive_year_fraction,
                    "ic_sign_preserved":np.sign(row.mean_ic)==np.sign(base.mean_ic)}
            if tier==PRIMARY_TIER: size_rows.append(record)
            if size==PRIMARY_SIZE: universe_rows.append(record)
    return pd.DataFrame(size_rows),pd.DataFrame(universe_rows)


def leave_one_sector_out(panel: pd.DataFrame, baseline_cache: dict) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows=[]; sectors=sorted(panel.sector.unique())
    for formation in FORMATIONS:
        for future in FUTURES:
            work=pair_work(panel,formation,future); base_daily=baseline_cache[(formation,future)].set_index("date")
            baseline=summarize_daily(base_daily.reset_index())
            total_ic_sum=base_daily.ic.sum(); total_ic_count=base_daily.ic.notna().sum()
            total_spread_sum=base_daily.q5_q1_spread.sum(); total_spread_count=base_daily.q5_q1_spread.notna().sum()
            old_ic_sum=defaultdict(float); old_ic_count=defaultdict(int); new_ic_sum=defaultdict(float); new_ic_count=defaultdict(int)
            old_spread_sum=defaultdict(float); old_spread_count=defaultdict(int); new_spread_sum=defaultdict(float); new_spread_count=defaultdict(int)
            for day,group in work.groupby("date",sort=True):
                base=base_daily.loc[day]; ic_deleted,_=deletion_statistics(group,"rank","outcome")
                factors=group.factor.to_numpy(float); outcomes=group.outcome.to_numpy(float); codes=group.sector_code.astype(str).to_numpy()
                for j,sector in enumerate(group.sector):
                    if np.isfinite(base.ic): old_ic_sum[sector]+=base.ic; old_ic_count[sector]+=1
                    if np.isfinite(ic_deleted[j]): new_ic_sum[sector]+=ic_deleted[j]; new_ic_count[sector]+=1
                    if np.isfinite(base.q5_q1_spread): old_spread_sum[sector]+=base.q5_q1_spread; old_spread_count[sector]+=1
                    keep=np.arange(len(group))!=j; n=int(keep.sum())
                    if n>=15:
                        order=np.lexsort((codes[keep],factors[keep])); ranks=np.empty(n,int); ranks[order]=np.arange(1,n+1)
                        quintile=((ranks-1)*5//n)+1
                        spread=outcomes[keep][quintile==5].mean()-outcomes[keep][quintile==1].mean()
                        if np.isfinite(spread): new_spread_sum[sector]+=spread; new_spread_count[sector]+=1
            for excluded in sectors:
                ic_den=total_ic_count-old_ic_count[excluded]+new_ic_count[excluded]
                spread_den=total_spread_count-old_spread_count[excluded]+new_spread_count[excluded]
                excluded_ic=(total_ic_sum-old_ic_sum[excluded]+new_ic_sum[excluded])/ic_den if ic_den else np.nan
                excluded_spread=(total_spread_sum-old_spread_sum[excluded]+new_spread_sum[excluded])/spread_den if spread_den else np.nan
                rows.append({"formation_horizon":formation,"future_horizon":future,"excluded_sector":excluded,
                    "baseline_mean_ic":baseline["mean_ic"],"excluded_mean_ic":excluded_ic,
                    "mean_ic_change":excluded_ic-baseline["mean_ic"],
                    "baseline_q5_q1_spread":baseline["mean_q5_q1_spread"],
                    "excluded_q5_q1_spread":excluded_spread,
                    "q5_q1_spread_change":excluded_spread-baseline["mean_q5_q1_spread"],
                    "removed_only_intended_sector":True})
    detail=pd.DataFrame(rows)
    summary=[]
    for keys,group in detail.groupby(["formation_horizon","future_horizon"],sort=True):
        pos=group.loc[group.mean_ic_change.idxmax()]; neg=group.loc[group.mean_ic_change.idxmin()]
        spread=group.loc[group.q5_q1_spread_change.abs().idxmax()]
        summary.append({"formation_horizon":keys[0],"future_horizon":keys[1],
            "largest_positive_ic_change":pos.mean_ic_change,"largest_positive_ic_change_sector":pos.excluded_sector,
            "largest_negative_ic_change":neg.mean_ic_change,"largest_negative_ic_change_sector":neg.excluded_sector,
            "largest_absolute_spread_change":spread.q5_q1_spread_change,"largest_spread_influence_sector":spread.excluded_sector})
    return detail,pd.DataFrame(summary)


def classify_formations(summary: pd.DataFrame, fixed: pd.DataFrame, nonoverlap: pd.DataFrame,
                        uncertainty: pd.DataFrame, testing: pd.DataFrame,
                        size_sensitivity: pd.DataFrame, universe_sensitivity: pd.DataFrame,
                        config: dict) -> pd.DataFrame:
    rules=config["classification_rules"]; rows=[]
    non=nonoverlap.drop_duplicates(["formation_horizon","future_horizon"])
    for formation in FORMATIONS:
        full=summary[summary.formation_horizon.eq(formation)]
        hold=fixed[(fixed.formation_horizon.eq(formation))&fixed.period.eq("HOLDOUT")]
        n=non[non.formation_horizon.eq(formation)]
        ci=uncertainty[(uncertainty.formation_horizon.eq(formation))&uncertainty.statistic.eq("MEAN_RANK_IC")]
        mt=testing[testing.formation_horizon.eq(formation)]
        positive_full=int(full.mean_ic.gt(0).sum()); negative_full=int(full.mean_ic.lt(0).sum())
        positive_hold=int(hold.mean_ic.gt(0).sum()); negative_hold=int(hold.mean_ic.lt(0).sum())
        positive_non=int(n.offset_mean_ic.gt(0).sum()); negative_non=int(n.offset_mean_ic.lt(0).sum())
        positive_ci=int(ci.ci_lower.gt(0).sum()); negative_ci=int(ci.ci_upper.lt(0).sum())
        positive_bh=int((mt["benjamini_hochberg_reject_0.05"]&mt.direction.eq("POSITIVE_CONTINUATION")).sum())
        positive_holm=int((mt["holm_reject_0.05"]&mt.direction.eq("POSITIVE_CONTINUATION")).sum())
        size=size_sensitivity[size_sensitivity.formation_horizon.eq(formation)]
        universe=universe_sensitivity[universe_sensitivity.formation_horizon.eq(formation)]
        sensitivity_positive=float(pd.concat([size.mean_ic.gt(0),universe.mean_ic.gt(0)]).mean())
        rr=rules["robust"]; pp=rules["promising"]; rv=rules["reversal_like"]
        if (positive_full>=rr["minimum_positive_primary_pairs"] and positive_hold>=rr["minimum_positive_holdout_pairs"]
            and positive_non>=rr["minimum_positive_nonoverlap_pairs"] and positive_ci>=rr["minimum_positive_confidence_intervals"]
            and positive_bh>=rr["minimum_positive_bh_rejections"]): label="ROBUST"
        elif (negative_full>=rv["minimum_negative_primary_pairs"] and negative_hold>=rv["minimum_negative_holdout_pairs"]
              and negative_non>=rv["minimum_negative_nonoverlap_pairs"]): label="REVERSAL-LIKE"
        elif (positive_full>=pp["minimum_positive_primary_pairs"] and positive_hold>=pp["minimum_positive_holdout_pairs"]
              and positive_non>=pp["minimum_positive_nonoverlap_pairs"]): label="PROMISING BUT UNSTABLE"
        elif positive_full<=1 and positive_hold<=1: label="FAIL"
        else: label="INCONCLUSIVE"
        rows.append({"formation_horizon":formation,"classification":label,
            "positive_primary_pairs":positive_full,"negative_primary_pairs":negative_full,
            "positive_holdout_pairs":positive_hold,"negative_holdout_pairs":negative_hold,
            "positive_nonoverlap_pairs":positive_non,"negative_nonoverlap_pairs":negative_non,
            "positive_95pct_ic_intervals":positive_ci,"negative_95pct_ic_intervals":negative_ci,
            "positive_bh_rejections":positive_bh,"positive_holm_rejections":positive_holm,
            "sensitivity_cells_positive_fraction":sensitivity_positive})
    return pd.DataFrame(rows)
