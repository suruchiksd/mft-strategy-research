import hashlib
import json
from itertools import product
from pathlib import Path

import pandas as pd
import yaml

from mft_research.reversal_amendment import (CANDIDATE_CLASSES, classify_candidate,
    classify_overall, directional_retention, enumerate_candidate_states, overall_decision_table)

ROOT=Path(__file__).resolve().parents[1]
PREREG="fb0976eeea5dc524f4bb9a22dad98b6b0ec6fc42507dcc90f9d5f16d52da6995"
EXTENSION="8ad77b280031a1f9d99f6ce85a2078e6f6457a3ffdc39a9a0c6e9857225abc13"


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def config():return yaml.safe_load((ROOT/"config/phase10_classification_amendment.yaml").read_text())


def test_every_candidate_state_maps_exactly_once():
    frame=enumerate_candidate_states()
    assert len(frame)==7*7*7*2*2*2*3==8232
    assert not frame.drop(columns="classification").duplicated().any()
    assert not frame.classification.isna().any()
    assert set(frame.classification)==set(CANDIDATE_CLASSES)


def test_hierarchy_predicates_are_mutually_exclusive_and_exhaustive():
    for p,m,n,basic,moderate,flip,dates in product(range(7),range(7),range(7),(False,True),(False,True),(False,True),("LT20","20_TO_59","GE60")):
        stable=directional_retention(p,m,n,basic,moderate,flip)
        matches=[dates=="LT20",dates!="LT20" and p<=1,dates!="LT20" and 2<=p<=3,
          dates!="LT20" and p>=4 and not stable,dates=="20_TO_59" and p>=4 and stable,
          dates=="GE60" and p>=4 and stable]
        assert sum(matches)==1
        assert classify_candidate(p,m,n,basic,moderate,flip,dates)==CANDIDATE_CLASSES[matches.index(True)]


def test_four_or_more_positive_with_any_robustness_failure_is_unstable():
    cases=[(4,3,6,True,True,False),(5,6,3,True,True,False),(6,6,6,False,True,False),
           (6,6,6,True,False,False),(6,6,6,True,True,True)]
    for values in cases:
        assert classify_candidate(*values,"20_TO_59")=="DIRECTIONALLY POSITIVE BUT UNSTABLE"
        assert classify_candidate(*values,"GE60")=="DIRECTIONALLY POSITIVE BUT UNSTABLE"


def test_date_thresholds_have_priority_and_are_unchanged():
    assert classify_candidate(6,6,6,True,True,False,"LT20")=="INSUFFICIENT SAMPLE"
    assert classify_candidate(6,6,6,True,True,False,"20_TO_59")=="SUPPORTIVE BUT SHORT SAMPLE"
    assert classify_candidate(6,6,6,True,True,False,"GE60")=="SUPPORTED"


def test_all_36_overall_pairs_map_once():
    table=overall_decision_table()
    assert len(table)==36 and not table.duplicated(["REV05_classification","REV20_classification"]).any()
    for a,b in product(CANDIDATE_CLASSES,repeat=2):
        assert len(table[(table.REV05_classification==a)&(table.REV20_classification==b)])==1


def test_overall_precedence_and_edge_pairs():
    assert classify_overall("SUPPORTED","SUPPORTED")=="PASS FOR COMPLEMENTARITY RESEARCH"
    assert classify_overall("SUPPORTED","CONTRADICTORY")=="CONDITIONAL PASS"
    assert classify_overall("SUPPORTIVE BUT SHORT SAMPLE","SUPPORTIVE BUT SHORT SAMPLE")=="CONDITIONAL PASS"
    assert classify_overall("CONTRADICTORY","CONTRADICTORY")=="FAIL"
    assert classify_overall("SUPPORTIVE BUT SHORT SAMPLE","CONTRADICTORY")=="RESEARCH FURTHER"
    assert classify_overall("DIRECTIONALLY POSITIVE BUT UNSTABLE","SUPPORTED")=="CONDITIONAL PASS"


def test_factor_definitions_universes_and_outcomes_unchanged():
    c=config()
    assert c["candidates"]==["REV05","REV20"]
    assert c["candidate_formulas"]=={"REV05":"-1 * price_return_5","REV20":"-1 * price_return_20"}
    assert (c["primary_universe"],c["sensitivity_universe"])==("BASIC_LIQUID","MODERATE_LIQUID")
    assert c["future_horizons"]==[1,2,3,5,10,20]
    assert c["new_confirmation_signal_start_exclusive"]=="2026-09-11"


def test_original_preregistration_registry_and_blocker_unchanged():
    c=config();manifest=json.loads((ROOT/c["inputs"]["preregistration_manifest"]).read_text())
    assert sha(ROOT/c["inputs"]["preregistration_manifest"])==PREREG
    assert sha(ROOT/c["inputs"]["candidate_registry"])==manifest["frozen_file_sha256"]["reports/reversal/preregistration/reversal_candidate_registry.csv"]
    assert sha(ROOT/c["inputs"]["blocker_report"])=="a22db930294f54032d98036926ef0d71d74fa12748beae84be6d645d0a755567"


def test_extension_and_prior_accepted_outputs_unchanged():
    c=config();extension=json.loads((ROOT/c["inputs"]["extension_manifest"]).read_text())
    assert extension["build_id"]==EXTENSION
    manifest=json.loads((ROOT/"reports/reversal/amendment/phase10_amendment_manifest.json").read_text())
    assert manifest["immutable_inputs"]["extension_verified_outputs"]==10
    assert [manifest["immutable_inputs"][f"phase{x}_verified_outputs"] for x in range(5,10)]==[24,15,21,14,22]
    assert manifest["immutable_inputs"]["gated_phase10_verified_outputs"]==14


def test_amendment_does_not_claim_new_validation():
    manifest=json.loads((ROOT/"reports/reversal/amendment/phase10_amendment_manifest.json").read_text())
    assert manifest["new_data_inspected"] is False
    assert manifest["observed_sample_status"]=="RULE_GAP_AMENDMENT_DEVELOPMENT_EVIDENCE"
    assert manifest["retrospective_mapping"]=={"REV05":"DIRECTIONALLY POSITIVE BUT UNSTABLE","REV20":"CONTRADICTORY"}
    assert manifest["accepted_overall_phase10_decision"]=="RESEARCH FURTHER"


def test_published_tables_match_executable_rules():
    candidate=pd.read_csv(ROOT/"reports/reversal/amendment/phase10_complete_classification_table.csv")
    overall=pd.read_csv(ROOT/"reports/reversal/amendment/phase10_overall_decision_table.csv")
    assert candidate.classification.tolist()==list(CANDIDATE_CLASSES)
    pd.testing.assert_frame_equal(overall,overall_decision_table())
