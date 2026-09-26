import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def builder():
    path=ROOT/"scripts/build_phase10_reversal.py"
    spec=importlib.util.spec_from_file_location("phase10_builder",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_preregistration_precedes_confirmation_and_is_immutable():
    m=builder();config=m.load_config();prereg,digest=m.verify_preregistration(config)
    build=json.loads((ROOT/"reports/reversal/research/phase10_build_manifest.json").read_text())
    assert prereg["post_cutoff_outcomes_inspected"] is False
    assert build["preregistration_manifest_sha256"]==digest
    assert datetime.fromisoformat(prereg["frozen_at_utc"]) < datetime.fromisoformat(build["build_timestamp_utc"])


def test_accepted_phase5_through_phase9_artifacts_unchanged():
    m=builder();result=m.verify_accepted(m.load_config())
    assert [result[f"phase{x}_verified_outputs"] for x in range(5,10)]==[24,15,21,14,22]


def test_ca_extension_uses_accepted_semantics_and_blocks_confirmation():
    m=builder();audit,accepted,latest=m.corporate_action_audit(m.load_config())
    assert accepted is False and latest=="2026-07-17"
    assert not audit.extension_accepted.any()
    assert set(pd.read_csv(ROOT/"reports/reversal/research/confirmation_coverage.csv").status)=={"NO_CERTIFIED_CONFIRMATION_SAMPLE"}


def test_confirmation_outputs_have_no_uncertified_rows_or_forbidden_values():
    directory=ROOT/"reports/reversal/research"
    names=["confirmation_rank_ic_daily.csv","confirmation_rank_ic_summary.csv","confirmation_decile_returns.csv",
           "confirmation_tail_analysis.csv","confirmation_nonoverlap.csv","confirmation_uncertainty.csv",
           "universe_sensitivity.csv","leave_one_date_out.csv"]
    for name in names:
        frame=pd.read_csv(directory/name);assert frame.empty
        assert not any(any(token in column.lower() for token in ("volume","sector_momentum","portfolio","pnl","trading")) for column in frame.columns)
    coverage=pd.read_csv(directory/"confirmation_coverage.csv")
    assert len(coverage)==12 and coverage.valid_dates.eq(0).all() and coverage.stock_observations.eq(0).all()


def test_historical_reexpression_and_deterministic_proof():
    historical=pd.read_csv(ROOT/"reports/reversal/research/historical_discovery_summary.csv")
    assert len(historical)==12 and historical.mean_rank_ic.gt(0).all()
    assert set(historical.evidence_status)=={"DISCOVERY_HISTORICAL_NOT_OOS"}
    proof=json.loads((ROOT/"reports/reversal/research/phase10_rebuild_verification.json").read_text())
    assert proof["byte_identical"] is True and proof["output_count"]==14
