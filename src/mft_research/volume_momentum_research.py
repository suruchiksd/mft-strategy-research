"""Predictive research for the seven frozen Phase-8 Volume + Momentum candidates."""

from __future__ import annotations

import math
import os
from itertools import combinations

import numpy as np
import pandas as pd

from mft_research.csrs.phase4 import correlation, moving_block_bootstrap, rank_average
from mft_research.csrs.phase5 import adjust_pvalues, interval_crosses

CANDIDATES = ("VM01", "VM02", "VM03", "VM04", "VM05", "VM06", "VM07")
FUTURES = (1, 2, 3, 5, 10, 20)
INTERACTIONS = {"VM05": ("VM01", "VM03"), "VM06": ("VM02", "VM03"), "VM07": ("VM02", "VM04")}
ROLES = {"VM01": "CONTROL_PRICE", "VM02": "CONTROL_PRICE", "VM03": "CONTROL_VOLUME",
         "VM04": "CONTROL_VOLUME", "VM05": "INTERACTION", "VM06": "INTERACTION", "VM07": "INTERACTION"}
UNIVERSES = ("BASIC_LIQUID", "MODERATE_LIQUID")


def _rss_mib() -> float:
    """Return current resident memory for compact build-stage diagnostics."""
    try:
        for line in open(f"/proc/{os.getpid()}/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return float("nan")


def _stage(name: str) -> None:
    print(f"STAGE {name} rss_mib={_rss_mib():.1f}", flush=True)


def validate_config(config: dict, registry: pd.DataFrame) -> None:
    if tuple(config["candidate_ids"]) != CANDIDATES or tuple(registry.candidate_id) != CANDIDATES:
        raise ValueError("Frozen seven-candidate registry changed")
    if tuple(config["future_horizons"]) != FUTURES:
        raise ValueError("Frozen Phase-9 future horizons changed")
    if config["interaction_controls"] != {key: list(value) for key, value in INTERACTIONS.items()}:
        raise ValueError("Frozen interaction-control map changed")
    if config["primary_universe"] != "BASIC_LIQUID" or config["sensitivity_universe"] != "MODERATE_LIQUID":
        raise ValueError("Frozen Phase-9 universe contract changed")
    if dict(zip(registry.candidate_id, registry.role)) != ROLES:
        raise ValueError("Candidate roles changed")


def blocking_event_map(actions: pd.DataFrame, config: dict) -> dict[str, np.ndarray]:
    selected = actions[actions.series.eq("EQ") & actions.research_impact.isin(config["corporate_action_blocking_impacts"])]
    return {symbol: np.array(sorted(pd.Timestamp(day).to_datetime64() for day in group.date.unique()))
            for symbol, group in selected.groupby("symbol", sort=False)}


def candidate_source(candidate: str, universe: str) -> str:
    number = candidate.lower()
    return f"candidate_{number}" if candidate in CANDIDATES[:4] else f"candidate_{number}_{universe.lower()}"


def candidate_reason(frame: pd.DataFrame, candidate: str) -> pd.Series:
    dependencies = {
        "VM01": [("valid_price_return_5", "price_return_5_invalid_reason")],
        "VM02": [("valid_price_return_20", "price_return_20_invalid_reason")],
        "VM03": [("valid_volume_baseline_20", "volume_baseline_20_invalid_reason")],
        "VM04": [("valid_volume_baseline_60", "volume_baseline_60_invalid_reason")],
        "VM05": [("valid_price_return_5", "price_return_5_invalid_reason"), ("valid_volume_baseline_20", "volume_baseline_20_invalid_reason")],
        "VM06": [("valid_price_return_20", "price_return_20_invalid_reason"), ("valid_volume_baseline_20", "volume_baseline_20_invalid_reason")],
        "VM07": [("valid_price_return_20", "price_return_20_invalid_reason"), ("valid_volume_baseline_60", "volume_baseline_60_invalid_reason")],
    }
    reason = pd.Series("", index=frame.index, dtype="string")
    for valid, column in dependencies[candidate]:
        selected = ~frame[valid].fillna(False) & reason.eq("")
        reason.loc[selected] = frame.loc[selected, column].replace("", "UNSAFE_COMPONENT")
    return reason


def rank_same_date(frame: pd.DataFrame, raw: str, valid: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    work = frame.loc[valid & frame[raw].notna(), ["date", "symbol", raw]].copy()
    work = work.sort_values(["date", raw, "symbol"], kind="stable")
    work["rank"] = work.groupby("date", sort=False).cumcount() + 1
    work["count"] = work.groupby("date", sort=False).symbol.transform("size")
    work["pct"] = np.where(work["count"].gt(1), (work["rank"] - 1) / (work["count"] - 1), .5)
    rank = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    count = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    pct = pd.Series(np.nan, index=frame.index)
    rank.loc[work.index] = work["rank"].astype(int); count.loc[work.index] = work["count"].astype(int); pct.loc[work.index] = work.pct
    return rank, pct, count


def recorded_action_proximity(frame: pd.DataFrame, actions: pd.DataFrame, window: int) -> pd.Series:
    date_position = frame[["date", "session_position"]].drop_duplicates().set_index("date").session_position
    events = actions[actions.series.eq("EQ")][["symbol", "date"]].drop_duplicates()
    events["position"] = events.date.map(date_position)
    records = []
    for offset in range(-window, window + 1):
        shifted = events.dropna(subset=["position"])[["symbol", "position"]].copy()
        shifted["session_position"] = shifted.position.astype(int) + offset
        records.append(shifted[["symbol", "session_position"]])
    keys = pd.MultiIndex.from_frame(pd.concat(records, ignore_index=True).drop_duplicates())
    observed = pd.MultiIndex.from_frame(frame[["symbol", "session_position"]])
    return pd.Series(observed.isin(keys), index=frame.index)


def residualize_same_date(panel: pd.DataFrame, interaction: str, controls: tuple[str, str], suffix: str) -> pd.Series:
    columns = [f"{interaction.lower()}_pct_{suffix}", f"{controls[0].lower()}_pct_{suffix}", f"{controls[1].lower()}_pct_{suffix}"]
    result = pd.Series(np.nan, index=panel.index)
    valid = panel[columns].notna().all(axis=1)
    for _, index in panel.loc[valid].groupby("date", sort=False).groups.items():
        y = panel.loc[index, columns[0]].to_numpy(float)
        x = panel.loc[index, columns[1:]].to_numpy(float)
        design = np.column_stack([np.ones(len(x)), x])
        result.loc[index] = y - design @ np.linalg.lstsq(design, y, rcond=None)[0]
    return result


def build_panel(foundation: pd.DataFrame, identity: pd.DataFrame, actions: pd.DataFrame,
                registry: pd.DataFrame, config: dict) -> pd.DataFrame:
    validate_config(config, registry)
    base = ["date", "symbol", "source_format", "session_position", "close", "research_quality_status",
            "universe_basic_liquid", "universe_moderate_liquid"]
    dependency = ["valid_price_return_5", "price_return_5_invalid_reason", "valid_price_return_20", "price_return_20_invalid_reason",
                  "valid_volume_baseline_20", "volume_baseline_20_invalid_reason", "valid_volume_baseline_60", "volume_baseline_60_invalid_reason"]
    raw = [candidate_source(candidate, universe) for universe in UNIVERSES for candidate in CANDIDATES]
    raw = list(dict.fromkeys(raw))
    panel = foundation[base + dependency + raw].copy().sort_values(["symbol", "date"], kind="stable").reset_index(drop=True)
    ambiguity = identity.set_index("symbol").identity_ambiguity
    panel["identity_safe"] = ~panel.symbol.map(ambiguity).fillna(True)
    cutoff = pd.Timestamp(config["corporate_action_coverage_end"]).date()
    for universe in UNIVERSES:
        suffix = universe.lower(); member = panel[f"universe_{suffix}"].fillna(False)
        for candidate in CANDIDATES:
            source = candidate_source(candidate, universe); raw_column = f"{candidate.lower()}_raw_{suffix}"
            panel[raw_column] = panel[source]
            reason = candidate_reason(panel, candidate)
            valid = member & panel.identity_safe & panel[source].notna() & panel.date.le(cutoff)
            reason.loc[~member] = "NOT_IN_POINT_IN_TIME_UNIVERSE"
            reason.loc[member & ~panel.identity_safe] = "IDENTITY_AMBIGUOUS"
            reason.loc[member & panel.identity_safe & panel.date.gt(cutoff)] = "CORPORATE_ACTION_COVERAGE_UNCERTIFIED"
            reason.loc[valid] = ""
            panel[f"valid_{candidate.lower()}_{suffix}"] = valid
            panel[f"{candidate.lower()}_invalid_reason_{suffix}"] = reason
            rank, pct, count = rank_same_date(panel, raw_column, valid)
            panel[f"{candidate.lower()}_rank_{suffix}"] = rank
            panel[f"{candidate.lower()}_pct_{suffix}"] = pct
            panel[f"{candidate.lower()}_count_{suffix}"] = count

    grouped = panel.groupby("symbol", sort=False)
    quality = panel.research_quality_status.eq("VALID_REPORTED_EQ_ROW")
    events = blocking_event_map(actions, config)
    start = pd.Timestamp(config["corporate_action_coverage_start"]).date(); end = cutoff
    for horizon in FUTURES:
        target_close = grouped.close.shift(-horizon); target_date = grouped.date.shift(-horizon)
        target_position = grouped.session_position.shift(-horizon)
        interval_quality = pd.concat([quality.groupby(panel.symbol, sort=False).shift(-k) for k in range(horizon + 1)], axis=1).all(axis=1)
        contiguous = (target_position - panel.session_position).eq(horizon)
        crossing = interval_crosses(panel.symbol, panel.date, target_date, events)
        coverage = panel.date.ge(start) & target_date.le(end)
        valid = (panel.identity_safe & target_close.gt(0).fillna(False) & interval_quality & contiguous.fillna(False) & ~crossing & coverage.fillna(False)).fillna(False)
        panel[f"future_return_{horizon}"] = (target_close / panel.close - 1).where(valid)
        panel[f"valid_future_{horizon}"] = valid
        conditions=[(~panel.identity_safe).to_numpy(bool),target_date.isna().to_numpy(bool),
                    ((~contiguous.fillna(False))&target_date.notna()).to_numpy(bool),
                    ((~interval_quality)&target_date.notna()).to_numpy(bool),np.asarray(crossing,dtype=bool),
                    ((~coverage.fillna(False))&target_date.notna()).to_numpy(bool),target_close.le(0).fillna(False).to_numpy(bool)]
        reason = np.select(conditions,
                           ["IDENTITY_AMBIGUOUS", "UNAVAILABLE_FUTURE_ENDPOINT", "MISSING_TRADING_SESSION_ENDPOINT",
                            "UNSAFE_OUTCOME_INTERVAL", "CORPORATE_ACTION_INTERVAL_BLOCKED",
                            "CORPORATE_ACTION_COVERAGE_UNCERTIFIED", "INVALID_FUTURE_PRICE_ENDPOINT"], default="")
        panel[f"future_invalid_reason_{horizon}"] = reason
    panel["near_recorded_action_5_sessions"] = recorded_action_proximity(panel, actions, int(config["corporate_action_proximity_sessions"]))
    for interaction, controls in INTERACTIONS.items():
        panel[f"{interaction.lower()}_incremental_residual_basic_liquid"] = residualize_same_date(panel, interaction, controls, "basic_liquid")
    panel["phase8_registry_build_id"] = config["phase8_required_build_id"]
    keep = ["date", "symbol", "source_format", "session_position", "close", "universe_basic_liquid",
            "universe_moderate_liquid", "identity_safe", "near_recorded_action_5_sessions", "phase8_registry_build_id"]
    keep += [column for column in panel.columns if any(candidate.lower() in column for candidate in CANDIDATES)]
    keep += [column for column in panel.columns if column.startswith("valid_future_") or column.startswith("future_return_") or column.startswith("future_invalid_reason_")]
    return panel[keep].sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def pair_work(panel: pd.DataFrame, candidate: str, future: int, universe: str,
              exclude_action_proximity: bool = False) -> pd.DataFrame:
    suffix = universe.lower(); raw = f"{candidate.lower()}_raw_{suffix}"
    signal_valid = panel[f"valid_{candidate.lower()}_{suffix}"].copy()
    if exclude_action_proximity:
        signal_valid &= ~panel.near_recorded_action_5_sessions
        rank,percentile,count=rank_same_date(panel,raw,signal_valid)
    else:
        rank=panel[f"{candidate.lower()}_rank_{suffix}"]; percentile=panel[f"{candidate.lower()}_pct_{suffix}"]
        count=panel[f"{candidate.lower()}_count_{suffix}"]
    valid = signal_valid & panel[f"valid_future_{future}"]
    columns = ["date", "symbol", "session_position", "source_format", raw, f"future_return_{future}"]
    work = panel.loc[valid, columns].copy(); work.columns = ["date", "symbol", "session_position", "source_format", "factor", "outcome"]
    work["rank"] = rank.loc[work.index].astype(int)
    work["percentile"] = percentile.loc[work.index]
    work["cross_section_count"] = count.loc[work.index].astype(int)
    count = work.cross_section_count
    work["decile"] = np.where(count.ge(20), ((work["rank"] - 1) * 10 // count) + 1, 0).astype(int)
    for fraction in (.05, .10, .20):
        key = int(fraction * 100); n = np.ceil(count * fraction)
        work[f"top{key}"] = work["rank"].gt(count - n); work[f"bottom{key}"] = work["rank"].le(n)
    return work


def daily_statistics(work: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for day, group in work.groupby("date", sort=True):
        outcome = group.outcome.to_numpy(float); factor = group["rank"].to_numpy(float)
        row = {"date": day, "session_position": int(group.session_position.iloc[0]), "source_format": group.source_format.iloc[0],
               "ic": correlation(factor, rank_average(outcome)), "observations": len(group),
               "cross_section_count": int(group.cross_section_count.iloc[0]), "decile_available": bool(len(group) >= 20)}
        for decile in range(1, 11):
            values = group.loc[group.decile.eq(decile), "outcome"]
            row[f"d{decile}_sum"] = values.sum(); row[f"d{decile}_count"] = len(values); row[f"d{decile}_mean"] = values.mean()
        row["d10_d1_spread"] = row["d10_mean"] - row["d1_mean"] if row["d10_count"] and row["d1_count"] else np.nan
        for fraction in (5, 10, 20):
            for side in ("top", "bottom"):
                values = group.loc[group[f"{side}{fraction}"], "outcome"]
                row[f"{side}{fraction}_mean"] = values.mean(); row[f"{side}{fraction}_count"] = len(values)
            row[f"top{fraction}_bottom{fraction}_spread"] = row[f"top{fraction}_mean"] - row[f"bottom{fraction}_mean"]
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_daily(daily: pd.DataFrame) -> dict:
    if daily.empty:
        return {"mean_ic": np.nan, "median_ic": np.nan, "ic_std": np.nan, "ic_positive_pct": np.nan,
                "ic_negative_pct": np.nan, "valid_dates": 0, "stock_observations": 0,
                "median_cross_section_size": np.nan, "mean_d10_d1_spread": np.nan, "mean_top10_bottom10_spread": np.nan}
    return {"mean_ic": daily.ic.mean(), "median_ic": daily.ic.median(), "ic_std": daily.ic.std(ddof=1),
            "ic_positive_pct": 100 * daily.ic.gt(0).mean(), "ic_negative_pct": 100 * daily.ic.lt(0).mean(),
            "valid_dates": int(daily.ic.notna().sum()), "stock_observations": int(daily.observations.sum()),
            "median_cross_section_size": daily.cross_section_count.median(),
            "mean_d10_d1_spread": daily.d10_d1_spread.mean(),
            "mean_top10_bottom10_spread": daily.top10_bottom10_spread.mean()}


def pooled(values: pd.Series) -> dict:
    values = values.dropna()
    return {"observation_count": len(values), "mean_future_return": values.mean(), "median_future_return": values.median(),
            "std_future_return": values.std(ddof=1), "positive_return_pct": 100 * values.gt(0).mean() if len(values) else np.nan}


def block_pvalue(values: np.ndarray, block: int, replications: int, seed: int) -> float:
    values = values[np.isfinite(values)]
    if not len(values): return np.nan
    centered = values - values.mean(); n = len(values); length = min(block, n); blocks = math.ceil(n / length)
    rng = np.random.default_rng(seed); offsets = np.arange(length); observed = abs(values.mean()); exceed = 0
    for _ in range(replications):
        starts = rng.integers(0, n, size=blocks); sample = centered[((starts[:, None] + offsets) % n).ravel()[:n]]
        exceed += abs(sample.mean()) >= observed
    return (exceed + 1) / (replications + 1)


def uncertainty(values: pd.Series, future: int, seed: int, config: dict) -> dict:
    array = values.dropna().to_numpy(float); block = max(10, 2 * future); settings = config["uncertainty"]
    estimate, lower, upper = moving_block_bootstrap(array, block, settings["replications"], seed, settings["confidence_level"])
    return {"estimate": estimate, "ci_lower": lower, "ci_upper": upper,
            "raw_p_value": block_pvalue(array, block, settings["replications"], seed + 500000),
            "block_length_sessions": block, "replications": settings["replications"], "seed": seed,
            "method": "CIRCULAR_MOVING_BLOCK_BOOTSTRAP_DAILY_STATISTIC", "valid_dates": len(array)}


def adjust_family(frame: pd.DataFrame, family: str, alpha: float) -> pd.DataFrame:
    result = frame.copy()
    for method in ("BENJAMINI_HOCHBERG", "HOLM"):
        label = method.lower(); result[f"{label}_p_value"] = adjust_pvalues(result.raw_p_value, method)
        result[f"{label}_reject_{alpha}"] = result[f"{label}_p_value"].le(alpha)
    result["direction"] = np.where(result.estimate.gt(0), "POSITIVE", np.where(result.estimate.lt(0), "NEGATIVE_REVERSAL_LIKE", "ZERO"))
    result["test_family"] = family
    return result


def incremental_work(panel: pd.DataFrame, interaction: str, future: int) -> pd.DataFrame:
    residual = f"{interaction.lower()}_incremental_residual_basic_liquid"
    valid = panel[residual].notna() & panel[f"valid_future_{future}"]
    work = panel.loc[valid, ["date", "session_position", "symbol", residual, f"future_return_{future}"]].copy()
    work.columns = ["date", "session_position", "symbol", "factor", "outcome"]
    work["ic_component"] = np.nan
    rows = []
    for day, group in work.groupby("date", sort=True):
        rows.append({"date": day, "session_position": int(group.session_position.iloc[0]),
                     "ic": correlation(rank_average(group.factor.to_numpy(float)), rank_average(group.outcome.to_numpy(float))),
                     "observations": len(group)})
    return pd.DataFrame(rows)


def analyze(panel: pd.DataFrame, registry: pd.DataFrame, config: dict) -> tuple[dict[str, pd.DataFrame], dict]:
    rank_daily=[]; summaries=[]; deciles=[]; tails=[]; yearly=[]; fixed=[]; expanding=[]; nonoverlap=[]; unc=[]
    cache={}; works={}; settings=config["uncertainty"]
    _stage("PRIMARY_42_DECILES_TAILS_CHRONOLOGY_NONOVERLAP_BOOTSTRAP_PRIMARY")
    for candidate in CANDIDATES:
        for future in FUTURES:
            work=pair_work(panel,candidate,future,"BASIC_LIQUID"); works[(candidate,future)]=work
            daily=daily_statistics(work); cache[(candidate,future)]=daily
            tagged=daily.copy(); tagged.insert(0,"future_horizon",future); tagged.insert(0,"candidate_id",candidate); rank_daily.append(tagged)
            summaries.append({"candidate_id":candidate,"candidate_role":ROLES[candidate],"future_horizon":future,**summarize_daily(daily)})
            means=[]
            for d in range(1,11):
                stats=pooled(work.loc[work.decile.eq(d),"outcome"]); means.append(stats["mean_future_return"])
                deciles.append({"candidate_id":candidate,"future_horizon":future,"bucket":f"D{d}",**stats})
            spread=daily.d10_d1_spread.dropna(); deciles.append({"candidate_id":candidate,"future_horizon":future,"bucket":"D10_MINUS_D1",**pooled(spread),
                "monotonicity":correlation(np.arange(1,11,dtype=float),rank_average(np.asarray(means,float)))})
            for fraction in (5,10,20):
                for side in ("top","bottom"):
                    stats=pooled(work.loc[work[f"{side}{fraction}"],"outcome"])
                    tails.append({"candidate_id":candidate,"future_horizon":future,"group":f"{side.upper()}{fraction}",**stats})
                values=daily[f"top{fraction}_bottom{fraction}_spread"]
                tails.append({"candidate_id":candidate,"future_horizon":future,"group":f"TOP{fraction}_MINUS_BOTTOM{fraction}",**pooled(values)})
            years=pd.to_datetime(daily.date).dt.year
            for year in config["evaluation_years"]: yearly.append({"year":year,"candidate_id":candidate,"future_horizon":future,**summarize_daily(daily[years.eq(year)])})
            for period in config["fixed_periods"]:
                start=pd.Timestamp(period["start"]).date(); end=pd.Timestamp(period["end"]).date(); selected=daily[daily.date.between(start,end)]
                fixed.append({"period":period["name"],"calendar_start":start,"calendar_end":end,"actual_first_date":selected.date.min() if len(selected) else pd.NaT,
                              "actual_last_date":selected.date.max() if len(selected) else pd.NaT,"candidate_id":candidate,"future_horizon":future,**summarize_daily(selected)})
            for year in config["expanding_evaluation_years"]:
                history=daily[years.lt(year)]; evaluation=daily[years.eq(year)]
                expanding.append({"evaluation_year":year,"history_end_year":year-1,"history_actual_last_date":history.date.max() if len(history) else pd.NaT,
                    "evaluation_actual_first_date":evaluation.date.min() if len(evaluation) else pd.NaT,"evaluation_actual_last_date":evaluation.date.max() if len(evaluation) else pd.NaT,
                    "candidate_id":candidate,"future_horizon":future,**{f"history_{k}":v for k,v in summarize_daily(history).items()},
                    **{f"evaluation_{k}":v for k,v in summarize_daily(evaluation).items()}})
            for offset in range(future):
                selected=daily[daily.session_position.mod(future).eq(offset)]; positions=np.sort(selected.session_position.unique())
                spacing=int(np.diff(positions).min()) if len(positions)>1 else np.nan
                nonoverlap.append({"candidate_id":candidate,"future_horizon":future,"offset":offset,"minimum_signal_spacing_sessions":spacing,
                                   "spacing_valid":bool(pd.isna(spacing) or spacing>=future),**summarize_daily(selected)})
            for index,(stat,column) in enumerate((("MEAN_RANK_IC","ic"),("MEAN_D10_D1_SPREAD","d10_d1_spread"))):
                seed=settings["seed"]+int(candidate[2:])*1000+future*10+index
                unc.append({"candidate_id":candidate,"future_horizon":future,"statistic":stat,**uncertainty(daily[column],future,seed,config)})
    non=pd.DataFrame(nonoverlap); grouped=non.groupby(["candidate_id","future_horizon"],sort=True)
    non["offset_mean_ic"]=grouped.mean_ic.transform("mean"); non["offset_positive_fraction"]=grouped.mean_ic.transform(lambda x:x.gt(0).mean())
    non["offset_mean_d10_d1_spread"]=grouped.mean_d10_d1_spread.transform("mean")
    uncertainty_frame=pd.DataFrame(unc); primary_testing=adjust_family(uncertainty_frame[uncertainty_frame.statistic.eq("MEAN_RANK_IC")],
        config["multiple_testing"]["primary_family"],config["multiple_testing"]["alpha"])

    # Interaction residual evidence is a separate, frozen 18-test family.
    _stage("INCREMENTAL_18_BOOTSTRAP_INCREMENTAL")
    incremental=[]; incremental_unc=[]; incremental_cache={}
    for interaction, controls in INTERACTIONS.items():
        for future in FUTURES:
            daily=incremental_work(panel,interaction,future); incremental_cache[(interaction,future)]=daily
            years=pd.to_datetime(daily.date).dt.year
            hold=daily[daily.date.between(pd.Timestamp("2025-01-01").date(),pd.Timestamp(config["corporate_action_coverage_end"]).date())]
            record={"candidate_id":interaction,"control_1":controls[0],"control_2":controls[1],"future_horizon":future,
                    "residualization":"SAME_DATE_LINEAR_RANK_RESIDUAL_NO_OUTCOME_INPUT","mean_incremental_ic":daily.ic.mean(),
                    "median_incremental_ic":daily.ic.median(),"ic_positive_pct":100*daily.ic.gt(0).mean(),"valid_dates":daily.ic.notna().sum(),
                    "stock_observations":daily.observations.sum(),"holdout_mean_incremental_ic":hold.ic.mean(),
                    "positive_year_fraction":daily.assign(year=years).groupby("year").ic.mean().gt(0).mean(),
                    "interaction_mean_ic":cache[(interaction,future)].ic.mean(),
                    "control_1_mean_ic":cache[(controls[0],future)].ic.mean(),
                    "control_2_mean_ic":cache[(controls[1],future)].ic.mean()}
            incremental.append(record)
            seed=settings["seed"]+70000+int(interaction[2:])*1000+future*10
            incremental_unc.append({"candidate_id":interaction,"future_horizon":future,"statistic":"MEAN_INCREMENTAL_RANK_IC",
                                    **uncertainty(daily.ic,future,seed,config)})
    incremental_unc=pd.DataFrame(incremental_unc); incremental_testing=adjust_family(incremental_unc,
        config["multiple_testing"]["incremental_family"],config["multiple_testing"]["alpha"])

    # Limited 5x5 component double sorts.
    _stage("DOUBLE_SORT")
    double=[]
    for interaction,(price,volume) in INTERACTIONS.items():
        for future in FUTURES:
            valid=(panel[f"valid_{interaction.lower()}_basic_liquid"]&panel[f"valid_{price.lower()}_basic_liquid"]&
                   panel[f"valid_{volume.lower()}_basic_liquid"]&panel[f"valid_future_{future}"])
            cols=[f"{price.lower()}_pct_basic_liquid",f"{volume.lower()}_pct_basic_liquid",f"future_return_{future}"]
            work=panel.loc[valid,cols].copy(); work.columns=["price_pct","volume_pct","outcome"]
            work["price_quintile"]=(np.minimum(np.floor(work.price_pct*5),4)+1).astype(int)
            work["volume_quintile"]=(np.minimum(np.floor(work.volume_pct*5),4)+1).astype(int)
            for (pq,vq),group in work.groupby(["price_quintile","volume_quintile"],sort=True):
                double.append({"candidate_id":interaction,"price_control":price,"volume_control":volume,"future_horizon":future,
                               "price_quintile":pq,"volume_quintile":vq,**pooled(group.outcome)})

    # Universe, source-era, action-proximity, and predictive-redundancy sensitivities.
    _stage("MODERATE_SOURCE_ERA_ACTION_PROXIMITY")
    universe_rows=[]; source_rows=[]; proximity_rows=[]
    for universe in UNIVERSES:
        for candidate in CANDIDATES:
            for future in FUTURES:
                daily=(cache[(candidate,future)] if universe == "BASIC_LIQUID"
                       else daily_statistics(pair_work(panel,candidate,future,universe)))
                stats=summarize_daily(daily)
                years=daily.assign(year=pd.to_datetime(daily.date).dt.year).groupby("year").ic.mean() if len(daily) else pd.Series(dtype=float)
                universe_rows.append({"universe":universe,"candidate_id":candidate,"future_horizon":future,**stats,
                                      "positive_year_fraction":years.gt(0).mean() if len(years) else np.nan})
    for candidate in CANDIDATES:
        for future in FUTURES:
            baseline=cache[(candidate,future)]; base_stats=summarize_daily(baseline)
            for era in ("OLD","NEW"):
                selected=baseline[baseline.source_format.eq(era)]
                source_rows.append({"source_era":era,"candidate_id":candidate,"future_horizon":future,**summarize_daily(selected)})
            excluded=daily_statistics(pair_work(panel,candidate,future,"BASIC_LIQUID",True)); stats=summarize_daily(excluded)
            proximity_rows.append({"candidate_id":candidate,"future_horizon":future,"sample":"EXCLUDE_RECORDED_ACTION_PLUS_MINUS_5_SESSIONS",
                                   "baseline_mean_ic":base_stats["mean_ic"],"baseline_d10_d1_spread":base_stats["mean_d10_d1_spread"],
                                   **stats,"mean_ic_change_vs_all":stats["mean_ic"]-base_stats["mean_ic"],
                                   "spread_change_vs_all":stats["mean_d10_d1_spread"]-base_stats["mean_d10_d1_spread"]})
    redundancy=[]
    daily_all=pd.concat(rank_daily,ignore_index=True)
    for future in FUTURES:
        pivot=daily_all[daily_all.future_horizon.eq(future)].pivot(index="date",columns="candidate_id",values="ic")
        for left,right in combinations(CANDIDATES,2):
            pair=pivot[[left,right]].dropna(); redundancy.append({"future_horizon":future,"candidate_left":left,"candidate_right":right,
                "valid_dates":len(pair),"daily_ic_pearson":pair[left].corr(pair[right]),
                "daily_ic_spearman":pair[left].rank().corr(pair[right].rank())})

    outputs={"candidate_rank_ic_daily":daily_all,"candidate_rank_ic_summary":pd.DataFrame(summaries),
             "candidate_decile_returns":pd.DataFrame(deciles),"candidate_tail_analysis":pd.DataFrame(tails),
             "yearly_analysis":pd.DataFrame(yearly),"fixed_period_results":pd.DataFrame(fixed),
             "expanding_window_results":pd.DataFrame(expanding),"nonoverlap_results":non,
             "uncertainty_intervals":uncertainty_frame,"multiple_testing":primary_testing,
             "interaction_incremental_ic":pd.DataFrame(incremental),"interaction_incremental_uncertainty":incremental_testing,
             "interaction_double_sort":pd.DataFrame(double),"universe_sensitivity":pd.DataFrame(universe_rows),
             "source_era_sensitivity":pd.DataFrame(source_rows),"corporate_action_proximity_sensitivity":pd.DataFrame(proximity_rows),
             "predictive_redundancy":pd.DataFrame(redundancy)}
    _stage("ANALYSIS_COMPLETE")
    return outputs,{"daily":cache,"incremental_daily":incremental_cache}


def signal_decay(summary: pd.DataFrame) -> pd.DataFrame:
    result = summary.copy()
    descriptions = {}
    for candidate, group in result.groupby("candidate_id", sort=False):
        values = group.sort_values("future_horizon").mean_ic.to_numpy(float)
        if np.all(values > 0): label = "STRENGTHENS" if values[-1] > values[0] else "DECAYS_OR_PLATEAUS"
        elif np.all(values < 0): label = "REVERSAL_STRENGTHENS" if abs(values[-1]) > abs(values[0]) else "REVERSAL_DECAYS_OR_PLATEAUS"
        else: label = "MIXED"
        descriptions[candidate] = label
    result["decay_description"] = result.candidate_id.map(descriptions)
    return result[["candidate_id","candidate_role","future_horizon","mean_ic","mean_d10_d1_spread",
                   "mean_top10_bottom10_spread","decay_description"]]


def classify_candidates(outputs: dict[str, pd.DataFrame], config: dict) -> pd.DataFrame:
    summary=outputs["candidate_rank_ic_summary"]; fixed=outputs["fixed_period_results"]
    non=outputs["nonoverlap_results"].drop_duplicates(["candidate_id","future_horizon"])
    uncertainty_frame=outputs["uncertainty_intervals"].query("statistic == 'MEAN_RANK_IC'")
    testing=outputs["multiple_testing"]; yearly=outputs["yearly_analysis"]
    sensitivity=outputs["universe_sensitivity"].query("universe == 'MODERATE_LIQUID'")
    incremental=outputs["interaction_incremental_ic"]; increment_test=outputs["interaction_incremental_uncertainty"]
    r=config["classification_rules"]["robust"]; p=config["classification_rules"]["promising"]
    ir=config["classification_rules"]["interaction_incremental"]
    rows=[]
    for candidate in CANDIDATES:
        full=summary[summary.candidate_id.eq(candidate)]; hold=fixed[(fixed.candidate_id.eq(candidate))&fixed.period.eq("HOLDOUT")]
        n=non[non.candidate_id.eq(candidate)]; ci=uncertainty_frame[uncertainty_frame.candidate_id.eq(candidate)]
        mt=testing[testing.candidate_id.eq(candidate)]; yr=yearly[yearly.candidate_id.eq(candidate)]; sens=sensitivity[sensitivity.candidate_id.eq(candidate)]
        pos={"primary":int(full.mean_ic.gt(0).sum()),"holdout":int(hold.mean_ic.gt(0).sum()),
             "nonoverlap":int(n.offset_mean_ic.gt(0).sum()),"ci":int(ci.ci_lower.gt(0).sum()),
             "bh":int((mt["benjamini_hochberg_reject_0.05"]&mt.direction.eq("POSITIVE")).sum()),
             "year_fraction":float(yr.mean_ic.gt(0).mean()),"sensitivity":int(sens.mean_ic.gt(0).sum())}
        neg={"primary":int(full.mean_ic.lt(0).sum()),"holdout":int(hold.mean_ic.lt(0).sum()),
             "nonoverlap":int(n.offset_mean_ic.lt(0).sum()),"ci":int(ci.ci_upper.lt(0).sum()),
             "bh":int((mt["benjamini_hochberg_reject_0.05"]&mt.direction.eq("NEGATIVE_REVERSAL_LIKE")).sum()),
             "year_fraction":float(yr.mean_ic.lt(0).mean()),"sensitivity":int(sens.mean_ic.lt(0).sum())}
        robust=lambda x:(x["primary"]>=r["minimum_directional_primary_pairs"] and x["holdout"]>=r["minimum_directional_holdout_pairs"]
            and x["nonoverlap"]>=r["minimum_directional_nonoverlap_pairs"] and x["ci"]>=r["minimum_directional_confidence_intervals"]
            and x["bh"]>=r["minimum_directional_bh_rejections"] and x["year_fraction"]>=r["minimum_directional_year_fraction"]
            and x["sensitivity"]>=r["minimum_directional_sensitivity_pairs"])
        promising=lambda x:(x["primary"]>=p["minimum_directional_primary_pairs"] and x["holdout"]>=p["minimum_directional_holdout_pairs"]
            and x["nonoverlap"]>=p["minimum_directional_nonoverlap_pairs"] and x["year_fraction"]>=p["minimum_directional_year_fraction"])
        inc_pos=incremental[incremental.candidate_id.eq(candidate)] if candidate in INTERACTIONS else pd.DataFrame()
        inc_mt=increment_test[increment_test.candidate_id.eq(candidate)] if candidate in INTERACTIONS else pd.DataFrame()
        inc_pairs=int(inc_pos.mean_incremental_ic.gt(0).sum()) if len(inc_pos) else 0
        inc_hold=int(inc_pos.holdout_mean_incremental_ic.gt(0).sum()) if len(inc_pos) else 0
        inc_ci=int(inc_mt.ci_lower.gt(0).sum()) if len(inc_mt) else 0
        inc_robust=(inc_pairs>=ir["robust_minimum_positive_pairs"] and inc_hold>=ir["robust_minimum_positive_holdout_pairs"]
                    and inc_ci>=ir["robust_minimum_positive_confidence_intervals"])
        inc_promising=(inc_pairs>=ir["promising_minimum_positive_pairs"] and inc_hold>=ir["promising_minimum_positive_holdout_pairs"])
        if ROLES[candidate]=="CONTROL_VOLUME" and (robust(pos) or robust(neg)): label="VOLUME-ONLY EFFECT"
        elif robust(neg): label="REVERSAL-LIKE"
        elif ROLES[candidate]=="INTERACTION" and robust(pos) and inc_robust: label="ROBUST POSITIVE"
        elif ROLES[candidate]=="INTERACTION" and (robust(pos) or promising(pos)) and not inc_promising: label="NO INCREMENTAL VALUE"
        elif robust(pos): label="ROBUST POSITIVE"
        elif promising(pos) and (ROLES[candidate]!="INTERACTION" or inc_promising): label="PROMISING POSITIVE"
        elif promising(neg): label="REVERSAL-LIKE"
        else: label="INCONCLUSIVE"
        rows.append({"candidate_id":candidate,"role":ROLES[candidate],"classification":label,
                     "positive_primary_pairs":pos["primary"],"negative_primary_pairs":neg["primary"],
                     "positive_holdout_pairs":pos["holdout"],"negative_holdout_pairs":neg["holdout"],
                     "positive_nonoverlap_pairs":pos["nonoverlap"],"negative_nonoverlap_pairs":neg["nonoverlap"],
                     "positive_ic_intervals":pos["ci"],"negative_ic_intervals":neg["ci"],
                     "positive_bh_rejections":pos["bh"],"negative_bh_rejections":neg["bh"],
                     "positive_year_cell_fraction":pos["year_fraction"],"negative_year_cell_fraction":neg["year_fraction"],
                     "moderate_positive_pairs":pos["sensitivity"],"moderate_negative_pairs":neg["sensitivity"],
                     "incremental_positive_pairs":inc_pairs,"incremental_positive_holdout_pairs":inc_hold,
                     "incremental_positive_intervals":inc_ci})
    return pd.DataFrame(rows)
