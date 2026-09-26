"""Frozen Phase-10 reversal confirmation calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from mft_research.csrs.phase4 import correlation, moving_block_bootstrap, rank_average
from mft_research.csrs.phase5 import interval_crosses
from mft_research.reversal import CANDIDATES, FUTURES, rank_signal


def build_event_map(historical: pd.DataFrame, extension: pd.DataFrame, config: dict) -> dict[str, np.ndarray]:
    old = historical[historical.series.eq("EQ") & historical.research_impact.isin(config["historical_blocking_impacts"])][["symbol", "date"]].copy()
    old.columns = ["symbol", "date"]
    new = extension[extension.mapped_symbol.notna() & extension.safety_classification.isin(config["extension_blocking_classes"])][["mapped_symbol", "blocking_date"]].copy()
    new.columns = ["symbol", "date"]
    events = pd.concat([old, new], ignore_index=True)
    events["date"] = pd.to_datetime(events.date).dt.date
    return {symbol: np.array(sorted(pd.Timestamp(x).to_datetime64() for x in group.date.unique()))
            for symbol, group in events.groupby("symbol", sort=False)}


def _all_quality(grouped, quality: pd.Series, horizon: int, future: bool) -> pd.Series:
    result = quality.copy()
    for offset in range(1, horizon + 1):
        shifted = grouped["quality"].shift(-offset if future else offset).fillna(False)
        result &= shifted
    return result


def build_panel(daily: pd.DataFrame, identity: pd.DataFrame, historical: pd.DataFrame,
                extension: pd.DataFrame, config: dict) -> pd.DataFrame:
    columns = ["date", "symbol", "close", "session_position", "research_quality_status",
               "universe_basic_liquid", "universe_moderate_liquid"]
    frame = daily[columns].copy().sort_values(["symbol", "date"], kind="stable").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame.date).dt.date
    ambiguity = identity.set_index("symbol").identity_ambiguity.astype(bool)
    frame["identity_safe"] = ~frame.symbol.map(ambiguity).fillna(True)
    frame["quality"] = frame.research_quality_status.eq("VALID_REPORTED_EQ_ROW") & frame.identity_safe & frame.close.gt(0)
    grouped = frame.groupby("symbol", sort=False)
    event_map = build_event_map(historical, extension, config)

    for candidate, horizon in config["candidate_formations"].items():
        start_close = grouped.close.shift(horizon)
        start_date = grouped.date.shift(horizon)
        start_position = grouped.session_position.shift(horizon)
        exact = (frame.session_position - start_position).eq(horizon)
        safe = _all_quality(grouped, frame.quality, horizon, False)
        crosses = interval_crosses(frame.symbol, start_date, frame.date, event_map)
        valid = safe & exact & start_close.notna() & ~crosses
        raw_return = frame.close / start_close - 1
        frame[f"price_return_{horizon}"] = np.where(valid, raw_return, np.nan)
        frame[candidate] = np.where(valid, -raw_return, np.nan)
        frame[f"valid_{candidate}"] = valid
        frame[f"{candidate}_invalid_reason"] = np.select(
            [~frame.identity_safe, ~frame.quality, start_close.isna(), ~exact, crosses, ~safe],
            ["IDENTITY_AMBIGUOUS", "INVALID_SIGNAL_ENDPOINT", "INSUFFICIENT_HISTORY", "UNAVAILABLE_SESSION_ENDPOINT",
             "CORPORATE_ACTION_INTERVAL", "UNSAFE_INTERVENING_SESSION"], default="")

    for horizon in config["future_horizons"]:
        target_close = grouped.close.shift(-horizon)
        target_date = grouped.date.shift(-horizon)
        target_position = grouped.session_position.shift(-horizon)
        exact = (target_position - frame.session_position).eq(horizon)
        safe = _all_quality(grouped, frame.quality, horizon, True)
        crosses = interval_crosses(frame.symbol, frame.date, target_date, event_map)
        certified = pd.to_datetime(target_date).dt.date.le(pd.Timestamp(config["certified_end"]).date())
        valid = frame.quality & target_close.notna() & exact & safe & ~crosses & certified
        frame[f"future_return_{horizon}"] = np.where(valid, target_close / frame.close - 1, np.nan)
        frame[f"valid_future_{horizon}"] = valid
        frame[f"future_invalid_reason_{horizon}"] = np.select(
            [~frame.identity_safe, ~frame.quality, target_close.isna(), ~exact, ~certified, crosses, ~safe],
            ["IDENTITY_AMBIGUOUS", "INVALID_SIGNAL_ENDPOINT", "UNAVAILABLE_FUTURE_ENDPOINT", "UNAVAILABLE_SESSION_ENDPOINT",
             "CORPORATE_ACTION_COVERAGE_UNCERTIFIED", "CORPORATE_ACTION_INTERVAL", "UNSAFE_INTERVENING_SESSION"], default="")

    cutoff = pd.Timestamp(config["confirmation_signal_start_exclusive"]).date()
    frame = frame[frame.date > cutoff].copy()
    for universe, flag in (("basic", "universe_basic_liquid"), ("moderate", "universe_moderate_liquid")):
        for candidate in CANDIDATES:
            valid = frame[flag].fillna(False) & frame[f"valid_{candidate}"]
            ranked = rank_signal(frame, candidate, valid)
            frame.loc[ranked.index, f"{candidate}_rank_{universe}"] = ranked["rank"]
            frame.loc[ranked.index, f"{candidate}_pct_{universe}"] = ranked["percentile"]
            frame.loc[ranked.index, f"{candidate}_cross_section_count_{universe}"] = ranked["cross_section_count"]
    keep = frame.universe_basic_liquid.fillna(False) | frame.universe_moderate_liquid.fillna(False)
    return frame.loc[keep].drop(columns=["quality"]).sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def daily_statistics(panel: pd.DataFrame, candidate: str, future: int, universe: str,
                     minimum_cross_section: int) -> pd.DataFrame:
    pct = f"{candidate}_pct_{universe.lower().split('_')[0]}"
    count = f"{candidate}_cross_section_count_{universe.lower().split('_')[0]}"
    flag = f"universe_{universe.lower()}"
    valid = panel[flag].fillna(False) & panel[pct].notna() & panel[f"valid_future_{future}"]
    rows = []
    for day, group in panel.loc[valid, ["date", "session_position", pct, count, f"future_return_{future}"]].groupby("date", sort=True):
        factor = group[pct].to_numpy(float); outcome = group[f"future_return_{future}"].to_numpy(float)
        cs = int(group[count].iloc[0]); decile = np.minimum(np.floor(factor * 10).astype(int) + 1, 10)
        spread = outcome[decile == 10].mean() - outcome[decile == 1].mean() if cs >= minimum_cross_section else np.nan
        rows.append({"date": day, "session_position": int(group.session_position.iloc[0]),
                     "rank_ic": correlation(rank_average(factor), rank_average(outcome)),
                     "d10_d1_spread": spread, "stock_observations": len(group), "signal_cross_section_count": cs})
    return pd.DataFrame(rows)


def summarize(daily: pd.DataFrame) -> dict:
    if daily.empty:
        return {"mean_ic": np.nan, "median_ic": np.nan, "ic_positive_pct": np.nan, "valid_dates": 0,
                "stock_observations": 0, "median_cross_section_size": np.nan, "mean_d10_d1_spread": np.nan}
    return {"mean_ic": daily.rank_ic.mean(), "median_ic": daily.rank_ic.median(),
            "ic_positive_pct": 100 * daily.rank_ic.gt(0).mean(), "valid_dates": int(daily.rank_ic.notna().sum()),
            "stock_observations": int(daily.stock_observations.sum()),
            "median_cross_section_size": daily.signal_cross_section_count.median(),
            "mean_d10_d1_spread": daily.d10_d1_spread.mean()}


def analyze(panel: pd.DataFrame, config: dict) -> tuple[dict[str, pd.DataFrame], dict]:
    caches = {}; daily_rows=[]; summary_rows=[]; coverage=[]
    for universe in ("BASIC_LIQUID", "MODERATE_LIQUID"):
        for candidate in CANDIDATES:
            for horizon in FUTURES:
                daily = daily_statistics(panel, candidate, horizon, universe, config["minimum_cross_section"])
                caches[(candidate, horizon, universe)] = daily
                if not daily.empty:
                    temp=daily.copy();temp.insert(0,"future_horizon",horizon);temp.insert(0,"universe",universe);temp.insert(0,"candidate_id",candidate);daily_rows.append(temp)
                summary_rows.append({"candidate_id":candidate,"universe":universe,"future_horizon":horizon,**summarize(daily)})
                coverage.append({"candidate_id":candidate,"universe":universe,"future_horizon":horizon,
                    "first_confirmation_signal_date":daily.date.min() if not daily.empty else pd.NaT,
                    "last_usable_signal_date":daily.date.max() if not daily.empty else pd.NaT,
                    "valid_dates":int(daily.rank_ic.notna().sum()) if not daily.empty else 0,
                    "stock_observations":int(daily.stock_observations.sum()) if not daily.empty else 0,
                    "certified_end":config["certified_end"]})
    summary=pd.DataFrame(summary_rows); outputs={
      "confirmation_rank_ic_daily.csv":pd.concat(daily_rows,ignore_index=True) if daily_rows else pd.DataFrame(),
      "confirmation_rank_ic_summary.csv":summary,
      "confirmation_coverage.csv":pd.DataFrame(coverage),
      "universe_sensitivity.csv":summary.copy()}

    deciles=[];tails=[]
    for candidate in CANDIDATES:
      for horizon in FUTURES:
        pct=f"{candidate}_pct_basic";count=f"{candidate}_cross_section_count_basic"
        selected=panel[panel.universe_basic_liquid.fillna(False)&panel[pct].notna()&panel[f"valid_future_{horizon}"]].copy()
        selected=selected[selected[count].ge(config["minimum_cross_section"])]
        selected["bucket"]=np.minimum(np.floor(selected[pct]*10).astype(int)+1,10)
        outcome=selected[f"future_return_{horizon}"]
        bucket_means=[]
        for bucket in range(1,11):
          values=outcome[selected.bucket.eq(bucket)].dropna();bucket_means.append(values.mean())
          deciles.append({"candidate_id":candidate,"future_horizon":horizon,"bucket":bucket,"observation_count":len(values),
            "mean_future_return":values.mean(),"median_future_return":values.median(),"positive_return_pct":100*values.gt(0).mean()})
        mono=correlation(np.arange(1,11,dtype=float),rank_average(np.array(bucket_means,float)))
        for row in deciles[-10:]:row["d10_d1_spread"]=bucket_means[-1]-bucket_means[0];row["monotonicity"]=mono
        for fraction in config["tails"]:
          for side,mask in (("TOP",selected[pct].ge(1-fraction)),("BOTTOM",selected[pct].le(fraction))):
            values=outcome[mask].dropna();tails.append({"candidate_id":candidate,"future_horizon":horizon,"tail_fraction":fraction,
              "group":side,"observation_count":len(values),"mean_future_return":values.mean(),"median_future_return":values.median(),"positive_return_pct":100*values.gt(0).mean()})
          top=tails[-2]["mean_future_return"];bottom=tails[-1]["mean_future_return"]
          tails[-2]["top_bottom_spread"]=top-bottom;tails[-1]["top_bottom_spread"]=top-bottom
    outputs["confirmation_decile_returns.csv"]=pd.DataFrame(deciles);outputs["confirmation_tail_analysis.csv"]=pd.DataFrame(tails)

    non=[]; uncertainty=[]; loo=[]
    settings=config["uncertainty"]
    for candidate in CANDIDATES:
      for horizon in FUTURES:
        daily=caches[(candidate,horizon,"BASIC_LIQUID")]
        for offset in range(horizon):
          sample=daily[daily.session_position.mod(horizon).eq(offset)] if not daily.empty else daily
          non.append({"candidate_id":candidate,"future_horizon":horizon,"offset":offset,"mean_ic":sample.rank_ic.mean() if not sample.empty else np.nan,
            "valid_dates":len(sample),"positive":bool(sample.rank_ic.mean()>0) if not sample.empty else False,"spacing_valid":True})
        subset=pd.DataFrame(non[-horizon:]);mean_offset=subset.mean_ic.mean();positive_fraction=subset.mean_ic.gt(0).mean()
        for row in non[-horizon:]:row["offset_mean_ic"]=mean_offset;row["positive_offset_fraction"]=positive_fraction
        for stat,column,index in (("MEAN_RANK_IC","rank_ic",0),("MEAN_D10_D1_SPREAD","d10_d1_spread",1)):
          values=daily[column].dropna().to_numpy(float) if not daily.empty else np.array([])
          estimate,lo,hi=moving_block_bootstrap(values,max(10,2*horizon),settings["replications"],settings["seed"]+horizon*10+index+(5 if candidate=="REV05" else 20)*1000,settings["confidence_level"])
          uncertainty.append({"candidate_id":candidate,"future_horizon":horizon,"statistic":stat,"estimate":estimate,"ci_lower":lo,"ci_upper":hi,
            "replications":settings["replications"],"block_length":max(10,2*horizon),"valid_dates":len(values)})
        baseline=daily.rank_ic.mean() if not daily.empty else np.nan
        for day in daily.date if not daily.empty else []:
          estimate=daily.loc[daily.date.ne(day),"rank_ic"].mean()
          loo.append({"candidate_id":candidate,"future_horizon":horizon,"excluded_date":day,"baseline_mean_ic":baseline,
            "leave_one_date_out_mean_ic":estimate,"change":estimate-baseline,"sign_flip":bool(np.sign(estimate)!=np.sign(baseline))})
    outputs["confirmation_nonoverlap.csv"]=pd.DataFrame(non);outputs["confirmation_uncertainty.csv"]=pd.DataFrame(uncertainty);outputs["leave_one_date_out.csv"]=pd.DataFrame(loo)
    return outputs,caches


def classify(outputs: dict[str, pd.DataFrame], historical: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, str]:
    summary=outputs["confirmation_rank_ic_summary.csv"];non=outputs["confirmation_nonoverlap.csv"].drop_duplicates(["candidate_id","future_horizon"]);loo=outputs["leave_one_date_out.csv"]
    rows=[]
    for candidate in CANDIDATES:
        primary=summary[(summary.candidate_id==candidate)&(summary.universe=="BASIC_LIQUID")]
        moderate=summary[(summary.candidate_id==candidate)&(summary.universe=="MODERATE_LIQUID")]
        ppos=int(primary.mean_ic.gt(0).sum());mpos=int(moderate.mean_ic.gt(0).sum());npos=int(non[non.candidate_id==candidate].offset_mean_ic.gt(0).sum())
        min_dates=int(primary.valid_dates.min()); historical_positive=int(historical[historical.candidate_id==candidate].mean_rank_ic.gt(0).sum())
        supporting=set(primary.loc[primary.mean_ic.gt(0),"future_horizon"])
        flips=loo[(loo.candidate_id==candidate)&loo.future_horizon.isin(supporting)].sign_flip.any()
        directional=(historical_positive>=6 and ppos>=4 and mpos>=4 and npos>=4 and primary.mean_ic.mean()>0 and moderate.mean_ic.mean()>0 and not flips)
        if min_dates<20:label="INSUFFICIENT SAMPLE"
        elif directional and min_dates>=60:label="SUPPORTED"
        elif directional:label="SUPPORTIVE BUT SHORT SAMPLE"
        elif ppos in (2,3):label="MIXED"
        elif ppos in (0,1):label="CONTRADICTORY"
        else:label="PREREGISTRATION_RULE_GAP"
        rows.append({"candidate_id":candidate,"classification":label,"historical_positive_horizons":historical_positive,
          "confirmation_positive_horizons":ppos,"moderate_positive_horizons":mpos,"nonoverlap_positive_horizons":npos,
          "minimum_daily_ic_dates":min_dates,"leave_one_date_sign_flip":bool(flips),"directional_acceptance_passed":bool(directional)})
    result=pd.DataFrame(rows);labels=set(result.classification)
    if "PREREGISTRATION_RULE_GAP" in labels:overall="RESEARCH FURTHER"
    elif labels=={"SUPPORTED"}:overall="PASS FOR COMPLEMENTARITY RESEARCH"
    elif "SUPPORTED" in labels or labels=={"SUPPORTIVE BUT SHORT SAMPLE"}:overall="CONDITIONAL PASS"
    elif labels=={"CONTRADICTORY"}:overall="FAIL"
    else:overall="RESEARCH FURTHER"
    return result,overall
