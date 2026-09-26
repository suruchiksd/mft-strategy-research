#!/usr/bin/env python3
"""Run the single frozen Strategy V2 development simulation."""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, os, sys, tempfile
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mft_research.ca_extension import parse_official
from mft_research.csrs.phase5 import canonicalize_source, read_source, source_format
from mft_research.data.manifest import canonical_json, sha256
from mft_research.sector_strategy import action_contract
from mft_research.sector_strategy_v2_backtest import metrics, simulate_v2

PREREG = ROOT / "reports/sector_strategy/v2/preregistration"
OUT = ROOT / "reports/sector_strategy/v2"
DEV = OUT / "development"
EXPECTED_PREREG = "2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f"
EXPECTED_P12A = "9a3b56f77d15b7f32c86e848fb5e399284680e0790a97ce542e92f20be4b5bc5"


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify_gate():
    p12b = json.loads((PREREG / "phase12b_sector_strategy_v2_manifest.json").read_text())
    if p12b["preregistration_hash"] != EXPECTED_PREREG:
        raise RuntimeError("Phase-12B preregistration hash mismatch")
    if p12b["v2_pnl_inspected"] or p12b["post_2026_09_17_v2_performance_inspected"]:
        raise RuntimeError("Phase-12B pre-P&L flags changed")
    for n, h in p12b["frozen_artifact_sha256"].items():
        if digest(PREREG / n) != h:
            raise RuntimeError(f"Phase-12B frozen artifact changed: {n}")
    p12a = json.loads((ROOT / "reports/sector_strategy/v1_diagnostics/phase12a_build_manifest.json").read_text())
    if p12a["build_id"] != EXPECTED_P12A:
        raise RuntimeError("Phase-12A authoritative build mismatch")
    for n, h in p12a["output_sha256"].items():
        p = ROOT / "reports/phase12a_sector_strategy_v1_diagnostics.md" if n.startswith("phase12a_") else ROOT / "reports/sector_strategy/v1_diagnostics" / n
        if digest(p) != h:
            raise RuntimeError(f"Phase-12A artifact changed: {n}")
    p11 = json.loads((ROOT / "reports/sector_strategy/phase11_strategy_build_manifest.json").read_text())
    if p11["build_id"] != "17ee67218388859ee7211e7a4deea60227f2c5cd4ef6a72e8d62583bee6ae2b3":
        raise RuntimeError("Phase-11 build changed")
    # All accepted manifest outputs are checked before any performance input is loaded.
    for mp in sorted((ROOT / "reports").rglob("*manifest*.json")):
        if "confirmation_unaccepted" in mp.as_posix() or "v2/preregistration" in mp.as_posix():
            continue
        try: m = json.loads(mp.read_text())
        except Exception: continue
        for n, h in m.get("output_sha256", {}).items():
            hits = [p for p in ROOT.rglob(Path(n).name) if digest(p) == h]
            if not hits:
                raise RuntimeError(f"Accepted artifact missing or changed: {mp} {n}")
    rules = json.loads((PREREG / "phase12b_v2_acceptance_rules.json").read_text())
    return p12b, rules


class RawQuotes:
    def __init__(self, daily):
        self.paths = daily.drop_duplicates("date").set_index("date").source_file.to_dict()
        self.cache = {}

    def __call__(self, date):
        date = pd.Timestamp(date).date()
        if date not in self.cache:
            raw, _ = read_source(Path(self.paths[date]))
            x = canonicalize_source(raw, source_format(Path(self.paths[date])), str(self.paths[date]))
            self.cache[date] = x[["symbol", "series", "open", "close", "volume"]]
        return self.cache[date]


def load_inputs():
    base = pd.read_parquet(ROOT / "data/derived/historical_nse_daily.parquet")
    ext = pd.read_parquet(ROOT / "data/derived/phase11_historical_daily_extension.parquet")
    daily = pd.concat([base, ext], ignore_index=True).sort_values(["date", "symbol"], kind="stable").reset_index(drop=True)
    daily["date"] = pd.to_datetime(daily.date).dt.date
    daily = daily[daily.date <= pd.Timestamp("2026-09-17").date()].copy()
    factor = pd.read_parquet(ROOT / "data/derived/phase11_sector_signal_panel.parquet")
    factor["date"] = pd.to_datetime(factor.date).dt.date
    factor = factor[factor.date <= pd.Timestamp("2026-09-17").date()].copy()
    mapping = pd.read_parquet(ROOT / "data/derived/sector_research_mapping.parquet")
    hist = pd.read_parquet(ROOT / "data/derived/corporate_action_ledger.parquet")
    extensions = []
    for name in ("phase10_corporate_action_extension.parquet", "phase11_corporate_action_extension.parquet"):
        extensions.append(pd.read_parquet(ROOT / "data/derived" / name))
    actions = action_contract(hist, extensions)
    return daily, factor, mapping, actions


def period_returns(curve, period, initial):
    if curve.empty: return pd.DataFrame(columns=[period, "return"])
    x = curve.copy(); x[period] = pd.to_datetime(x.date).dt.to_period("M" if period == "month" else "Y").astype(str)
    rows = []; prior = initial
    for key, g in x.groupby(period, sort=True):
        end = float(g.equity.iloc[-1]); rows.append({period: key, "return": end / prior - 1}); prior = end
    return pd.DataFrame(rows)


def contribution_tables(result):
    c = result["contribution"].copy()
    if c.empty:
        return (pd.DataFrame(columns=["symbol", "contribution_rupees", "absolute_contribution_share"]), pd.DataFrame(columns=["sector", "contribution_rupees", "absolute_contribution_share"]))
    out = []
    for key in ("symbol", "sector"):
        x = c.groupby(key, as_index=False).contribution_rupees.sum().sort_values("contribution_rupees", ascending=False, kind="stable")
        den = x.contribution_rupees.abs().sum(); x["absolute_contribution_share"] = x.contribution_rupees.abs() / den if den else np.nan; out.append(x)
    return out[0], out[1]


def stability(selection):
    if selection.empty: return pd.DataFrame()
    rows = []; prev_s = set(); prev_st = set(); sector_runs = {}; stock_runs = {}
    for r in selection.itertuples(index=False):
        s = set(r.selected_sectors.split("|")) if r.selected_sectors else set(); st = set(r.selected_stocks.split("|")) if r.selected_stocks else set()
        for x in s: sector_runs[x] = sector_runs.get(x, 0) + 1
        for x in st: stock_runs[x] = stock_runs.get(x, 0) + 1
        rows.append({"rebalance_id": r.rebalance_id, "signal_date": r.signal_date, "execution_date": r.execution_date,
                     "selected_sectors": r.selected_sectors, "sectors_retained": len(s & prev_s), "sectors_entered": len(s - prev_s), "sectors_exited": len(prev_s - s),
                     "sector_jaccard": len(s & prev_s) / len(s | prev_s) if s | prev_s else np.nan, "mean_active_sector_duration_cycles": np.mean([sector_runs[x] for x in s]) if s else np.nan,
                     "selected_stocks": r.selected_stocks, "stocks_retained": len(st & prev_st), "stocks_entered": len(st - prev_st), "stocks_exited": len(prev_st - st),
                     "stock_jaccard": len(st & prev_st) / len(st | prev_st) if st | prev_st else np.nan, "mean_active_stock_duration_cycles": np.mean([stock_runs[x] for x in st]) if st else np.nan})
        prev_s, prev_st = s, st
    return pd.DataFrame(rows)


def drawdowns(curve):
    if curve.empty: return pd.DataFrame()
    x = curve.sort_values("date").reset_index(drop=True); peak = x.equity.cummax(); dd = x.equity / peak - 1; rows = []
    in_dd = False; peak_i = 0; trough_i = 0; start_i = 0
    for i, v in enumerate(dd):
        if v == 0:
            if in_dd: rows.append((peak_i, start_i, trough_i, i)); in_dd = False
            peak_i = i
        elif not in_dd:
            in_dd = True; start_i = i; trough_i = i
        elif x.equity.iloc[i] < x.equity.iloc[trough_i]: trough_i = i
    if in_dd: rows.append((peak_i, start_i, trough_i, None))
    rec = []
    for j, (pi, si, ti, ri) in enumerate(rows, 1):
        rec.append({"episode_id": j, "peak_date": x.date.iloc[pi], "underwater_start": x.date.iloc[si], "trough_date": x.date.iloc[ti], "recovery_date": x.date.iloc[ri] if ri is not None else pd.NaT, "depth": x.equity.iloc[ti] / x.equity.iloc[pi] - 1, "peak_to_trough_sessions": ti - pi, "recovered": ri is not None})
    return pd.DataFrame(rec).sort_values("depth").reset_index(drop=True)


def benchmark(daily, curve):
    if curve.empty: return np.nan
    x = daily[daily.symbol.eq("NIFTYBEES") & daily.date.between(curve.date.min(), curve.date.max())].sort_values("date")
    return float(x.close.iloc[-1] / x.open.iloc[0] - 1) if len(x) and x.date.iloc[0] == curve.date.min() and x.date.iloc[-1] == curve.date.max() else np.nan


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--verify-rebuild", action="store_true"); args = ap.parse_args()
    p12b, rules = verify_gate()  # must precede all performance reads
    daily, factor, mapping, actions = load_inputs()
    if daily.date.max() > pd.Timestamp("2026-09-17").date(): raise RuntimeError("post-boundary data read")
    raw = RawQuotes(daily); capital = 500000.0
    components = {0: (0, 0), 10: (8, 2), 25: (20, 5), 50: (40, 10)}
    runs = {}
    for bps, (tc, sl) in components.items():
        runs[bps] = simulate_v2(daily, factor, mapping, actions, "2020-01-01", "2026-09-17", capital, tc, sl, raw_provider=raw)
    primary = runs[25]; gross = runs[0]; pm = metrics(primary, capital); gm = metrics(gross, capital)
    stock, sector = contribution_tables(primary)
    sens = pd.DataFrame([{"total_bps_per_side": b, **metrics(r, capital)} for b, r in runs.items()])
    turnover = primary["trades"].groupby("trade_class", as_index=False).agg(rupee_turnover=("notional", "sum"), trade_count=("symbol", "size"), transaction_cost=("transaction_cost", "sum"))
    for cls in ["SECTOR_ENTRY_EXIT", "WITHIN_SECTOR_STOCK_REPLACEMENT", "WEIGHT_REBALANCING", "FORCED_OPERATIONAL"]:
        if cls not in set(turnover.trade_class):
            turnover = pd.concat([turnover, pd.DataFrame([{ "trade_class": cls, "rupee_turnover": 0.0, "trade_count": 0, "transaction_cost": 0.0 }])], ignore_index=True)
    turnover = turnover.sort_values("trade_class", kind="stable").reset_index(drop=True)
    total_turn = turnover.rupee_turnover.sum(); turnover["percentage_of_total_turnover"] = turnover.rupee_turnover / total_turn if total_turn else np.nan
    turnover["normalized_turnover"] = turnover.rupee_turnover / capital
    sel = stability(primary["selection"]); dd = drawdowns(primary["equity"])
    gross_gain = gm["cumulative_return"]; retention = (pm["cumulative_return"] / gross_gain) if gross_gain > 0 else np.nan
    max_stock = float(stock.absolute_contribution_share.max()) if len(stock) else 1.; max_sector = float(sector.absolute_contribution_share.max()) if len(sector) else 1.
    gates = {
        "operational_invariants": {"value": len(primary["anomalies"]) == 0 and (primary["equity"].cash >= -1e-7).all(), "threshold": True, "pass": len(primary["anomalies"]) == 0 and (primary["equity"].cash >= -1e-7).all()},
        "mean_weekly_gross_turnover": {"value": pm["mean_weekly_gross_turnover"], "threshold": 0.65, "pass": bool(pm["mean_weekly_gross_turnover"] <= 0.65)},
        "primary_25bps_cumulative_return": {"value": pm["cumulative_return"], "threshold": ">0", "pass": bool(pm["cumulative_return"] > 0)},
        "primary_25bps_CAGR": {"value": pm["CAGR"], "threshold": ">0", "pass": bool(pm["CAGR"] > 0)},
        "primary_25bps_Sharpe": {"value": pm["Sharpe"], "threshold": ">0", "pass": bool(pm["Sharpe"] > 0)},
        "cost_retention_ratio": {"value": retention, "threshold": 0.40, "pass": bool(gross_gain <= 0 or retention >= 0.40)},
        "maximum_drawdown": {"value": pm["maximum_drawdown"], "threshold": ">-0.40", "pass": bool(pm["maximum_drawdown"] > -0.40)},
        "single_stock_contribution_share": {"value": max_stock, "threshold": 0.50, "pass": bool(max_stock <= 0.50)},
        "single_sector_contribution_share": {"value": max_sector, "threshold": 0.60, "pass": bool(max_sector <= 0.60)},
    }
    hard = gates["operational_invariants"]["pass"] and gates["maximum_drawdown"]["pass"] and gates["primary_25bps_cumulative_return"]["pass"]
    shared = all(v["pass"] for v in gates.values())
    if not hard: decision = "REJECT STRATEGY V2"
    elif not shared: decision = "RESEARCH FURTHER"
    elif pm["maximum_drawdown"] < -0.35: decision = "CONDITIONAL PROSPECTIVE CANDIDATE"
    else: decision = "READY FOR PROSPECTIVE VALIDATION"
    metrics_frame = pd.DataFrame([{**pm, "gross_cumulative_return": gm["cumulative_return"], "cost_retention_ratio": retention, "maximum_stock_absolute_contribution_share": max_stock, "maximum_sector_absolute_contribution_share": max_sector, "decision": decision}])
    comparison = pd.DataFrame([{ "metric": k, "V1": v1, "V2": metrics_frame.iloc[0].get(k, np.nan), "absolute_change": metrics_frame.iloc[0].get(k, np.nan) - v1 if pd.notna(metrics_frame.iloc[0].get(k, np.nan)) else np.nan } for k, v1 in [("cumulative_return", 0.6810), ("CAGR", 0.0888), ("Sharpe", 0.484), ("maximum_drawdown", -0.4622), ("mean_weekly_gross_turnover", 0.942), ("operational_anomalies", 534)]])
    operational = primary["anomalies"].copy()
    if operational.empty and len(operational.columns) == 0:
        operational = pd.DataFrame(columns=["date", "type", "symbol", "detail", "strategy_version"])
    operational["strategy_version"] = "V2"
    outputs = {
        "development/v2_equity_curve.csv": primary["equity"], "development/v2_rebalances.csv": primary["rebalances"], "development/v2_trades.csv": primary["trades"], "development/v2_positions.csv": primary["positions"], "development/v2_metrics.csv": metrics_frame, "development/v2_monthly_returns.csv": period_returns(primary["equity"], "month", capital), "development/v2_yearly_returns.csv": period_returns(primary["equity"], "year", capital), "development/v2_cost_sensitivity.csv": sens, "development/v2_turnover_attribution.csv": turnover, "development/v2_sector_contribution.csv": sector, "development/v2_stock_contribution.csv": stock, "development/v2_operational_events.csv": operational, "development/v2_selection_stability.csv": sel, "development/v2_drawdown_episodes.csv": dd, "development/v2_v1_comparison.csv": comparison,
    }
    def jsonable(value):
        if isinstance(value, dict): return {str(k): jsonable(v) for k, v in value.items()}
        if isinstance(value, list): return [jsonable(v) for v in value]
        if isinstance(value, (np.bool_,)): return bool(value)
        if isinstance(value, (np.integer,)): return int(value)
        if isinstance(value, (np.floating,)): return None if not np.isfinite(value) else float(value)
        if isinstance(value, (datetime, date, pd.Timestamp)): return str(value)
        return value
    cost_records = sens.astype(object).where(pd.notna(sens), None).to_dict("records")
    for rec in cost_records:
        for key, value in list(rec.items()):
            if isinstance(value, (datetime, date, pd.Timestamp)):
                rec[key] = str(value)
    acceptance = jsonable({"strategy_version": "V2", "preregistration_hash": EXPECTED_PREREG, "development_data_end": "2026-09-17", "post_boundary_performance_inspected": False, "decision": decision, "gates": gates, "cost_scenarios": cost_records, "state": {"pnl_inspected_after_gate": True, "post_2026_09_17_performance_inspected": False}})
    op_type = operational["type"] if "type" in operational.columns else pd.Series(dtype=object)
    report = f"""# Phase 12C — Sector Momentum Strategy V2 Development Backtest

**Decision: {decision}**

This is a V2 DEVELOPMENT / HISTORICAL STRATEGY SIMULATION through 2026-09-17, not fresh out-of-sample validation. The frozen Phase12B specification and acceptance JSON were loaded without modification.

## Results

The first executable date was {pm.get('start_date')}. Primary 25-bps cumulative return was {pm['cumulative_return']:.2%}; gross cumulative return was {gm['cumulative_return']:.2%}; CAGR {pm['CAGR']:.2%}; Sharpe {pm['Sharpe']:.3f}; maximum drawdown {pm['maximum_drawdown']:.2%}; mean weekly turnover {pm['mean_weekly_gross_turnover']:.3f}; cost-retention ratio {retention:.3f}.

Cost sensitivity cumulative returns: {', '.join(f"{int(r.total_bps_per_side)} bps={r.cumulative_return:.2%}" for r in sens.itertuples())}.

V2 turnover attribution was {turnover.set_index('trade_class')['percentage_of_total_turnover'].to_dict()}. V1 reference shares were sector entry/exit 87.293%, stock replacement 10.235%, weight restoration 2.222%, and operational 0.250%.

The simulation recorded {len(operational)} operational events, {int(op_type.eq('UNEXECUTABLE_EXIT_NO_VALID_OPEN').sum())} unavailable exit attempts, {int(op_type.eq('STALE_MARK_CARRIED_NO_VALID_CLOSE').sum())} stale marks, and no fabricated prices. Maximum simultaneous trapped capital and duration are reported in the machine-readable event/position files. Maximum stock and sector absolute contribution shares were {max_stock:.2%} and {max_sector:.2%}.

The acceptance gates were frozen before this run and are recorded individually in `phase12c_v2_acceptance.json`. V2 is not paper-traded and no post-2026-09-17 performance is included.
"""
    with tempfile.TemporaryDirectory(prefix=".phase12c-", dir=OUT) as tmp:
        stage = Path(tmp)
        for name, frame in outputs.items():
            p = stage / name; p.parent.mkdir(parents=True, exist_ok=True); frame.to_csv(p, index=False, date_format="%Y-%m-%d", float_format="%.12f")
        (stage / "phase12c_v2_acceptance.json").write_text(canonical_json(acceptance)); (stage / "phase12c_sector_momentum_strategy_v2.md").write_text(report)
        names = sorted(str(p.relative_to(stage)) for p in stage.rglob("*") if p.is_file()); hashes = {n: sha256(stage / n) for n in names}
        key = {"accepted_inputs": {"phase12a_build_id": EXPECTED_P12A, "phase12b_preregistration_hash": EXPECTED_PREREG}, "output_sha256": hashes, "decision": decision, "performance_data_end": "2026-09-17", "post_boundary_performance_inspected": False}
        build = hashlib.sha256(canonical_json(key).encode()).hexdigest(); manifest = {**key, "build_id": build, "strategy_version": "V2", "development_start": str(pm["start_date"]), "development_end": "2026-09-17"}; (stage / "phase12c_v2_build_manifest.json").write_text(canonical_json(manifest)); names.append("phase12c_v2_build_manifest.json")
        if args.verify_rebuild:
            old = json.loads((OUT / "phase12c_v2_build_manifest.json").read_text()); diffs = {n: (old["output_sha256"].get(n), sha256(stage / n)) for n in names if n != "phase12c_v2_build_manifest.json" and old["output_sha256"].get(n) != sha256(stage / n)}
            if old["build_id"] != build or diffs: raise AssertionError(f"Phase12C rebuild differs: {diffs}")
            print(f"PASS Phase-12C deterministic rebuild {len(names)}/{len(names)} byte-identical {build}"); return
        (OUT / "development").mkdir(parents=True, exist_ok=True)
        for n in names: os.replace(stage / n, OUT / n)
    print(f"Built Phase-12C V2 {build} — {decision}")


if __name__ == "__main__": main()
