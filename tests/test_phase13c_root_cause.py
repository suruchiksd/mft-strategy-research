import hashlib,json
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; H=ROOT/'reports/sector_strategy/v2/paper_handoff'; OUT=H/'phase13c'
EXPECTED={'historical_target_to_order_parity.csv':'8b41348bb0baff1a8c39616c6a435ab7210abf7a44cd887ea1eb4c6f0e9f9e7e','historical_risk_parity.csv':'1aa8a9af1148bf33df06c54705a9c86228c6bd17c39d0e49154396d7af82ff68','phase13b_execution_parity_manifest.json':'3ffed4c8f0d6e0041bfafe5c700b61336fc1b32af161d778447a7aff2dcbcb9b'}
def test_phase13b_evidence_unchanged():
    assert all(hashlib.sha256((H/f).read_bytes()).hexdigest()==h for f,h in EXPECTED.items())
def test_all_mismatches_classified():
    x=pd.read_csv(OUT/'order_mismatch_attribution.csv'); assert len(x)==101; assert x.classification.notna().all(); assert x.root_cause.notna().all()
def test_all_rejections_reconcile():
    x=pd.read_csv(OUT/'risk_rejection_attribution.csv'); assert len(x)==3657; assert x.reason.value_counts().to_dict()=={'insufficient available cash':3656,'maximum open positions reached':1}
def test_strategy_integrity_and_boundary():
    s=json.loads((OUT/'phase13c_root_cause_summary.json').read_text()); assert s['phase12b_preregistration_hash']=='2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f'; assert s['phase12c_build']=='96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb'; assert s['post_boundary_performance_inspected'] is False
def test_no_performance_outputs_created():
    assert not any('return' in p.name or 'sharpe' in p.name or 'drawdown' in p.name for p in OUT.iterdir())

def test_phase13d_remains_unaccepted():
    m=json.loads((OUT.parent/'phase13d/phase13d_manifest.json').read_text()); assert m['decision']=='PAPER ENGINE NOT READY'; assert m['post_2026_09_17_performance_inspected'] is False
