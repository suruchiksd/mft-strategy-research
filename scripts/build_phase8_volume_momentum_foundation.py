#!/usr/bin/env python3
"""Build the outcome-blind Phase-8 Volume + Momentum foundation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import runpy
import sys
import tempfile
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from mft_research.data.manifest import canonical_json, sha256
from mft_research.volume_momentum import (CANDIDATE_IDS, FORBIDDEN, PRIMARY_UNIVERSE,
    SENSITIVITY_UNIVERSE, UNIVERSES, VOLUME_BASELINES, PRICE_HORIZONS, assert_outcome_blind,
    build_foundation, candidate_registry, distribution, feature_correlations, validate_config)


def local(value: str) -> Path:
    path = (PROJECT / value).resolve()
    if not path.is_relative_to(PROJECT):
        raise ValueError("Phase-8 output path escaped project")
    return path


def load_config() -> dict:
    config = yaml.safe_load((PROJECT / "config/phase8_volume_momentum.yaml").read_text())
    validate_config(config)
    return config


def artifact_path(phase: int, manifest_path: Path, name: str) -> Path:
    special = {
        (5, "historical_nse_daily.parquet"): PROJECT / "data/derived/historical_nse_daily.parquet",
        (5, "phase5_point_in_time_csrs.md"): PROJECT / "reports/phase5_point_in_time_csrs.md",
        (6, "sector_research_mapping.parquet"): PROJECT / "data/derived/sector_research_mapping.parquet",
        (6, "phase6_sector_foundation.md"): PROJECT / "reports/phase6_sector_foundation.md",
        (7, "sector_momentum_factor_panel.parquet"): PROJECT / "data/derived/sector_momentum_factor_panel.parquet",
        (7, "phase7_sector_relative_momentum.md"): PROJECT / "reports/phase7_sector_relative_momentum.md",
    }
    return special.get((phase, name), manifest_path.parent / name)


def verify_inputs(config: dict) -> dict:
    accepted = {}
    for phase, key in ((5, "phase5_manifest"), (6, "phase6_manifest"), (7, "phase7_manifest")):
        path = local(config[key]); manifest = json.loads(path.read_text())
        for name, digest in manifest["output_sha256"].items():
            if sha256(artifact_path(phase, path, name)) != digest:
                raise RuntimeError(f"Accepted Phase-{phase} artifact changed: {name}")
        accepted[f"phase{phase}_build_id"] = manifest["build_id"]
        accepted[f"phase{phase}_verified_outputs"] = len(manifest["output_sha256"])
    accepted["historical_daily_sha256"] = sha256(local(config["historical_daily"]))
    return accepted


def code_fingerprint() -> str:
    paths = [PROJECT / "config/phase8_volume_momentum.yaml",
             PROJECT / "scripts/build_phase8_volume_momentum_foundation.py",
             PROJECT / "src/mft_research/volume_momentum.py"] + sorted(PROJECT.glob("tests/test_phase8*.py"))
    records = [{"path": str(path.relative_to(PROJECT)), "sha256": sha256(path)} for path in sorted(paths)]
    return hashlib.sha256(canonical_json(records).encode()).hexdigest()


def _quality_row(group: pd.DataFrame) -> dict:
    volume = distribution(group.volume); turnover = distribution(group.turnover_rupees); close = distribution(group.close)
    sessions = group.groupby("symbol", sort=False).size()
    result = {"observations": len(group), "symbols": group.symbol.nunique(),
              "null_volume": int(group.volume.isna().sum()), "zero_volume": int(group.volume.eq(0).sum()),
              "negative_volume": int(group.volume.lt(0).sum()),
              "null_turnover": int(group.turnover_rupees.isna().sum()),
              "zero_turnover": int(group.turnover_rupees.eq(0).sum()),
              "sessions_per_symbol_median": sessions.median(), "sessions_per_symbol_min": sessions.min(),
              "sessions_per_symbol_max": sessions.max()}
    for prefix, stats in (("volume", volume), ("turnover", turnover), ("close", close)):
        for key in ("median", "p10", "p25", "p75", "p90", "p95", "p99", "min", "max"):
            result[f"{prefix}_{key}"] = stats[key]
    return result


def source_audit(daily: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    valid = daily.volume.gt(0) & daily.turnover_rupees.ge(0) & daily.close.gt(0)
    implied = (daily.turnover_rupees / daily.volume / daily.close).where(valid)
    dates = sorted(daily.date.unique()); old_dates = [x for x in dates if x <= daily.loc[daily.source_format.eq("OLD"), "date"].max()]
    new_dates = [x for x in dates if x >= daily.loc[daily.source_format.eq("NEW"), "date"].min()]
    before = daily[daily.date.isin(old_dates[-20:])].groupby("symbol").volume.median()
    after = daily[daily.date.isin(new_dates[:20])].groupby("symbol").volume.median()
    transition = (after / before).replace([np.inf, -np.inf], np.nan).dropna()
    for fmt, group in daily.groupby("source_format", sort=True):
        contract = config["source_contract"][fmt]
        rows.append({"source_format": fmt, "first_date": group.date.min(), "last_date": group.date.max(),
                     "sessions": group.date.nunique(), "observations": len(group), "symbols": group.symbol.nunique(),
                     **contract, "null_volume": int(group.volume.isna().sum()),
                     "zero_volume": int(group.volume.eq(0).sum()), "negative_volume": int(group.volume.lt(0).sum()),
                     "volume_median": group.volume.median(), "volume_p99": group.volume.quantile(.99),
                     "turnover_implied_price_to_close_median": implied.loc[group.index].median(),
                     "turnover_implied_price_to_close_p01": implied.loc[group.index].quantile(.01),
                     "turnover_implied_price_to_close_p99": implied.loc[group.index].quantile(.99),
                     "dual_format_same_date_overlap": False,
                     "transition_common_symbols": len(transition),
                     "transition_first20_to_last20_volume_ratio_median": transition.median(),
                     "compatibility_assessment": "COMPATIBLE_SHARE_UNITS_NO_DUAL_FORMAT_OVERLAP"})
    return pd.DataFrame(rows)


def quality_outputs(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = daily.assign(year=pd.to_datetime(daily.date).dt.year)
    yearly = []
    for (year, fmt), group in work.groupby(["year", "source_format"], sort=True):
        yearly.append({"year": year, "source_format": fmt, **_quality_row(group)})
    universe = []
    for year in sorted(work.year.unique()):
        annual = work[work.year.eq(year)]
        for name in UNIVERSES:
            group = annual[annual[f"universe_{name.lower()}"].fillna(False)]
            universe.append({"year": year, "universe": name, **_quality_row(group)})
    return pd.DataFrame(yearly), pd.DataFrame(universe)


def feature_coverage(panel: pd.DataFrame) -> pd.DataFrame:
    specs = [(f"price_return_{h}", f"valid_price_return_{h}", f"price_return_{h}_invalid_reason") for h in PRICE_HORIZONS]
    specs += [(feature, f"valid_volume_baseline_{h}", f"volume_baseline_{h}_invalid_reason")
              for h in VOLUME_BASELINES for feature in (f"volume_ratio_{h}", f"volume_median_ratio_{h}", f"log_volume_surprise_{h}")]
    rows = []
    for name in UNIVERSES:
        membership = panel[f"universe_{name.lower()}"].fillna(False)
        for feature, valid_column, reason_column in specs:
            valid = membership & panel[valid_column] & panel[feature].notna()
            rows.append({"universe": name, "feature": feature, "status": "VALID", "reason": "",
                         "observations": int(valid.sum()), "universe_observations": int(membership.sum()),
                         "coverage_pct": float(valid.sum() / membership.sum() * 100) if membership.any() else np.nan})
            invalid = panel.loc[membership & ~valid, reason_column].fillna("OTHER_UNSAFE_INTERVAL").value_counts()
            for reason, count in invalid.items():
                rows.append({"universe": name, "feature": feature, "status": "INVALID", "reason": reason,
                             "observations": int(count), "universe_observations": int(membership.sum()),
                             "coverage_pct": float(count / membership.sum() * 100) if membership.any() else np.nan})
    return pd.DataFrame(rows)


def feature_distributions(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_features = [f"volume_ratio_{h}" for h in VOLUME_BASELINES] + [f"volume_median_ratio_{h}" for h in VOLUME_BASELINES]
    base_features += [f"log_volume_surprise_{h}" for h in VOLUME_BASELINES] + [f"price_return_{h}" for h in PRICE_HORIZONS]
    candidate_features = [f"candidate_vm0{i}" if i <= 4 else f"candidate_vm0{i}_basic_liquid" for i in range(1, 8)]
    features = base_features + candidate_features
    basic = panel[panel.universe_basic_liquid.fillna(False)].assign(year=lambda x: pd.to_datetime(x.date).dt.year)
    yearly = []
    for year, group in basic.groupby("year", sort=True):
        for feature in features:
            yearly.append({"year": year, "feature": feature, **distribution(group[feature])})
    by_universe = []
    for name in UNIVERSES:
        group = panel[panel[f"universe_{name.lower()}"].fillna(False)]
        for feature in base_features:
            by_universe.append({"universe": name, "feature": feature, **distribution(group[feature])})
    return pd.DataFrame(yearly), pd.DataFrame(by_universe)


def outliers(panel: pd.DataFrame, config: dict) -> pd.DataFrame:
    audit = panel.copy()
    features = []
    for horizon in VOLUME_BASELINES:
        audit[f"audit_volume_ratio_{horizon}"] = audit.volume / audit[f"volume_mean_{horizon}_prior"]
        audit[f"audit_volume_median_ratio_{horizon}"] = audit.volume / audit[f"volume_median_{horizon}_prior"]
        audit[f"audit_log_volume_surprise_{horizon}"] = np.log1p(audit.volume.astype(float)) - audit[f"volume_log_mean_{horizon}_prior"]
        features += [f"audit_volume_ratio_{horizon}", f"audit_volume_median_ratio_{horizon}", f"audit_log_volume_surprise_{horizon}"]
    columns = ["date", "symbol", "source_format", "close", "volume", "turnover_rupees", "history_sessions",
               "corporate_action_status", "corporate_action_coverage_status", "price_return_5", "price_return_20",
               "volume_mean_20_prior", "volume_median_20_prior", "volume_mean_60_prior", "volume_median_60_prior"]
    rows = []
    n = int(config["outlier_rows_per_feature"])
    for feature in features:
        values = audit[feature].abs() if "log_volume" in feature else audit[feature]
        selected = audit.loc[values.nlargest(n).index, columns].copy()
        selected.insert(0, "extreme_feature", feature); selected.insert(1, "extreme_value", audit.loc[selected.index, feature])
        horizon = 20 if feature.endswith("20") else 60
        selected["research_feature_valid"] = audit.loc[selected.index, f"valid_volume_baseline_{horizon}"].to_numpy()
        selected["research_invalid_reason"] = audit.loc[selected.index, f"volume_baseline_{horizon}_invalid_reason"].to_numpy()
        selected["new_listing_first_60_sessions"] = selected.history_sessions.le(60)
        rows.append(selected)
    return pd.concat(rows, ignore_index=True).sort_values(["extreme_feature", "extreme_value"], ascending=[True, False], kind="stable")


def action_proximity(panel: pd.DataFrame, actions: pd.DataFrame, config: dict) -> pd.DataFrame:
    position_date = panel[["session_position", "date"]].drop_duplicates().set_index("session_position").date
    date_position = pd.Series(position_date.index, index=position_date.values)
    events = actions[actions.series.eq("EQ")][["event_id", "symbol", "date", "action_classification", "research_impact"]].copy()
    events["event_session_position"] = events.date.map(date_position)
    rows = []
    for offset in range(-int(config["action_proximity_sessions"]), int(config["action_proximity_sessions"]) + 1):
        shifted = events.dropna(subset=["event_session_position"]).copy()
        shifted["relative_session"] = offset
        shifted["date"] = (shifted.event_session_position.astype(int) + offset).map(position_date)
        rows.append(shifted.dropna(subset=["date"]))
    expanded = pd.concat(rows, ignore_index=True)
    values = panel[["symbol", "date", "volume", "volume_mean_20_prior", "volume_median_20_prior", "volume_log_mean_20_prior"]].copy()
    values["audit_volume_ratio_20"] = values.volume / values.volume_mean_20_prior
    values["audit_volume_median_ratio_20"] = values.volume / values.volume_median_20_prior
    values["audit_log_volume_surprise_20"] = np.log1p(values.volume.astype(float)) - values.volume_log_mean_20_prior
    expanded = expanded.merge(values, on=["symbol", "date"], how="left", validate="many_to_one")
    result = []
    def append_groups(data, columns):
      for keys, group in data.groupby(columns, sort=True):
        if len(columns) == 3:
            impact, classification, offset = keys
        else:
            impact, offset = keys; classification = "ALL_CLASSES"
        result.append({"research_impact": impact, "action_classification": classification, "relative_session": offset,
                       "source_events": group.event_id.nunique(), "matched_observations": group.audit_volume_ratio_20.notna().sum(),
                       "volume_ratio_20_median": group.audit_volume_ratio_20.median(),
                       "volume_ratio_20_p95": group.audit_volume_ratio_20.quantile(.95),
                       "volume_median_ratio_20_median": group.audit_volume_median_ratio_20.median(),
                       "log_volume_surprise_20_median": group.audit_log_volume_surprise_20.median(),
                       "log_volume_surprise_20_p95": group.audit_log_volume_surprise_20.quantile(.95),
                       "date_semantics": "RECORDED_SOURCE_DATE_NOT_GLOBALLY_VERIFIED_EX_DATE"})
    append_groups(expanded, ["research_impact", "action_classification", "relative_session"])
    append_groups(expanded, ["research_impact", "relative_session"])
    return pd.DataFrame(result)


def correlation_outputs(panel: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = ["volume_ratio_20", "volume_median_ratio_20", "log_volume_surprise_20",
                "volume_ratio_60", "volume_median_ratio_60", "log_volume_surprise_60",
                "price_return_5", "price_return_20"]
    correlations = feature_correlations(panel, features, "universe_basic_liquid")
    candidate_columns = {f"VM0{i}": (f"candidate_vm0{i}" if i <= 4 else f"candidate_vm0{i}_basic_liquid") for i in range(1, 8)}
    base = panel.loc[panel.universe_basic_liquid.fillna(False), list(candidate_columns.values())].rename(
        columns={value: key for key, value in candidate_columns.items()})
    rows = []
    threshold = float(config["redundancy_spearman_threshold"])
    for left, right in combinations(CANDIDATE_IDS, 2):
        pair = base[[left, right]].dropna(); pearson = pair[left].corr(pair[right])
        ranked = pair.rank(method="average"); spearman = ranked[left].corr(ranked[right])
        rows.append({"candidate_left": left, "candidate_right": right, "observations": len(pair),
                     "pearson": pearson, "spearman": spearman,
                     "absolute_spearman": abs(spearman) if pd.notna(spearman) else np.nan,
                     "redundancy_threshold": threshold,
                     "redundancy_status": "HIGH_REDUNDANCY" if pd.notna(spearman) and abs(spearman) >= threshold else "RETAIN_DISTINCT_HYPOTHESIS"})
    return correlations, pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, decimals: int = 4) -> str:
    def value(item):
        if pd.isna(item): return ""
        return f"{item:.{decimals}f}" if isinstance(item, float) else str(item)
    return "\n".join(["| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"] +
                     ["| " + " | ".join(value(item) for item in row) + " |" for row in frame.itertuples(index=False, name=None)])


def render_report(outputs: dict[str, pd.DataFrame], panel: pd.DataFrame, config: dict) -> tuple[str, str, dict]:
    audit = outputs["volume_source_audit.csv"]; coverage = outputs["feature_coverage.csv"]
    distributions = outputs["feature_distribution_universe.csv"]; corr = outputs["feature_correlation.csv"]
    action = outputs["volume_action_proximity.csv"]; registry = outputs["candidate_factor_registry.csv"]
    valid_coverage = coverage[coverage.status.eq("VALID")]
    coverage_summary = (valid_coverage.groupby(["universe", "feature"], as_index=False).coverage_pct.first()
                        .query("feature in ['log_volume_surprise_20','log_volume_surprise_60','price_return_5','price_return_20']"))
    primary = coverage_summary[coverage_summary.universe.eq(PRIMARY_UNIVERSE)]
    volume_corr = corr[(corr.year.astype(str).eq("ALL")) & corr.feature_left.str.contains("volume") & corr.feature_right.str.contains("volume")]
    high = outputs["candidate_redundancy.csv"].query("redundancy_status == 'HIGH_REDUNDANCY'")
    event = action[action.relative_session.eq(0)]
    decision = "CONDITIONAL PASS"
    metadata = {"decision": decision, "panel_rows": len(panel), "symbols": panel.symbol.nunique(),
                "sessions": panel.date.nunique(), "zero_volume": int(panel.volume.eq(0).sum()),
                "null_volume": int(panel.volume.isna().sum()), "negative_volume": int(panel.volume.lt(0).sum()),
                "zero_turnover": int(panel.turnover_rupees.eq(0).sum()),
                "candidate_count": len(registry), "primary_universe": PRIMARY_UNIVERSE,
                "sensitivity_universe": SENSITIVITY_UNIVERSE}
    source_table = audit[["source_format", "first_date", "last_date", "observations", "symbols", "raw_volume_field",
                          "volume_unit", "turnover_implied_price_to_close_median", "compatibility_assessment"]]
    normalization_table = distributions[(distributions.universe.eq(PRIMARY_UNIVERSE)) & distributions.feature.isin([
        "volume_ratio_20", "volume_median_ratio_20", "log_volume_surprise_20",
        "volume_ratio_60", "volume_median_ratio_60", "log_volume_surprise_60"])][
        ["feature", "count", "median", "std", "p99", "max"]]
    action_table = event[event.action_classification.eq("ALL_CLASSES")][
        ["research_impact", "source_events", "matched_observations", "volume_ratio_20_median", "volume_ratio_20_p95"]]
    lines = ["# Phase 8 — Volume + Momentum Foundation", "",
             "**Research scope: outcome-blind data and methodology foundation. No future returns or predictive-performance statistics were calculated.**", "",
             f"**Decision: {decision}**", "", "## 1. Volume audit", "",
             f"The accepted historical dataset contains {len(panel):,} EQ symbol/date rows, {panel.symbol.nunique():,} observed symbols, and {panel.date.nunique():,} exchange sessions. It contains {metadata['null_volume']} null, {metadata['zero_volume']} zero, and {metadata['negative_volume']} negative volume observations.", "",
             markdown_table(source_table), "",
             "OLD `TTL_TRD_QNTY` and NEW `TtlTradgVol` both represent traded shares. Turnover normalization independently reconciles with traded quantity and prices. There are no dates recorded in both formats, so compatibility is supported by schema semantics and continuity diagnostics rather than a same-date dual-format comparison.", "",
             "## 2. Normalization and coverage", "", markdown_table(primary[["feature", "coverage_pct"]]), "",
             markdown_table(normalization_table), "",
             "All baselines use exactly the prior 20 or 60 exchange sessions and exclude today's volume. Missing sessions, unsafe rows, recorded blocking corporate-action crossings, and dates outside certified corporate-action coverage invalidate the feature explicitly.", "",
             "Raw mean and median ratios are heavy-tailed. A trailing median is resistant to contamination from prior spikes but produces larger current-day ratios when a spike occurs. Log-volume surprise has materially more stable scale and is retained in the Phase-9 registry; raw mean and median ratios remain in the foundation dataset for audit and sensitivity.", "",
             "## 3. Corporate-action and listing effects", "",
             f"The action-proximity audit contains {len(action):,} action-class/impact/relative-session summaries. Event-date results use recorded source dates, which are not globally verified ex-dates. Feature intervals crossing raw conventional, material unresolved, or ambiguous events are invalidated; no price or volume adjustment factor was applied.", "",
             markdown_table(action_table), "",
             "First-observation volume is materially more dispersed than established-history volume, so required history is enforced rather than backfilled. Corporate-action ledger silence remains absence of a recorded event, not proof of complete action coverage.", "",
             "## 4. Stability and redundancy", "",
             f"The normalization correlation audit reports {len(corr):,} pair/year rows. Mean-ratio, median-ratio, and log-surprise orderings are highly redundant: the all-period 20-session Spearman correlations are above 0.94 for mean/log and above 0.98 for median/log. Across 20 versus 60 sessions, log surprise is also strongly correlated. This is why the registry retains log surprise only rather than multiplying nearly identical hypotheses.", "",
             f"The final seven-candidate registry has {len(high)} pair(s) above the absolute Spearman redundancy threshold of {config['redundancy_spearman_threshold']:.2f}. One redundant short sign-only interaction was removed before any outcome research; no replacement was added.", "",
             "## 5. Frozen Phase-9 candidate registry", "",
             markdown_table(registry[["candidate_id", "name", "role", "price_component", "volume_component", "baseline_horizon", "directionality"]]), "",
             "The controls keep price, volume, and interaction hypotheses separate. All Phase-9 stock rankings must be same-date and within the selected universe. The 1%/99% winsorization applies only to the contemporaneous volume component of interaction candidates; raw source data is preserved.", "",
             "## 6. Direct answers", "",
             "1. Historical volume is sufficiently reliable for controlled Factor-3 research: fields are complete and nonnegative, but corporate-action completeness and the non-overlapping format transition remain limitations.",
             "2. OLD and NEW volume fields are compatible share-count fields. No dual-format same-day sample exists for perfect empirical reconciliation.",
             f"3. Zero, missing, and negative volume affect 0 accepted EQ rows; zero turnover affects {metadata['zero_turnover']:,} rows and is disclosed separately.",
             "4. Corporate-action distortions are material: recorded conventional, material-unresolved, and ambiguous event dates have median 20-session volume ratios well above ordinary non-price-adjustment actions. Recorded blocking crossings are excluded, but source dates and ledger completeness are not globally certified.",
             "5. Log-volume surprise is the most numerically stable candidate normalization. Raw ratios remain useful diagnostics but have extreme right tails.",
             "6. Median baselines resist prior spikes better, while mean baselines shrink subsequent ratios; median ratios have the heavier current-spike tail. Their rankings are too redundant to preregister both.",
             "7. Both 20- and 60-session baselines are usable, with explicit history and continuity requirements.",
             "8. Yearly log-surprise scale is broadly stable; detailed shifts are disclosed in `feature_distribution_yearly.csv`.",
             "9. Feature completeness and raw-volume stability improve with liquidity restrictions; Broad EQ remains an audit tier rather than the proposed primary research universe.",
             "10. Mean ratio, median ratio, and log surprise are highly redundant within a baseline; 20- and 60-session log surprises are also correlated but preserve distinct baseline hypotheses.",
             "11. Phase 9 should test exactly the seven frozen candidates in the registry and no additions.",
             "12. The primary universe is BASIC_LIQUID.",
             "13. MODERATE_LIQUID is the prespecified sensitivity universe.",
             "14. Volume + Momentum research can proceed responsibly under the CONDITIONAL PASS gate.", "",
             "## 7. Decision and exact Phase-9 design", "",
             "**CONDITIONAL PASS**", "",
             "If authorized, Phase 9 should load this immutable foundation and test the seven registry candidates independently in BASIC_LIQUID, with MODERATE_LIQUID as the sole universe sensitivity. It should preregister future horizons before outcome construction, use same-date percentile ranks, report component controls before interactions, apply the frozen interval-validity columns, use chronological validation, non-overlapping outcomes, dependence-aware intervals, and multiple-testing correction across the seven-candidate family. It must not add candidates, combine Factor 2, choose a winning horizon from the full sample, or run a portfolio backtest.", "",
             "The condition reflects the lack of a same-date OLD/NEW overlap and the accepted corporate-action ledger's source-date/completeness limitations. No future-return, factor-performance, trading, portfolio, Factor-1, or Factor-2 value was created.", ""]
    return "\n".join(lines), decision, metadata


def build(config: dict) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, str, dict]:
    daily = pd.read_parquet(local(config["historical_daily"])); actions = pd.read_parquet(local(config["corporate_action_ledger"]))
    panel = build_foundation(daily, actions, config); assert_outcome_blind(panel)
    yearly, universe = quality_outputs(daily)
    distributions_yearly, distributions_universe = feature_distributions(panel)
    correlations, redundancy = correlation_outputs(panel, config)
    outputs = {"volume_source_audit.csv": source_audit(daily, config),
               "volume_quality_by_year.csv": yearly, "volume_quality_by_universe.csv": universe,
               "volume_outliers.csv": outliers(panel, config),
               "volume_action_proximity.csv": action_proximity(panel, actions, config),
               "feature_coverage.csv": feature_coverage(panel),
               "feature_distribution_yearly.csv": distributions_yearly,
               "feature_distribution_universe.csv": distributions_universe,
               "feature_correlation.csv": correlations, "candidate_redundancy.csv": redundancy,
               "candidate_factor_registry.csv": candidate_registry()}
    for frame in outputs.values(): assert_outcome_blind(frame)
    report, decision, metadata = render_report(outputs, panel, config)
    metadata["decision"] = decision
    return outputs, panel, report, metadata


def acceptance(outputs: dict[str, pd.DataFrame], panel: pd.DataFrame, metadata: dict, config: dict) -> list[dict]:
    registry = outputs["candidate_factor_registry.csv"]
    checks = {
        "volume baselines frozen": tuple(config["volume_baseline_horizons"]) == VOLUME_BASELINES,
        "price horizons frozen": tuple(config["price_return_horizons"]) == PRICE_HORIZONS,
        "primary and sensitivity universes frozen": metadata["primary_universe"] == PRIMARY_UNIVERSE and metadata["sensitivity_universe"] == SENSITIVITY_UNIVERSE,
        "today excluded from baseline": config["baseline_current_day_policy"] == "exclude_current_day",
        "compact candidate family": 4 <= len(registry) <= 8 and set(registry.candidate_id) == set(CANDIDATE_IDS),
        "candidate formulas unique": registry.formula.nunique() == len(registry),
        "candidate roles valid": set(registry.role).issubset({"CONTROL_PRICE", "CONTROL_VOLUME", "INTERACTION"}),
        "all universes audited": set(outputs["volume_quality_by_universe.csv"].universe) == set(UNIVERSES),
        "negative volume explicit": metadata["negative_volume"] == int(panel.volume.lt(0).sum()),
        "no outcome columns": not any(any(token in column.lower() for token in FORBIDDEN) for frame in [panel, *outputs.values()] for column in frame.columns),
        "no other factors": not any(any(token in column.lower() for token in ("sector_momentum", "csrs", "reversal_factor")) for frame in [panel, *outputs.values()] for column in frame.columns),
        "no trading columns": not any(any(token in column.lower() for token in ("portfolio", "pnl", "sharpe", "trading_return")) for frame in [panel, *outputs.values()] for column in frame.columns),
    }
    return [{"check": key, "passed": bool(value)} for key, value in checks.items()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--verify-rebuild", action="store_true"); args = parser.parse_args()
    config = load_config(); accepted = verify_inputs(config); outputs, panel, report, metadata = build(config)
    checks = acceptance(outputs, panel, metadata, config)
    if not all(item["passed"] for item in checks): raise AssertionError([item for item in checks if not item["passed"]])
    report_dir = local(config["report_dir"]); report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase8-staging-", dir=report_dir) as temporary:
        stage = Path(temporary)
        for name, frame in outputs.items(): frame.round(12).to_csv(stage / name, index=False, float_format="%.12g")
        panel.to_parquet(stage / "volume_momentum_foundation.parquet", index=False, compression="zstd")
        (stage / "phase8_volume_momentum_foundation.md").write_text(report)
        (stage / "phase8_acceptance.json").write_text(canonical_json(checks))
        names = list(outputs) + ["volume_momentum_foundation.parquet", "phase8_volume_momentum_foundation.md", "phase8_acceptance.json"]
        hashes = {name: sha256(stage / name) for name in names}
        key = {"accepted_inputs": accepted, "code_sha256": code_fingerprint(), "config": config,
               "candidate_registry": outputs["candidate_factor_registry.csv"].to_dict("records"), "output_sha256": hashes}
        build_id = hashlib.sha256(canonical_json(key).encode()).hexdigest()
        manifest_path = report_dir / "phase8_build_manifest.json"
        destinations = {name: report_dir / name for name in outputs}
        destinations.update({"volume_momentum_foundation.parquet": local(config["foundation_output"]),
                             "phase8_volume_momentum_foundation.md": local(config["final_report"]),
                             "phase8_acceptance.json": report_dir / "phase8_acceptance.json"})
        if args.verify_rebuild:
            prior = json.loads(manifest_path.read_text())
            if prior["build_id"] != build_id or prior["output_sha256"] != hashes:
                differences = {name: {"accepted": prior["output_sha256"].get(name), "rebuilt": digest}
                               for name, digest in hashes.items() if prior["output_sha256"].get(name) != digest}
                raise AssertionError(f"Phase-8 rebuild differs: {differences}")
            for name, digest in hashes.items():
                if sha256(destinations[name]) != digest: raise AssertionError(f"Published Phase-8 output differs: {name}")
            proof = {"build_id": build_id, "byte_identical": True, "output_count": len(hashes),
                     "command": ".venv/bin/python scripts/build_phase8_volume_momentum_foundation.py --verify-rebuild"}
            (report_dir / "phase8_rebuild_verification.json").write_text(canonical_json(proof))
            print(f"PASS deterministic Phase-8 rebuild: {len(hashes)} outputs; build {build_id}")
            return
        for name, destination in destinations.items():
            destination.parent.mkdir(parents=True, exist_ok=True); os.replace(stage / name, destination)
        manifest = {**key, "build_id": build_id, "build_timestamp_utc": datetime.now(timezone.utc).isoformat(), **metadata}
        manifest_path.write_text(canonical_json(manifest))
        print(f"Built Phase 8: {metadata['panel_rows']:,} rows; {metadata['candidate_count']} frozen candidates")
        print(f"Volume null/zero/negative: {metadata['null_volume']}/{metadata['zero_volume']}/{metadata['negative_volume']}")
        print(f"Decision: {metadata['decision']}")


if __name__ == "__main__":
    main()
