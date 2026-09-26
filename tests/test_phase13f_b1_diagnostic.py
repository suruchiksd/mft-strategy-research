import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/sector_strategy/v2/paper_handoff/phase13f'
OUT=BASE/'b1_resize_diagnostic'

def test_a_b_evidence_counts_unchanged():
    a=pd.read_csv(BASE/'a_open_valuation/order_parity.csv'); b=pd.read_csv(BASE/'b_retained_resize/order_parity.csv')
    assert (len(a),int((a.result=='PASS').sum()))==(112,47)
    assert (len(b),int((b.result=='PASS').sum()))==(112,52)
    s=json.loads((OUT/'phase13f_b1_summary.json').read_text())
    assert s['a_to_b_new_rejections']==60 and s['a_to_b_resolved_rejections']==56

def test_all_b_cap_rejections_and_mismatches_audited():
    c=pd.read_csv(OUT/'b_cap_rejection_trace.csv'); m=pd.read_csv(OUT/'remaining_60_mismatch_attribution.csv')
    assert len(c)==66 and c.open_position_count_before.eq(9).all() and c.free_slots_before.eq(0).all()
    assert len(m)==60 and m.classification.notna().all() and m.root_cause.notna().all()

def test_identity_and_boundary_outputs():
    i=pd.read_csv(OUT/'retained_identity_audit.csv'); assert bool(i.equality.iloc[0]) and bool(i.membership.iloc[0])
    b=pd.read_csv(OUT/'resize_boundary_behavior.csv')
    assert b.loc[b.deviation.eq(.0199),'actual_side'].iloc[0]=='NONE'
    assert set(b.loc[b.deviation.ge(.02),'actual_side']) <= {'BUY','SELL'}

def test_no_post_boundary_and_hashes():
    s=json.loads((OUT/'phase13f_b1_summary.json').read_text())
    assert s['phase12b_hash']=='2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f'
    assert s['phase12c_build']=='96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb'
    assert s['post_boundary_performance_inspected'] is False
