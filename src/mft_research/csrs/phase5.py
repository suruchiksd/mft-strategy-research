"""Point-in-time NSE Bhavcopy ingestion and frozen CSRS validation."""

from __future__ import annotations

import gzip
import hashlib
import io
import math
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from mft_research.csrs.phase4 import correlation, moving_block_bootstrap, rank_average, summarize_daily
from mft_research.data.sectors import read_sectors

FORMATIONS = (5, 10, 20, 40, 60)
FUTURES = (1, 2, 3, 5, 10, 20)
UNIVERSES = ("BROAD_EQ", "BASIC_LIQUID", "MODERATE_LIQUID", "STRICT_SENSITIVITY")
TIERS = ("PRIMARY_VERIFIED", "BROAD_SENSITIVITY")
_XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _xlsx_frame(payload: bytes) -> pd.DataFrame:
    """Read the archive's one gzip-wrapped XLSX without an Excel dependency."""
    with zipfile.ZipFile(io.BytesIO(payload)) as book:
        root = ET.fromstring(book.read("xl/sharedStrings.xml"))
        strings = ["".join((node.text or "") for node in item.iter(f"{_XLSX_NS}t"))
                   for item in root.findall(f"{_XLSX_NS}si")]
        sheet = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str | None]] = []
        for row in sheet.iter(f"{_XLSX_NS}row"):
            values: list[str | None] = []
            for cell in row.findall(f"{_XLSX_NS}c"):
                column = 0
                for char in re.match(r"[A-Z]+", cell.attrib["r"]).group():
                    column = column * 26 + ord(char) - 64
                values.extend([None] * (column - len(values)))
                node = cell.find(f"{_XLSX_NS}v")
                value = "" if node is None else node.text
                if cell.attrib.get("t") == "s" and value != "":
                    value = strings[int(value)]
                values[column - 1] = value
            rows.append(values)
        width = max(map(len, rows))
        rows = [row + [None] * (width - len(row)) for row in rows]
        return pd.DataFrame(rows[1:], columns=[str(value).strip() for value in rows[0]])


def source_format(path: Path) -> str:
    return "OLD" if path.name.startswith("sec_bhavdata_full_") else "NEW"


def filename_date(path: Path) -> pd.Timestamp:
    token = re.search(r"(\d{8})", path.name).group(1)
    fmt = "%d%m%Y" if source_format(path) == "OLD" else "%Y%m%d"
    return pd.to_datetime(token, format=fmt)


def read_source(path: Path) -> tuple[pd.DataFrame, str]:
    raw = path.read_bytes()
    payload = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    packaging = "GZIP_CSV" if raw[:2] == b"\x1f\x8b" else "PLAIN_CSV"
    if payload[:2] == b"PK":
        return _xlsx_frame(payload), "GZIP_XLSX"
    return pd.read_csv(io.BytesIO(payload), dtype=str, keep_default_na=False), packaging


def canonicalize_source(frame: pd.DataFrame, fmt: str, source_file: str) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    for column in frame.select_dtypes(include=["object", "string"]).columns:
        frame[column] = frame[column].astype("string").str.strip()
    if fmt == "OLD":
        result = pd.DataFrame({
            "date": pd.to_datetime(frame["DATE1"], format="%d-%b-%Y").dt.date,
            "symbol": frame["SYMBOL"], "series": frame["SERIES"],
            "open": pd.to_numeric(frame["OPEN_PRICE"]), "high": pd.to_numeric(frame["HIGH_PRICE"]),
            "low": pd.to_numeric(frame["LOW_PRICE"]), "close": pd.to_numeric(frame["CLOSE_PRICE"]),
            "volume": pd.to_numeric(frame["TTL_TRD_QNTY"]),
            "turnover_rupees": pd.to_numeric(frame["TURNOVER_LACS"]) * 100_000,
            "isin": pd.Series(pd.NA, index=frame.index, dtype="string"),
            "instrument_id": pd.Series(pd.NA, index=frame.index, dtype="string"),
            "security_name": pd.Series(pd.NA, index=frame.index, dtype="string"),
        })
    else:
        result = pd.DataFrame({
            "date": pd.to_datetime(frame["TradDt"]).dt.date,
            "symbol": frame["TckrSymb"], "series": frame["SctySrs"],
            "open": pd.to_numeric(frame["OpnPric"]), "high": pd.to_numeric(frame["HghPric"]),
            "low": pd.to_numeric(frame["LwPric"]), "close": pd.to_numeric(frame["ClsPric"]),
            "volume": pd.to_numeric(frame["TtlTradgVol"]),
            "turnover_rupees": pd.to_numeric(frame["TtlTrfVal"]),
            "isin": frame["ISIN"].replace("", pd.NA),
            "instrument_id": frame["FinInstrmId"].replace("", pd.NA),
            "security_name": frame["FinInstrmNm"].replace("", pd.NA),
        })
    result["source_format"] = fmt
    result["source_file"] = source_file
    return result


def inspect_archive(root: Path) -> tuple[pd.DataFrame, list[Path]]:
    paths = sorted(path for path in root.glob("*/*") if path.is_file() and
                   (path.name.startswith("sec_bhavdata_full_") or path.name.startswith("BhavCopy_NSE_CM_")))
    rows = []
    for path in paths:
        frame, packaging = read_source(path)
        fmt = source_format(path)
        normalized = canonicalize_source(frame, fmt, str(path))
        dates = sorted(normalized.date.dropna().unique())
        internal = dates[0] if len(dates) == 1 else None
        rows.append({"source_file": str(path), "source_name": path.name, "source_format": fmt,
                     "packaging": packaging, "filename_date": filename_date(path).date(),
                     "internal_date": internal, "filename_matches_internal": filename_date(path).date() == internal,
                     "rows": len(frame), "eq_rows": int(normalized.series.eq("EQ").sum()),
                     "column_count": len(frame.columns), "file_size": path.stat().st_size,
                     "mtime_ns": path.stat().st_mtime_ns,
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    audit = pd.DataFrame(rows).sort_values(["internal_date", "source_name"], kind="stable")
    chosen = (audit.assign(_priority=~audit.filename_matches_internal)
              .sort_values(["internal_date", "_priority", "source_name"], kind="stable")
              .drop_duplicates("internal_date"))
    return audit, [Path(path) for path in chosen.source_file]


def build_identity(daily: pd.DataFrame) -> pd.DataFrame:
    base = daily.groupby("symbol", sort=True).agg(first_date=("date", "min"), last_date=("date", "max"),
                                                   observed_sessions=("date", "size")).reset_index()
    observed = daily.dropna(subset=["isin"])[["symbol", "isin", "date"]].drop_duplicates()
    by_isin = observed.groupby("isin").symbol.agg(lambda values: tuple(sorted(set(values))))
    aliases = {symbol: tuple(other for other in symbols if other != symbol)
               for symbols in by_isin[by_isin.map(len).gt(1)] for symbol in symbols}
    isin_count = observed.groupby("symbol").isin.nunique()
    base["known_alias"] = base.symbol.map(lambda symbol: "|".join(aliases.get(symbol, ())))
    base["observed_isin_count"] = base.symbol.map(isin_count).fillna(0).astype(int)
    base["continuity_status"] = np.select(
        [base.known_alias.ne(""), base.observed_isin_count.gt(1)],
        ["OBJECTIVE_SAME_ISIN_ALIAS_OBSERVED_NO_STITCH", "MULTIPLE_ISIN_OBSERVED_NO_IDENTITY_INFERENCE"],
        default="OBSERVED_SYMBOL_HISTORY_NOT_STITCHED")
    base["identity_ambiguity"] = base.known_alias.ne("") | base.observed_isin_count.gt(1)
    base["identity_policy"] = "exact_observed_symbol_no_fuzzy_merge"
    return base


def add_point_in_time_fields(daily: pd.DataFrame, config: dict, actions: pd.DataFrame,
                             sectors: pd.DataFrame) -> pd.DataFrame:
    daily = daily.sort_values(["symbol", "date"], kind="stable").reset_index(drop=True)
    session_map = {day: index for index, day in enumerate(sorted(daily.date.unique()))}
    daily["session_position"] = daily.date.map(session_map).astype("int32")
    grouped = daily.groupby("symbol", sort=False)
    daily["first_observed_date"] = grouped.date.transform("min")
    daily["history_sessions"] = grouped.cumcount() + 1
    daily["prior_history_sessions"] = daily.history_sessions - 1
    window = int(config["rolling_liquidity_sessions"])
    long_window = int(config["rolling_turnover_long_sessions"])
    daily["avg_volume_20"] = grouped.volume.rolling(window, min_periods=window).mean().reset_index(level=0, drop=True)
    daily["avg_turnover_20"] = grouped.turnover_rupees.rolling(window, min_periods=window).mean().reset_index(level=0, drop=True)
    daily["avg_turnover_60"] = grouped.turnover_rupees.rolling(long_window, min_periods=long_window).mean().reset_index(level=0, drop=True)
    daily["recent_presence_20"] = (daily.session_position - grouped.session_position.shift(window - 1)).eq(window - 1)
    daily["recent_presence_60"] = (daily.session_position - grouped.session_position.shift(long_window - 1)).eq(long_window - 1)
    for name, spec in config["universe_specs"].items():
        mask = (daily.close >= spec["minimum_close"]) & (daily.prior_history_sessions >= spec["minimum_prior_sessions"])
        if spec["minimum_avg_turnover_20"]:
            mask &= daily.recent_presence_20 & daily.avg_turnover_20.ge(spec["minimum_avg_turnover_20"])
        if spec["minimum_avg_volume_20"]:
            mask &= daily.recent_presence_20 & daily.avg_volume_20.ge(spec["minimum_avg_volume_20"])
        daily[f"universe_{name.lower()}"] = mask.fillna(False)
    action_day = (actions[actions.series.eq("EQ")].groupby(["symbol", "date"]).research_impact
                  .agg(lambda values: "|".join(sorted(set(values)))))
    keys = pd.MultiIndex.from_frame(daily[["symbol", "date"]])
    daily["corporate_action_status"] = action_day.reindex(keys).fillna("NO_RECORDED_EVENT").to_numpy()
    coverage_start = pd.Timestamp(config["corporate_action_coverage_start"]).date()
    coverage_end = pd.Timestamp(config["corporate_action_coverage_end"]).date()
    daily["corporate_action_coverage_status"] = np.where(
        daily.date.between(coverage_start, coverage_end),
        config["corporate_action_policy"]["ledger_silence_status"], "OUTSIDE_LEDGER_DATE_COVERAGE")
    daily = daily.merge(sectors[["symbol", "sector", "sector_code", "sector_mapping_status"]],
                        on="symbol", how="left", validate="many_to_one")
    daily["identity_status"] = "OBSERVED_SYMBOL_NOT_STITCHED"
    valid_ohlc = (daily.high.ge(daily[["open", "close", "low"]].max(axis=1)) &
                  daily.low.le(daily[["open", "close", "high"]].min(axis=1)) &
                  daily[["open", "high", "low", "close"]].gt(0).all(axis=1) & daily.volume.ge(0))
    daily["research_quality_status"] = np.where(valid_ohlc, "VALID_REPORTED_EQ_ROW", "INVALID_REPORTED_ROW")
    return daily.sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)


def load_historical_daily(root: Path, config: dict, actions: pd.DataFrame,
                          sector_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit, chosen = inspect_archive(root)
    frames = []
    for path in chosen:
        raw, _ = read_source(path)
        normalized = canonicalize_source(raw, source_format(path), str(path))
        frames.append(normalized[normalized.series.eq(config["series"])])
    daily = pd.concat(frames, ignore_index=True)
    if daily.duplicated(["symbol", "date"]).any():
        raise ValueError("Canonical Bhavcopy contains duplicate EQ symbol/date rows")
    symbols = sorted(daily.symbol.unique())
    sectors, sector_issues = read_sectors(sector_root, symbols)
    daily = add_point_in_time_fields(daily, config, actions, sectors)
    identity = build_identity(daily)
    return daily, audit, identity, sector_issues


def blocking_event_map(actions: pd.DataFrame, config: dict) -> dict[str, np.ndarray]:
    impacts = set(config["corporate_action_policy"]["primary_blocking_impacts"])
    selected = actions[actions.series.eq("EQ") & actions.research_impact.isin(impacts)]
    return {symbol: np.array(sorted(pd.Timestamp(day).to_datetime64() for day in group.date.unique()))
            for symbol, group in selected.groupby("symbol", sort=False)}


def interval_crosses(symbols: pd.Series, starts: pd.Series, ends: pd.Series,
                     event_map: dict[str, np.ndarray]) -> np.ndarray:
    result = np.zeros(len(symbols), dtype=bool)
    work = pd.DataFrame({"symbol": symbols.to_numpy(), "start": starts.to_numpy(), "end": ends.to_numpy()})
    for symbol, index in work.groupby("symbol", sort=False).groups.items():
        events = event_map.get(symbol)
        if events is None or len(events) == 0:
            continue
        positions = np.asarray(list(index), dtype=int)
        start = pd.to_datetime(work.loc[index, "start"]).to_numpy(dtype="datetime64[D]")
        end = pd.to_datetime(work.loc[index, "end"]).to_numpy(dtype="datetime64[D]")
        good = ~pd.isna(start) & ~pd.isna(end)
        left = np.searchsorted(events, start[good], side="right")
        right = np.searchsorted(events, end[good], side="right")
        result[positions[good]] = right > left
    return result


def prepare_intervals(daily: pd.DataFrame, config: dict, actions: pd.DataFrame) -> pd.DataFrame:
    result = daily[["date", "symbol", "close", "session_position"]].copy()
    grouped = daily.groupby("symbol", sort=False)
    events = blocking_event_map(actions, config)
    coverage_start = pd.Timestamp(config["corporate_action_coverage_start"]).date()
    coverage_end = pd.Timestamp(config["corporate_action_coverage_end"]).date()
    quality = daily.research_quality_status.eq("VALID_REPORTED_EQ_ROW")
    for horizon in FORMATIONS:
        start_close = grouped.close.shift(horizon)
        start_date = grouped.date.shift(horizon)
        start_position = grouped.session_position.shift(horizon)
        contiguous = (daily.session_position - start_position).eq(horizon)
        crossing = interval_crosses(daily.symbol, start_date, daily.date, events)
        base = quality & start_close.notna() & contiguous & ~crossing
        result[f"ret_{horizon}"] = np.where(base, daily.close / start_close - 1, np.nan)
        result[f"valid_factor_broad_{horizon}"] = base
        result[f"valid_factor_primary_{horizon}"] = base & start_date.ge(coverage_start) & daily.date.le(coverage_end)
    for horizon in FUTURES:
        target_close = grouped.close.shift(-horizon)
        target_date = grouped.date.shift(-horizon)
        target_position = grouped.session_position.shift(-horizon)
        contiguous = (target_position - daily.session_position).eq(horizon)
        crossing = interval_crosses(daily.symbol, daily.date, target_date, events)
        base = quality & target_close.notna() & contiguous & ~crossing
        result[f"future_ret_{horizon}"] = np.where(base, target_close / daily.close - 1, np.nan)
        result[f"valid_future_broad_{horizon}"] = base
        result[f"valid_future_primary_{horizon}"] = base & daily.date.ge(coverage_start) & target_date.le(coverage_end)
    return result


def rank_factor(intervals: pd.DataFrame, eligible: pd.Series, formation: int, tier: str) -> pd.DataFrame:
    suffix = "primary" if tier == "PRIMARY_VERIFIED" else "broad"
    valid = eligible & intervals[f"valid_factor_{suffix}_{formation}"]
    work = intervals.loc[valid, ["date", "symbol", f"ret_{formation}"]].copy()
    work["_index"] = work.index
    work = work.sort_values(["date", f"ret_{formation}", "symbol"], kind="stable")
    work["rank"] = work.groupby("date", sort=False).cumcount() + 1
    work["cross_section_count"] = work.groupby("date", sort=False).symbol.transform("size")
    work["percentile"] = np.where(work.cross_section_count.gt(1),
                                  (work["rank"] - 1) / (work.cross_section_count - 1), 0.5)
    return work.set_index("_index").sort_index()


def _corr(group: pd.DataFrame) -> float:
    if len(group) < 2 or group["rank"].nunique() < 2 or group["outcome"].nunique() < 2:
        return np.nan
    return float(group["rank"].corr(group["outcome"].rank(method="average")))


def daily_statistics(work: pd.DataFrame, minimum_decile: int = 10) -> pd.DataFrame:
    if work.empty:
        return pd.DataFrame(columns=["date", "ic", "daily_spread", "observations", "cross_section_count"])
    work = work.copy()
    work["decile"] = np.where(work.cross_section_count.ge(minimum_decile),
                              ((work["rank"] - 1) * 10 // work.cross_section_count) + 1, 0).astype(int)
    grouped = work.groupby("date", sort=True)
    # Spearman is Pearson correlation of within-date average ranks. The factor's
    # deterministic ordinal is reranked after unsafe outcomes are removed.
    work["x"] = grouped["rank"].rank(method="average")
    work["y"] = grouped["outcome"].rank(method="average")
    work["xx"] = work.x * work.x; work["yy"] = work.y * work.y; work["xy"] = work.x * work.y
    moments = work.groupby("date", sort=True).agg(
        observations=("symbol","size"), cross_section_count=("cross_section_count","first"),
        sx=("x","sum"), sy=("y","sum"), sxx=("xx","sum"), syy=("yy","sum"), sxy=("xy","sum"))
    numerator = moments.sxy - moments.sx * moments.sy / moments.observations
    denominator = np.sqrt((moments.sxx - moments.sx.pow(2) / moments.observations) *
                          (moments.syy - moments.sy.pow(2) / moments.observations))
    result = moments[["observations","cross_section_count"]].copy()
    result["ic"] = numerator / denominator.replace(0,np.nan)
    tails = work[work.decile.between(1,10)].groupby(["date","decile"]).outcome.agg(["sum","count"])
    sums = tails["sum"].unstack(fill_value=0); counts = tails["count"].unstack(fill_value=0)
    for decile in range(1,11):
        result[f"q{decile}_sum"] = sums.get(decile,pd.Series(0,index=result.index)).reindex(result.index,fill_value=0)
        result[f"q{decile}_count"] = counts.get(decile,pd.Series(0,index=result.index)).reindex(result.index,fill_value=0)
    result["daily_spread"] = np.where(result.q1_count.gt(0)&result.q10_count.gt(0),
        result.q10_sum/result.q10_count-result.q1_sum/result.q1_count,np.nan)
    columns=["ic","daily_spread","observations","cross_section_count"]+[item for q in range(1,11) for item in (f"q{q}_sum",f"q{q}_count")]
    return result.reset_index()[["date",*columns]]


def _pooled_tail(work: pd.DataFrame, fraction: float, top: bool) -> dict:
    k = np.ceil(work.cross_section_count * fraction)
    mask = work["rank"].gt(work.cross_section_count - k) if top else work["rank"].le(k)
    values = work.loc[mask, "outcome"]
    return {"count": len(values), "mean": values.mean(), "median": values.median(),
            "positive_pct": 100 * values.gt(0).mean() if len(values) else np.nan}


def analyze_all(daily: pd.DataFrame, intervals: pd.DataFrame, config: dict) -> tuple[dict[str, pd.DataFrame], dict]:
    all_summary=[]; yearly=[]; expanding=[]; fixed=[]; nonoverlap=[]; uncertainty=[]; caches={}; ranks={}
    calendar = sorted(daily.date.unique()); positions = {day: index for index, day in enumerate(calendar)}
    uc = config["uncertainty"]
    for universe in UNIVERSES:
        eligible = daily[f"universe_{universe.lower()}"]
        for tier in TIERS:
            suffix = "primary" if tier == "PRIMARY_VERIFIED" else "broad"
            for formation in FORMATIONS:
                ranked = rank_factor(intervals, eligible, formation, tier)
                ranks[(universe,tier,formation)] = ranked
                for future in FUTURES:
                    outcome_valid = intervals[f"valid_future_{suffix}_{future}"]
                    idx = ranked.index[outcome_valid.reindex(ranked.index).fillna(False)]
                    work = ranked.loc[idx, ["date","symbol","rank","percentile","cross_section_count"]].copy()
                    work["outcome"] = intervals.loc[idx, f"future_ret_{future}"]
                    pair_daily = daily_statistics(work)
                    caches[(universe,tier,formation,future)] = pair_daily
                    stats = summarize_daily(pair_daily)
                    pooled=[]
                    for q in range(1,11):
                        count=pair_daily[f"q{q}_count"].sum(); pooled.append(pair_daily[f"q{q}_sum"].sum()/count if count else np.nan)
                    row={"analysis_tier":tier,"universe":universe,"formation_horizon":formation,"future_horizon":future,
                         **stats,"ic_positive_pct":100*pair_daily.ic.gt(0).mean() if len(pair_daily) else np.nan,
                         "ic_negative_pct":100*pair_daily.ic.lt(0).mean() if len(pair_daily) else np.nan,
                         "median_cross_section_count":pair_daily.cross_section_count.median() if len(pair_daily) else np.nan,
                         "mean_cross_section_count":pair_daily.cross_section_count.mean() if len(pair_daily) else np.nan,
                         "d1_mean":pooled[0],"d10_mean":pooled[9],"d10_d1_spread":pooled[9]-pooled[0],
                         "decile_monotonicity":correlation(np.arange(1,11,dtype=float),rank_average(np.asarray(pooled,dtype=float))) if np.isfinite(pooled).all() else np.nan}
                    for fraction in (0.05,0.10,0.20):
                        top=_pooled_tail(work,fraction,True); bottom=_pooled_tail(work,fraction,False); label=int(fraction*100)
                        for key,value in top.items(): row[f"top_{label}_{key}"]=value
                        for key,value in bottom.items(): row[f"bottom_{label}_{key}"]=value
                        row[f"top_bottom_{label}_spread"]=top["mean"]-bottom["mean"]
                    all_summary.append(row)
                    for year in config["evaluation_years"]:
                        selected=pair_daily[pd.to_datetime(pair_daily.date).dt.year.eq(year)]; st=summarize_daily(selected)
                        history=pair_daily[pd.to_datetime(pair_daily.date).dt.year.lt(year)]
                        yearly.append({"analysis_tier":tier,"universe":universe,"year":year,
                                       "formation_horizon":formation,"future_horizon":future,**st,
                                       "ic_positive_pct":100*selected.ic.gt(0).mean() if len(selected) else np.nan})
                        expanding.append({"analysis_tier":tier,"universe":universe,"evaluation_year":year,
                            "history_end_year":year-1,"formation_horizon":formation,"future_horizon":future,
                            **{f"history_{key}":value for key,value in summarize_daily(history).items()},
                            **{f"evaluation_{key}":value for key,value in st.items()}})
                    for period in config["fixed_periods"]:
                        start=pd.Timestamp(period["start"]).date(); end=pd.Timestamp(period["end"]).date(); selected=pair_daily[pair_daily.date.between(start,end)]
                        fixed.append({"analysis_tier":tier,"universe":universe,"period":period["name"],
                                      "formation_horizon":formation,"future_horizon":future,**summarize_daily(selected)})
                    date_positions=pair_daily.date.map(positions).to_numpy() if len(pair_daily) else np.array([])
                    for offset in range(future):
                        selected=pair_daily[date_positions % future == offset] if len(pair_daily) else pair_daily
                        nonoverlap.append({"analysis_tier":tier,"universe":universe,"formation_horizon":formation,
                                           "future_horizon":future,"offset":offset,**summarize_daily(selected)})
                    block=max(10,2*future)
                    for stat,column,stat_index in (("MEAN_RANK_IC","ic",0),("MEAN_DAILY_D10_D1_SPREAD","daily_spread",1)):
                        values=pair_daily[column].dropna().to_numpy(float); seed=uc["seed"]+UNIVERSES.index(universe)*100000+TIERS.index(tier)*50000+formation*1000+future*10+stat_index
                        estimate,lower,upper=moving_block_bootstrap(values,block,uc["replications"],seed,uc["confidence_level"])
                        pvalue=block_bootstrap_pvalue(values,block,uc["replications"],seed+1)
                        uncertainty.append({"analysis_tier":tier,"universe":universe,"formation_horizon":formation,
                                            "future_horizon":future,"statistic":stat,"estimate":estimate,"ci_lower":lower,"ci_upper":upper,
                                            "raw_p_value":pvalue,"block_length_sessions":block,"replications":uc["replications"],"seed":seed})
    outputs={"summary":pd.DataFrame(all_summary),"yearly":pd.DataFrame(yearly),"expanding":pd.DataFrame(expanding),"fixed":pd.DataFrame(fixed),
             "nonoverlap":pd.DataFrame(nonoverlap),"uncertainty":pd.DataFrame(uncertainty)}
    return outputs,{"cache":caches,"ranks":ranks}


def block_bootstrap_pvalue(values: np.ndarray, block_length: int, replications: int, seed: int) -> float:
    values=values[np.isfinite(values)]
    if len(values)==0: return np.nan
    centered=values-values.mean(); n=len(values); length=min(block_length,n); blocks=math.ceil(n/length); offsets=np.arange(length); rng=np.random.default_rng(seed); observed=abs(values.mean()); exceed=0
    for _ in range(replications):
        starts=rng.integers(0,n,size=blocks); sample=centered[((starts[:,None]+offsets)%n).ravel()[:n]]
        exceed += abs(sample.mean()) >= observed
    return (exceed+1)/(replications+1)


def adjust_pvalues(values: pd.Series, method: str) -> np.ndarray:
    p=values.to_numpy(float); n=len(p); order=np.argsort(p); adjusted=np.empty(n,float)
    if method=="BENJAMINI_HOCHBERG":
        ranked=p[order]*n/np.arange(1,n+1); ranked=np.minimum.accumulate(ranked[::-1])[::-1]
    elif method=="HOLM":
        ranked=p[order]*(n-np.arange(n)); ranked=np.maximum.accumulate(ranked)
    else: raise ValueError(method)
    adjusted[order]=np.minimum(ranked,1); return adjusted


def multiple_testing(uncertainty: pd.DataFrame, alpha: float) -> pd.DataFrame:
    frames=[]
    for keys,group in uncertainty.groupby(["analysis_tier","universe","statistic"],sort=True):
        group=group.copy()
        for method in ("BENJAMINI_HOCHBERG","HOLM"):
            group[f"{method.lower()}_p_value"] = adjust_pvalues(group.raw_p_value,method)
            group[f"{method.lower()}_reject_{alpha}"] = group[f"{method.lower()}_p_value"].le(alpha)
        frames.append(group)
    return pd.concat(frames,ignore_index=True)


def universe_counts(daily: pd.DataFrame, current_symbols: set[str]) -> tuple[pd.DataFrame,pd.DataFrame]:
    rows=[]; membership=[]
    for universe in UNIVERSES:
        mask=daily[f"universe_{universe.lower()}"]
        work=daily.loc[mask,["date","symbol"]].copy(); work["year"]=pd.to_datetime(work.date).dt.year
        per_day=work.groupby("date").symbol.nunique()
        for day,count in per_day.items(): rows.append({"date":day,"year":day.year,"universe":universe,"eligible_symbols":count})
        for year,g in work.groupby("year"):
            total=len(g); represented=g.symbol.isin(current_symbols).sum()
            membership.append({"year":year,"universe":universe,"eligible_observations":total,
                               "current120_observations":represented,"current120_observation_pct":100*represented/total if total else np.nan,
                               "distinct_symbols":g.symbol.nunique(),"outside_current120_symbols":len(set(g.symbol)-current_symbols)})
    counts=pd.DataFrame(rows); summary=(counts.groupby(["year","universe"]).eligible_symbols
            .agg(["min","median","mean","max"]).reset_index())
    return counts,summary.merge(pd.DataFrame(membership),on=["year","universe"],how="left")


def current120_comparison(point_summary: pd.DataFrame, point_yearly: pd.DataFrame, point_uncertainty: pd.DataFrame,
                          current_panel: pd.DataFrame, current_uncertainty: pd.DataFrame,
                          current_stability: pd.DataFrame, certified_end: str) -> pd.DataFrame:
    from mft_research.csrs.phase4 import build_daily_cache
    panel=current_panel[current_panel.date.le(pd.Timestamp(certified_end).date())]
    cache=build_daily_cache(panel,FORMATIONS,FUTURES)
    current=[]
    for (formation,future),daily_pair in cache.items():
        st=summarize_daily(daily_pair)
        current.append({"formation_horizon":formation,"future_horizon":future,
                        "current120_mean_ic":st["mean_ic"],"current120_spread":st["mean_daily_d10_d1_spread"],
                        "current120_median_cross_section":daily_pair.cross_section_count.median()})
    base=pd.DataFrame(current)
    ci=(current_uncertainty[current_uncertainty.statistic.eq("MEAN_RANK_IC")]
        [["formation_horizon","future_horizon","ci_lower","ci_upper"]]
        .rename(columns={"ci_lower":"current120_ci_lower","ci_upper":"current120_ci_upper"}))
    point_ci=(point_uncertainty[point_uncertainty.statistic.eq("MEAN_RANK_IC")]
        [["analysis_tier","universe","formation_horizon","future_horizon","ci_lower","ci_upper"]]
        .rename(columns={"ci_lower":"point_ci_lower","ci_upper":"point_ci_upper"}))
    stability=current_stability[["formation_horizon","future_horizon","ic_positive_fraction"]].rename(
        columns={"ic_positive_fraction":"current120_year_positive_fraction"})
    point_year=(point_yearly.groupby(["analysis_tier","universe","formation_horizon","future_horizon"])
                .mean_ic.agg(lambda values: values.gt(0).mean()).reset_index(name="point_year_positive_fraction"))
    point=point_summary.rename(columns={"mean_ic":"point_mean_ic","mean_daily_d10_d1_spread":"point_spread",
                                        "median_cross_section_count":"point_median_cross_section"})
    result=(point.merge(base,on=["formation_horizon","future_horizon"],validate="many_to_one")
            .merge(ci,on=["formation_horizon","future_horizon"],validate="many_to_one")
            .merge(point_ci,on=["analysis_tier","universe","formation_horizon","future_horizon"],validate="one_to_one")
            .merge(stability,on=["formation_horizon","future_horizon"],validate="many_to_one")
            .merge(point_year,on=["analysis_tier","universe","formation_horizon","future_horizon"],validate="one_to_one"))
    result["ic_change_point_minus_current120"]=result.point_mean_ic-result.current120_mean_ic
    result["spread_change_point_minus_current120"]=result.point_spread-result.current120_spread
    result["ic_sign_preserved"]=np.sign(result.point_mean_ic).eq(np.sign(result.current120_mean_ic))
    result["year_stability_change"]=result.point_year_positive_fraction-result.current120_year_positive_fraction
    result["cross_section_median_change"]=result.point_median_cross_section-result.current120_median_cross_section
    result["current120_ci_width"]=result.current120_ci_upper-result.current120_ci_lower
    result["point_ci_width"]=result.point_ci_upper-result.point_ci_lower
    result["ci_width_change"]=result.point_ci_width-result.current120_ci_width
    return result


def software_influence(daily: pd.DataFrame, intervals: pd.DataFrame, config: dict,
                       baseline: pd.DataFrame) -> pd.DataFrame:
    software=set(daily.loc[daily.sector.eq("software") & daily.sector_mapping_status.eq("UNIQUE"),"symbol"])
    rows=[]
    for universe in UNIVERSES:
        eligible=daily[f"universe_{universe.lower()}"] & ~daily.symbol.isin(software)
        for formation in FORMATIONS:
            ranked=rank_factor(intervals,eligible,formation,"PRIMARY_VERIFIED")
            for future in FUTURES:
                idx=ranked.index[intervals.loc[ranked.index,f"valid_future_primary_{future}"]]
                work=ranked.loc[idx,["date","symbol","rank","percentile","cross_section_count"]].copy()
                work["outcome"]=intervals.loc[idx,f"future_ret_{future}"]
                stats=summarize_daily(daily_statistics(work))
                base=baseline[(baseline.analysis_tier.eq("PRIMARY_VERIFIED")) & baseline.universe.eq(universe) &
                              baseline.formation_horizon.eq(formation) & baseline.future_horizon.eq(future)].iloc[0]
                rows.append({"universe":universe,"formation_horizon":formation,"future_horizon":future,
                             "excluded_sector":"software","excluded_symbol_count":len(software),
                             "baseline_mean_ic":base.mean_ic,"excluded_mean_ic":stats["mean_ic"],
                             "mean_ic_change":stats["mean_ic"]-base.mean_ic,
                             "baseline_spread":base.mean_daily_d10_d1_spread,
                             "excluded_spread":stats["mean_daily_d10_d1_spread"],
                             "spread_change":stats["mean_daily_d10_d1_spread"]-base.mean_daily_d10_d1_spread})
    return pd.DataFrame(rows)


def classify_formations(summary: pd.DataFrame, yearly: pd.DataFrame, fixed: pd.DataFrame,
                        testing: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    primary=summary[summary.analysis_tier.eq("PRIMARY_VERIFIED")]
    primary_year=yearly[yearly.analysis_tier.eq("PRIMARY_VERIFIED")]
    holdout=fixed[(fixed.analysis_tier.eq("PRIMARY_VERIFIED")) & fixed.period.eq("OUT_OF_SAMPLE_HOLDOUT")]
    mt=testing[(testing.analysis_tier.eq("PRIMARY_VERIFIED")) & testing.statistic.eq("MEAN_RANK_IC")]
    for formation in FORMATIONS:
        full=primary[primary.formation_horizon.eq(formation)]
        hold=holdout[holdout.formation_horizon.eq(formation)]
        per_universe=full.groupby("universe").mean_ic.apply(lambda values: int(values.gt(0).sum()))
        hold_per=hold.groupby("universe").mean_ic.apply(lambda values: int(values.gt(0).sum()))
        yearly_sign=(primary_year[primary_year.formation_horizon.eq(formation)]
                     .groupby(["universe","future_horizon"]).mean_ic.apply(lambda values: values.gt(0).mean()))
        fdr=int(mt.loc[mt.formation_horizon.eq(formation), "benjamini_hochberg_reject_0.05"].sum())
        if per_universe.ge(5).all() and hold_per.ge(5).all() and yearly_sign.ge(.5).mean()>=.8 and fdr>=4:
            label="ROBUST"
        elif per_universe.le(1).all() and hold_per.le(2).all():
            label="REVERSAL-LIKE"
        elif per_universe.ge(4).sum()>=3 and hold_per.ge(4).sum()>=3:
            label="PROMISING"
        elif per_universe.le(1).all() and hold_per.sum()<12:
            label="FAIL"
        elif per_universe.between(2,4).any() or hold_per.between(2,4).any():
            label="INCONCLUSIVE"
        else:
            label="FAIL"
        rows.append({"formation_horizon":formation,"classification":label,
                     "positive_pairs_broad_eq":int(per_universe.get("BROAD_EQ",0)),
                     "positive_pairs_basic_liquid":int(per_universe.get("BASIC_LIQUID",0)),
                     "positive_pairs_moderate_liquid":int(per_universe.get("MODERATE_LIQUID",0)),
                     "positive_pairs_strict_sensitivity":int(per_universe.get("STRICT_SENSITIVITY",0)),
                     "positive_holdout_pairs_total":int(hold_per.sum()),
                     "fraction_year_cells_positive":float(yearly_sign.mean()),
                     "bh_fdr_rejections_across_universes":fdr,
                     "classification_rule":"frozen_cross_universe_chronology_uncertainty_rule"})
    return pd.DataFrame(rows)


def audit_summary(audit: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    selected=(audit.assign(_priority=~audit.filename_matches_internal)
              .sort_values(["internal_date","_priority","source_name"],kind="stable").drop_duplicates("internal_date"))
    selected["year"]=pd.to_datetime(selected.internal_date).dt.year
    canonical=daily.groupby(pd.to_datetime(daily.date).dt.year).agg(canonical_eq_rows=("symbol","size"),unique_eq_symbols=("symbol","nunique"))
    rows=[]
    for (year,fmt),group in audit.assign(year=pd.to_datetime(audit.internal_date).dt.year).groupby(["year","source_format"]):
        chosen=selected[(selected.year.eq(year)) & selected.source_format.eq(fmt)]
        rows.append({"year":year,"format":fmt,"archive_files":len(group),"canonical_sessions":chosen.internal_date.nunique(),
                     "first_internal_date":chosen.internal_date.min(),"last_internal_date":chosen.internal_date.max(),
                     "canonical_all_rows":int(chosen.rows.sum()),"canonical_eq_rows":int(chosen.eq_rows.sum()),
                     "unique_eq_symbols":int(canonical.loc[year,"unique_eq_symbols"]),
                     "filename_date_mismatches":int((~group.filename_matches_internal).sum()),
                     "packaging_exception_files":int(group.packaging.eq("GZIP_XLSX").sum())})
    return pd.DataFrame(rows).sort_values(["year","format"])
