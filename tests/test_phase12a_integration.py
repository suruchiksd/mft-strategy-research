from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"reports/sector_strategy/v1_diagnostics"

def test_weight_attribution_is_retained_names_only_and_no_band_selected():
    x=pd.read_csv(OUT/"weight_rebalance_attribution.csv")
    assert x.absolute_weight_deviation.ge(0).all() and x.target_weight.gt(0).all()
    text=(OUT/"v2_design_requirements.md").read_text().lower()
    assert "weight band" in text and "none is selected" in text

def test_static_mapping_limit_and_fresh_v2_boundary_are_explicit():
    report=(ROOT/"reports/phase12a_sector_strategy_v1_diagnostics.md").read_text()
    assessment=(OUT/"factor_vs_implementation_assessment.md").read_text()
    assert "STATIC" in report.upper() and "strictly afterward" in report
    assert "BOTH, with implementation failure dominant" in assessment

def test_no_fabricated_price_or_exit_fields_exist():
    audit=pd.read_csv(OUT/"operational_exception_audit.csv")
    assert not audit.fabricated_exit.any()
    assert audit.loc[audit.eventual_exit_date.notna(),"eventual_exit_price"].gt(0).all()
