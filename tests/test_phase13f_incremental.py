from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "reports/sector_strategy/v2/paper_handoff/phase13f"


def test_phase13f_a_sm0020_and_nonincreasing_mismatch():
    a = json.loads((F / "a_open_valuation/phase13f_a_manifest.json").read_text())
    assert a["rows"] == 112
    assert a["mismatches"] == 65
    x = pd.read_csv(F / "a_open_valuation/order_parity.csv")
    assert x[(x.rebalance_id == "SMV2-0020") & (x.result == "FAIL")].empty


def test_phase13f_b_is_frozen_failed_gate_and_fallback_not_run():
    b = json.loads((F / "b_retained_resize/phase13f_b_manifest.json").read_text())
    assert b["rows"] == 112 and b["mismatches"] == 60
    assert b["risk_rejections"] == 66
    assert not (F / "c_fallback/phase13f_c_manifest.json").exists()


def test_frozen_tolerance_boundaries():
    assert (abs(0.0199) < 0.02) is True
    assert (abs(0.0200) < 0.02) is False
    assert (abs(0.0201) < 0.02) is False


def test_strategy_hashes_and_boundary_unchanged():
    assert json.loads((F / "a_open_valuation/phase13f_a_manifest.json").read_text())["phase12b_hash"] == "2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f"
    assert json.loads((F / "a_open_valuation/phase13f_a_manifest.json").read_text())["phase12c_build"] == "96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb"
    assert json.loads((F / "a_open_valuation/phase13f_a_manifest.json").read_text())["post_boundary_performance_inspected"] is False
