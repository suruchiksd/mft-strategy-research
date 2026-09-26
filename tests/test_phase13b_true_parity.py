from pathlib import Path
import json,pandas as pd
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'reports/sector_strategy/v2/paper_handoff'
def test_reference_trades_loaded_after_engine_generation():
    s=(ROOT/'scripts/run_phase13b_true_parity.py').read_text(); assert s.index("ref=pd.read_csv") > s.index("actual=[]")
def test_true_parity_is_not_self_reference():
    x=pd.read_csv(OUT/'historical_target_to_order_parity.csv'); assert 'actual_quantity' in x; assert len(x)>0; assert (x.result=='FAIL').any()
def test_v2_integrity_and_no_post_boundary():
    m=json.loads((OUT/'phase13b_execution_parity_manifest.json').read_text()); assert m['strategy_preregistration_hash']=='2e99d105d6a23538dafcaa4d6c17ba71b008c2e30fee63bec2cb50706a6aee2f'; assert m['strategy_build_reference']=='96e614a5638f221b1c340e4f9201e792b5c01e1394eac682ef7b53480aa0f2fb'; assert not m['post_2026_09_17_performance_inspected']; assert m['decision']=='PAPER ENGINE NOT READY'
