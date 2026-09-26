import importlib.util,json
from pathlib import Path

import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1]

def builder():
    p=ROOT/"scripts/build_phase11_strategy.py";s=importlib.util.spec_from_file_location("p11",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def test_frozen_preregistration_and_only_sector_alpha():
    m=builder();c,manifest=m.verify_gate()
    assert manifest["strategy_preregistration_hash"]=="197fb9d9a6185076a70cbb7f92affe2d8dd4688c2e2c3d7791e3438bf7b2cada"
    assert c["alpha"]["sole_factor"]=="SECTOR_RELATIVE_MOMENTUM" and c["alpha"]["formation_sessions"]==20
    text=(ROOT/"reports/sector_strategy/preregistration/phase11_sector_strategy_config.yaml").read_text().lower()
    assert "rev05" not in text and "rev20" not in text and "volume_momentum" not in text

def test_signal_panel_exactly_matches_accepted_phase7_definition():
    accepted=pd.read_parquet(ROOT/"data/derived/sector_momentum_factor_panel.parquet")
    extended=pd.read_parquet(ROOT/"data/derived/phase11_sector_signal_panel.parquet")
    cols=["date","sector_code","sector_ret_20","valid_sector_ret_20"]
    x=accepted[accepted.date<=pd.Timestamp("2026-07-17").date()][cols].merge(extended[cols],on=["date","sector_code"],suffixes=("_a","_b"),validate="one_to_one")
    expected=accepted[accepted.date<=pd.Timestamp("2026-07-17").date()]
    assert len(x)==len(expected) and (x.valid_sector_ret_20_a==x.valid_sector_ret_20_b).all()
    assert (x.sector_ret_20_a.fillna(0)-x.sector_ret_20_b.fillna(0)).abs().max()==0

def test_weekly_rule_and_next_session_execution_are_deterministic():
    from mft_research.sector_strategy import weekly_signal_dates
    calendar=pd.to_datetime(["2026-08-03","2026-08-04","2026-08-07","2026-08-10","2026-08-14"]).date
    x=weekly_signal_dates(calendar,"2026-08-14")
    assert x.signal_date.tolist()==list(pd.to_datetime(["2026-08-07","2026-08-14"]).date)
    assert x.execution_date.iloc[0]==pd.Timestamp("2026-08-10").date() and pd.isna(x.execution_date.iloc[1])

def test_targets_are_top_three_sectors_liquidity_only_and_at_most_nine():
    targets=pd.read_csv(ROOT/"reports/sector_strategy/holdout/holdout_signal_targets.csv",parse_dates=["signal_date","execution_date"])
    assert targets.groupby("signal_date").size().le(9).all()
    assert targets.groupby(["signal_date","sector_code"]).size().le(3).all()
    assert targets.groupby("signal_date").sector_code.nunique().le(3).all()
    for _,g in targets.groupby(["signal_date","sector_code"]):
        assert g.sort_values("liquidity_rank").avg_turnover_20.is_monotonic_decreasing
    assert not any(c.lower().startswith(("rev","vm")) or "stock_momentum" in c.lower() for c in targets.columns)

def test_simulator_uses_next_open_integer_cash_only_and_adverse_costs():
    from mft_research.sector_strategy import simulate
    dates=list(pd.to_datetime(["2026-08-03","2026-08-04"]).date)
    daily=pd.DataFrame({"date":dates,"symbol":["A","A"],"open":[100.,110.],"close":[105.,111.]})
    target=pd.DataFrame({"execution_date":[dates[0]],"signal_date":[pd.Timestamp("2026-07-31").date()],"rebalance_id":["X"],"symbol":["A"],"sector":["S"]})
    gross=simulate(daily,target,dates[0],dates[-1],1000,0,0);net=simulate(daily,target,dates[0],dates[-1],1000,20,5)
    assert gross["trades"].iloc[0].reference_open==100 and gross["trades"].iloc[0].quantity==10
    assert net["trades"].iloc[0].fill_price>100 and net["equity"].equity.iloc[-1]<gross["equity"].equity.iloc[-1]
    assert net["equity"].cash.min()>=0 and (net["trades"].quantity%1==0).all()

def test_published_rms_periods_and_single_holdout_evaluation():
    a=json.loads((ROOT/"reports/sector_strategy/phase11_strategy_acceptance.json").read_text())
    dev=pd.read_csv(ROOT/"reports/sector_strategy/development/development_equity_curve.csv",parse_dates=["date"])
    hold=pd.read_csv(ROOT/"reports/sector_strategy/holdout/holdout_equity_curve.csv",parse_dates=["date"])
    pos=pd.read_csv(ROOT/"reports/sector_strategy/holdout/holdout_positions.csv")
    assert dev.date.max()<=pd.Timestamp("2026-07-17") and hold.date.min()>=pd.Timestamp("2026-08-01")
    assert a["holdout_inspection_count"]==1 and pos.groupby("date").symbol.nunique().max()<=9
    assert pd.read_csv(ROOT/"reports/sector_strategy/holdout/holdout_operational_anomalies.csv").empty

def test_benchmark_has_no_date_lookahead_and_holdout_signals_execute_after_close():
    metrics=pd.read_csv(ROOT/"reports/sector_strategy/holdout/holdout_metrics.csv")
    reb=pd.read_csv(ROOT/"reports/sector_strategy/holdout/holdout_rebalances.csv",parse_dates=["signal_date","execution_date"])
    assert metrics.benchmark.iloc[0]=="NIFTYBEES" and (reb.execution_date>reb.signal_date).all()
    assert reb.execution_date.max()<=pd.Timestamp("2026-09-17")

def test_no_combined_factor_or_trading_rule_columns():
    forbidden=("rev05","rev20","volume_surprise","stop_loss","profit_target","combined_score")
    for p in (ROOT/"reports/sector_strategy").rglob("*.csv"):
        columns=[c.lower() for c in pd.read_csv(p,nrows=0).columns]
        assert not any(any(token in c for token in forbidden) for c in columns)

def test_phase11_manifest_hashes_and_prior_integrity():
    m=builder();prior=m.verify_prior();manifest=json.loads((ROOT/"reports/sector_strategy/phase11_strategy_build_manifest.json").read_text())
    assert prior["phase5_verified_outputs"]==24 and prior["phase9_verified_outputs"]==22
    assert prior["original_preregistration_sha256"]=="fb0976eeea5dc524f4bb9a22dad98b6b0ec6fc42507dcc90f9d5f16d52da6995"
    assert manifest["factor"]=="SECTOR_RELATIVE_MOMENTUM_ONLY"
    for name,digest in manifest["output_sha256"].items():
        p=ROOT/"reports/phase11_sector_momentum_strategy.md" if name=="phase11_sector_momentum_strategy.md" else ROOT/"reports/sector_strategy"/name
        assert m.sha256(p)==digest
