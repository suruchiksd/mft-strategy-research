import importlib.util,json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sector_strategy/v1_diagnostics"

def builder():
    p=ROOT/"scripts/build_phase12a_v1_diagnostics.py";s=importlib.util.spec_from_file_location("p12a",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def test_phase11_build_and_preregistration_are_unchanged():
    m=builder();accepted=m.verify_inputs(m.cfg())
    assert accepted["phase11_build_id"]=="17ee67218388859ee7211e7a4deea60227f2c5cd4ef6a72e8d62583bee6ae2b3"
    assert accepted["phase11_preregistration_hash"]=="197fb9d9a6185076a70cbb7f92affe2d8dd4688c2e2c3d7791e3438bf7b2cada"
    assert accepted["phase10_amendment_hash"]=="9752e169486101be217a9c9f96aa9cf22adfcbc563c2c544415db60e4f2e3b42"

def test_no_alternative_targets_or_v2_pnl_are_generated():
    manifest=json.loads((OUT/"phase12a_build_manifest.json").read_text())
    code=(ROOT/"scripts/build_phase12a_v1_diagnostics.py").read_text()+(ROOT/"src/mft_research/v1_diagnostics.py").read_text()
    assert manifest["alternative_strategy_pnl_count"]==0 and "generate_rebalances(" not in code and "simulate(" not in code
    assert not any("v2" in n.lower() and "pnl" in n.lower() for n in manifest["output_sha256"])

def test_no_strategy_performance_after_cutoff_is_read():
    manifest=json.loads((OUT/"phase12a_build_manifest.json").read_text())
    assert manifest["performance_data_max_date"]=="2026-09-17"
    for p in [ROOT/"reports/sector_strategy/development/development_equity_curve.csv",ROOT/"reports/sector_strategy/holdout/holdout_equity_curve.csv"]:
        assert pd.to_datetime(pd.read_csv(p).date).max()<=pd.Timestamp("2026-09-17")

def test_turnover_components_reconcile_to_every_accepted_trade():
    x=pd.read_csv(OUT/"turnover_decomposition.csv");assert set(x.turnover_class)=={"SECTOR_ENTRY_EXIT","WITHIN_SECTOR_STOCK_REPLACEMENT","WEIGHT_REBALANCING","FORCED_OPERATIONAL"}
    for period in ("development","holdout"):
        trades=pd.read_csv(ROOT/f"reports/sector_strategy/{period}/{period}_trades.csv")
        got=x[x.period.eq(period.upper())].rupee_turnover.sum()
        assert np.isclose(got,trades.notional.sum(),rtol=0,atol=1e-5)

def test_normalized_turnover_reconciles_to_accepted_rebalances():
    x=pd.read_csv(OUT/"turnover_decomposition.csv")
    for period in ("development","holdout"):
        reb=pd.read_csv(ROOT/f"reports/sector_strategy/{period}/{period}_rebalances.csv")
        assert np.isclose(x[x.period.eq(period.upper())].normalized_turnover.sum(),reb.gross_turnover.sum(),atol=1e-9)

def test_cost_components_reconcile_to_accepted_trade_costs_and_slippage():
    c=pd.read_csv(OUT/"cost_attribution.csv")
    for period in ("development","holdout"):
        t=pd.read_csv(ROOT/f"reports/sector_strategy/{period}/{period}_trades.csv")
        x=c[c.period.eq(period.upper())]
        assert np.isclose(x.transaction_cost.sum(),t.transaction_cost.sum(),atol=1e-6)
        assert np.isclose(x.slippage_cost.sum(),(abs(t.fill_price-t.reference_open)*t.quantity).sum(),atol=1e-6)

def test_contribution_attribution_reconciles_to_accepted_equity_change():
    stock=pd.read_csv(OUT/"gross_stock_contribution.csv");curve=pd.read_csv(ROOT/"reports/sector_strategy/development/development_equity_curve.csv")
    assert np.isclose(stock.net_contribution.sum(),curve.equity.iloc[-1]-500000,atol=1e-5)
    assert np.isclose(stock.gross_contribution.sum(),stock.net_contribution.sum()+stock.execution_cost.sum(),atol=1e-6)

def test_operational_audit_maps_all_records_without_fabricated_exits():
    audit=pd.read_csv(OUT/"operational_exception_audit.csv");raw=pd.read_csv(ROOT/"reports/sector_strategy/development/development_operational_anomalies.csv")
    assert audit[["stale_marks","unavailable_exit_attempts","position_cap_prevented_entries"]].sum().sum()==len(raw)==534
    assert not audit.fabricated_exit.any()
    affected=audit[audit.stale_marks.gt(0)];assert len(affected)==6 and set(affected.root_cause)=={"SERIES_CHANGE_EQ_TO_BE"}

def test_drawdowns_and_rank_boundary_are_descriptive_only():
    dd=pd.read_csv(OUT/"drawdown_episodes.csv");sector=pd.read_csv(OUT/"sector_rank_boundary_churn.csv");stock=pd.read_csv(OUT/"stock_rank_boundary_churn.csv")
    assert len(dd)==10 and np.isclose(dd.depth.min(),-0.462201102577,atol=1e-10)
    assert {"previous_strength_rank","current_strength_rank","small_boundary_move"}.issubset(sector.columns)
    assert {"previous_liquidity_rank","current_liquidity_rank","small_boundary_move"}.issubset(stock.columns)

def test_phase12a_output_hashes_are_valid():
    m=builder();manifest=json.loads((OUT/"phase12a_build_manifest.json").read_text())
    for name,digest in manifest["output_sha256"].items():
        path=ROOT/"reports/phase12a_sector_strategy_v1_diagnostics.md" if name=="phase12a_sector_strategy_v1_diagnostics.md" else OUT/name
        assert m.sha256(path)==digest
