import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "reports/sector_strategy/v2"
DEV = V2 / "development"
PREREG_HASH = "2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f"
P12A = "9a3b56f77d15b7f32c86e848fb5e399284680e0790a97ce542e92f20be4b5bc5"


def acceptance():
    return json.loads((V2 / "phase12c_v2_acceptance.json").read_text())


def test_exact_preregistration_and_inputs():
    a = acceptance(); m = json.loads((V2 / "phase12c_v2_build_manifest.json").read_text())
    assert a["preregistration_hash"] == PREREG_HASH
    assert m["accepted_inputs"]["phase12a_build_id"] == P12A


def test_frozen_boundaries_and_no_post_boundary_rows():
    a = acceptance(); assert a["development_data_end"] == "2026-09-17"
    assert a["post_boundary_performance_inspected"] is False
    eq = pd.read_csv(DEV / "v2_equity_curve.csv"); assert eq.date.max() <= "2026-09-17"


def test_buffers_and_weight_band_are_frozen():
    c = (V2 / "preregistration/phase12b_sector_strategy_v2_config.yaml").read_text()
    assert "sector_new_entry_rank_max: 3" in c and "sector_retention_rank_max: 5" in c
    assert "weight_restoration_absolute_band: 0.02" in c


def test_position_cap_and_whole_shares():
    p = pd.read_csv(DEV / "v2_positions.csv"); assert p.positions.max() if "positions" in p else True
    assert (p.shares % 1 == 0).all(); assert p.groupby("date").symbol.nunique().max() <= 9


def test_no_negative_cash_or_leverage():
    e = pd.read_csv(DEV / "v2_equity_curve.csv"); assert e.cash.min() >= -1e-7
    assert (e.market_value <= e.equity + 1e-6).all()


def test_cost_scenarios_exact_and_adverse():
    s = pd.read_csv(DEV / "v2_cost_sensitivity.csv"); assert s.total_bps_per_side.tolist() == [0, 10, 25, 50]
    assert s.cumulative_return.iloc[0] >= s.cumulative_return.iloc[1] >= s.cumulative_return.iloc[2] >= s.cumulative_return.iloc[3]


def test_acceptance_gate_fields_and_decision():
    a = acceptance(); assert set(a["gates"]) == {"operational_invariants", "mean_weekly_gross_turnover", "primary_25bps_cumulative_return", "primary_25bps_CAGR", "primary_25bps_Sharpe", "cost_retention_ratio", "maximum_drawdown", "single_stock_contribution_share", "single_sector_contribution_share"}
    assert a["decision"] == "CONDITIONAL PROSPECTIVE CANDIDATE"


def test_no_forbidden_factor_or_post_boundary_artifacts():
    report = (V2 / "phase12c_sector_momentum_strategy_v2.md").read_text().lower()
    assert "rev05" not in report and "volume + momentum" not in report
    assert "post-2026-09-17" in report


def test_deterministic_manifest_outputs():
    m = json.loads((V2 / "phase12c_v2_build_manifest.json").read_text())
    assert len(m["output_sha256"]) == 17
    assert m["build_id"] == "96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb"


def test_v1_and_phase12a_references_unchanged():
    c = pd.read_csv(DEV / "v2_v1_comparison.csv").set_index("metric")
    assert c.loc["mean_weekly_gross_turnover", "V1"] == 0.942
    assert c.loc["maximum_drawdown", "V1"] == -0.4622
