import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd

from mft_research.ca_extension import classify_subject, parse_official

ROOT=Path(__file__).resolve().parents[1]
PREREG_SHA="fb0976eeea5dc524f4bb9a22dad98b6b0ec6fc42507dcc90f9d5f16d52da6995"


def sha(path):
    h=hashlib.sha256();h.update(Path(path).read_bytes());return h.hexdigest()


def builder():
    path=ROOT/"scripts/build_phase10_ca_extension.py";spec=importlib.util.spec_from_file_location("caext",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_original_preregistration_hash_unchanged():
    assert sha(ROOT/"reports/reversal/preregistration/phase10_preregistration_manifest.json")==PREREG_SHA


def test_raw_official_sources_are_preserved_and_hashed():
    m=json.loads((ROOT/"reports/reversal/corporate_action_extension/official_source_manifest.json").read_text())
    for request in m["requests"]:assert sha(ROOT/request["body"])==request["body_sha256"]


def test_overlap_period_exists_and_reconciles():
    frame=pd.read_csv(ROOT/"reports/reversal/corporate_action_extension/overlap_reconciliation.csv")
    accepted=frame[frame.relationship.str.startswith("ACCEPTED")]
    assert len(accepted)==647 and accepted.relationship.eq("ACCEPTED_MATCHED_EXACT").sum()==646


def test_action_mapping_is_deterministic():
    assert classify_subject("Bonus 1:1")[1]=="BLOCK_PRICE_RETURN_INTERVAL"
    assert classify_subject("Dividend - Rs 2 Per Share")[1]=="NONBLOCKING_INFORMATIONAL"
    assert classify_subject("Buy Back")[1]=="NONBLOCKING_INFORMATIONAL"


def test_unknown_actions_are_never_silently_safe():
    assert classify_subject("Novel unclassified entitlement")[1] in {"BLOCK_PRICE_RETURN_INTERVAL","REVIEW_REQUIRED_BLOCKED"}
    assert classify_subject("Completely novel corporate event")[1]=="REVIEW_REQUIRED_BLOCKED"


def test_blocking_date_is_frozen_to_official_ex_date():
    ledger=pd.read_parquet(ROOT/"data/derived/phase10_corporate_action_extension.parquet")
    assert (ledger.blocking_date==ledger.ex_date).all()


def test_no_fuzzy_company_name_matching():
    ledger=pd.read_parquet(ROOT/"data/derived/phase10_corporate_action_extension.parquet")
    mapped=ledger[ledger.mapped_symbol.notna()]
    assert mapped.mapped_symbol.eq(mapped.raw_symbol).all()
    assert set(ledger.mapping_status)<={"EXACT_SYMBOL_ISIN_OBSERVED","EXACT_SYMBOL_ISIN_CONFLICT","NOT_IN_RESEARCH_DATA"}


def test_identity_conflicts_are_blocked():
    ledger=pd.read_parquet(ROOT/"data/derived/phase10_corporate_action_extension.parquet")
    conflict=ledger[ledger.mapping_status.eq("EXACT_SYMBOL_ISIN_CONFLICT")]
    assert len(conflict)>0 and conflict.safety_classification.eq("REVIEW_REQUIRED_BLOCKED").all()


def test_extension_covers_every_possible_admitted_endpoint():
    ledger=pd.read_parquet(ROOT/"data/derived/phase10_corporate_action_extension.parquet")
    assert min(ledger.ex_date)==pd.Timestamp("2026-07-20").date()
    assert max(ledger.ex_date)==pd.Timestamp("2026-09-11").date()
    manifest=json.loads((ROOT/"reports/reversal/corporate_action_extension/phase10_ca_extension_manifest.json").read_text())
    assert manifest["extension_coverage_end"]=="2026-09-11"


def test_no_post_cutoff_reversal_outcome_was_inspected_during_extension():
    manifest=json.loads((ROOT/"reports/reversal/corporate_action_extension/phase10_ca_extension_manifest.json").read_text())
    assert manifest["post_cutoff_reversal_outcomes_inspected"] is False


def test_original_phase5_ledger_and_gated_phase10_unchanged():
    b=builder();c=b.config();frozen=b.verify_frozen_inputs(c)
    assert frozen["phase10_gated_build_id"]=="cda8c86bfa6b904d1f6a8975ca3eb3257f528658ee3dd9cb5719a811cb9cdc91"
    gated=json.loads((ROOT/"reports/reversal/research/phase10_build_manifest.json").read_text())
    assert gated["post_cutoff_outcomes_inspected"] is False


def test_extension_acceptance_gate_passes_conditionally():
    a=json.loads((ROOT/"reports/reversal/corporate_action_extension/extension_acceptance.json").read_text())
    assert a["decision"]=="CONDITIONAL PASS FOR REVERSAL CONFIRMATION"
    assert all(check["passed"] for check in a["checks"])
    assert a["accepted_blocking_exact_matches"]==60 and a["accepted_blocking_false_negatives"]==1


def test_confirmation_rules_remain_semantically_identical_to_preregistration():
    prereg=json.loads((ROOT/"reports/reversal/preregistration/phase10_preregistration_manifest.json").read_text())
    for path,digest in prereg["frozen_file_sha256"].items():assert sha(ROOT/path)==digest


def test_deterministic_extension_rebuild_proof():
    proof=json.loads((ROOT/"reports/reversal/corporate_action_extension/phase10_ca_extension_rebuild_verification.json").read_text())
    assert proof["byte_identical"] is True and proof["output_count"]==10
