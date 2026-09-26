import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'reports/sector_strategy/v2/paper_handoff/phase13f/b2_exact_sequence'

def test_b2_counts_and_failure_frozen():
    m=json.loads((P/'phase13f_b2_manifest.json').read_text())
    assert m['rows']==112 and m['exact']==52 and m['mismatches']==60
    assert m['risk_rejections']==64 and m['insufficient_cash_rejections']==0
    assert m['post_boundary_performance_inspected'] is False

def test_b2_first_divergence_dynamic_artifact():
    x=pd.read_csv(P/'first_divergence.csv')
    assert x.first_divergent_rebalance.iloc[0]=='SMV2-0087'

def test_b2_all_remaining_rows_classified():
    x=pd.read_csv(P/'remaining_mismatch_attribution.csv')
    assert len(x)==60 and x.classification.notna().all() and x.root_cause.notna().all()

def test_b2_integrity_hashes():
    m=json.loads((P/'phase13f_b2_manifest.json').read_text())
    assert m['phase12b_hash']=='2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f'
    assert m['phase12c_build']=='96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb'
