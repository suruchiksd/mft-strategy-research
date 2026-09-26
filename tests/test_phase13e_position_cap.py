import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HAND = ROOT / "reports/sector_strategy/v2/paper_handoff"
REP = HAND / "phase13d/repaired"
OUT = HAND / "phase13e"


def test_phase13b_immutable_and_repaired_counts():
    expected = {
        "historical_target_to_order_parity.csv": "8b41348bb0baff1a8c39616c6a435ab7210abf7a44cd887ea1eb4c6f0e9f9e7e",
        "historical_risk_parity.csv": "1aa8a9af1148bf33df06c54705a9c86228c6bd17c39d0e49154396d7af82ff68",
        "phase13b_execution_parity_manifest.json": "3ffed4c8f0d6e0041bfafe5c700b61336fc1b32af161d778447a7aff2dcbcb9b",
    }
    for name, digest in expected.items():
        assert hashlib.sha256((HAND / name).read_bytes()).hexdigest() == digest
    x = pd.read_csv(REP / "target_to_order_parity_repaired.csv")
    r = pd.read_csv(REP / "risk_decisions_repaired.csv")
    assert (len(x), int((x.result == "PASS").sum()), int((x.result != "PASS").sum())) == (112, 30, 82)
    assert (len(r), int((~r.approved).sum()), int((~r.approved & r.reason.eq("maximum open positions reached")).sum())) == (2021, 58, 58)
    assert int((~r.approved & r.reason.eq("insufficient available cash")).sum()) == 0


def test_phase13d_repaired_manifest_and_boundary():
    m = json.loads((REP / "phase13d_repaired_manifest.json").read_text())
    assert m["phase12b_hash"] == "2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f"
    assert m["phase12c_build"] == "96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb"
    assert m["post_boundary_performance_inspected"] is False


def test_phase13e_exhaustive_mismatch_and_rejection_audits():
    x = pd.read_csv(OUT / "remaining_mismatch_attribution.csv")
    assert len(x) == 82 and x.classification.notna().all() and x.primary_root_cause.notna().all()
    r = pd.read_csv(OUT / "position_cap_rejection_audit.csv")
    assert len(r) == 58 and r.root_cause.notna().all()


def test_phase13e_first_divergence_and_no_post_boundary():
    s = json.loads((OUT / "phase13e_root_cause_summary.json").read_text())
    assert s["last_exact_sample"] == "SMV2-0019"
    assert s["first_divergent_sample"] == "SMV2-0020"
    assert s["post_boundary_performance_inspected"] is False


def test_phase13e_features_are_explicitly_unimplemented_without_mutation():
    x = pd.read_csv(OUT / "phase13d_feature_implementation_audit.csv").set_index("feature")
    assert x.loc["2pp retained-position resizing", "status"] == "NOT_IMPLEMENTED"
    assert x.loc["complete frozen fallback sequence", "status"] == "PARTIALLY_IMPLEMENTED"
