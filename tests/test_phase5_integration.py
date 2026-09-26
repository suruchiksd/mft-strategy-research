import json
from pathlib import Path

import pandas as pd

from mft_research.data.manifest import sha256

PROJECT=Path(__file__).resolve().parents[1]


def test_phase5_outputs_and_deterministic_proof():
    root=PROJECT/"reports/csrs/point_in_time"
    manifest=json.loads((root/"phase5_build_manifest.json").read_text())
    proof=json.loads((root/"phase5_rebuild_verification.json").read_text())
    assert proof["byte_identical"] and proof["build_id"]==manifest["build_id"]
    for name,digest in manifest["output_sha256"].items():
        path=(PROJECT/"data/derived/historical_nse_daily.parquet" if name=="historical_nse_daily.parquet" else
              PROJECT/"reports/phase5_point_in_time_csrs.md" if name=="phase5_point_in_time_csrs.md" else root/name)
        assert sha256(path)==digest


def test_all_universes_preserve_all_30_pairs_and_no_trading_pnl():
    root=PROJECT/"reports/csrs/point_in_time"; expected={(f,h) for f in (5,10,20,40,60) for h in (1,2,3,5,10,20)}
    for name in ("csrs_broad_eq.csv","csrs_basic_liquid.csv","csrs_moderate_liquid.csv","csrs_strict_sensitivity.csv"):
        frame=pd.read_csv(root/name)
        for tier in ("PRIMARY_VERIFIED","BROAD_SENSITIVITY"):
            part=frame[frame.analysis_tier.eq(tier)]
            assert set(zip(part.formation_horizon,part.future_horizon))==expected
        assert not any(token in column.lower() for column in frame for token in ("portfolio","pnl","trading_return","combined","weighted"))
    expanding=pd.read_csv(root/"expanding_window_results.csv")
    assert set(expanding.evaluation_year)=={2021,2022,2023,2024,2025,2026}
    assert (expanding.history_end_year==expanding.evaluation_year-1).all()


def test_current_comparison_reports_uncertainty_and_identical_grid():
    frame=pd.read_csv(PROJECT/"reports/csrs/point_in_time/current120_vs_pointintime.csv")
    assert {"current120_ci_width","point_ci_width","ci_width_change","ic_sign_preserved"}.issubset(frame.columns)
    assert len(frame)==240


def test_historical_daily_identity_and_membership_contract():
    daily=pd.read_parquet(PROJECT/"data/derived/historical_nse_daily.parquet")
    assert daily.series.eq("EQ").all() and not daily.duplicated(["symbol","date"]).any()
    assert daily.symbol.nunique()==3381
    assert daily.identity_status.eq("OBSERVED_SYMBOL_NOT_STITCHED").all()
    assert {"universe_broad_eq","universe_basic_liquid","universe_moderate_liquid","universe_strict_sensitivity"}.issubset(daily.columns)


def test_phase3_and_phase4_accepted_artifacts_unchanged():
    p3=json.loads((PROJECT/"reports/csrs/csrs_build_manifest.json").read_text())
    p4=json.loads((PROJECT/"reports/csrs/validation/phase4_build_manifest.json").read_text())
    assert sha256(PROJECT/"data/derived/csrs_factor_panel.parquet")==p3["panel_sha256"]
    for name,digest in p4["output_sha256"].items(): assert sha256(PROJECT/"reports/csrs/validation"/name)==digest
