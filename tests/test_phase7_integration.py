import json
from pathlib import Path

import pandas as pd

from mft_research.data.manifest import sha256
from mft_research.sector_momentum import daily_pair_statistics, pair_work, summarize_daily

PROJECT=Path(__file__).resolve().parents[1]


def _artifact(phase,manifest_path,name):
    if phase==5:
        return (PROJECT/"data/derived/historical_nse_daily.parquet" if name=="historical_nse_daily.parquet" else
                PROJECT/"reports/phase5_point_in_time_csrs.md" if name=="phase5_point_in_time_csrs.md" else manifest_path.parent/name)
    return (PROJECT/"data/derived/sector_research_mapping.parquet" if name=="sector_research_mapping.parquet" else
            PROJECT/"reports/phase6_sector_foundation.md" if name=="phase6_sector_foundation.md" else manifest_path.parent/name)


def test_phase5_phase6_accepted_artifacts_unchanged():
    for phase,path in ((5,PROJECT/"reports/csrs/point_in_time/phase5_build_manifest.json"),
                       (6,PROJECT/"reports/sector_momentum/foundation/phase6_build_manifest.json")):
        manifest=json.loads(path.read_text())
        for name,digest in manifest["output_sha256"].items(): assert sha256(_artifact(phase,path,name))==digest


def test_phase7_outputs_and_deterministic_proof():
    root=PROJECT/"reports/sector_momentum/research"
    manifest=json.loads((root/"phase7_build_manifest.json").read_text())
    proof=json.loads((root/"phase7_rebuild_verification.json").read_text())
    acceptance=json.loads((root/"phase7_acceptance.json").read_text())
    assert proof["byte_identical"] and proof["build_id"]==manifest["build_id"]
    assert all(item["passed"] for item in acceptance)
    for name,digest in manifest["output_sha256"].items():
        path=(PROJECT/"data/derived/sector_momentum_factor_panel.parquet" if name.endswith(".parquet") else
              PROJECT/"reports/phase7_sector_relative_momentum.md" if name.endswith(".md") else root/name)
        assert sha256(path)==digest


def test_all_30_pairs_chronology_offsets_and_sensitivities():
    root=PROJECT/"reports/sector_momentum/research"; expected={(f,h) for f in (5,10,20,40,60) for h in (1,2,3,5,10,20)}
    summary=pd.read_csv(root/"rank_ic_summary.csv")
    assert set(zip(summary.formation_horizon,summary.future_horizon))==expected
    expanding=pd.read_csv(root/"expanding_window_results.csv")
    assert (expanding.history_end_year==expanding.evaluation_year-1).all()
    assert (pd.to_datetime(expanding.history_actual_last_date).dt.year < expanding.evaluation_year).all()
    assert (pd.to_datetime(expanding.evaluation_actual_first_date).dt.year == expanding.evaluation_year).all()
    assert expanding.groupby("evaluation_year").size().eq(30).all()
    non=pd.read_csv(root/"nonoverlap_results.csv")
    assert all(set(group.offset)==set(range(h)) for (_,h),group in non.groupby(["formation_horizon","future_horizon"]))
    assert non.spacing_valid.all()
    assert (non.minimum_signal_spacing_sessions >= non.future_horizon).all()
    assert set(pd.read_csv(root/"sector_size_sensitivity.csv").minimum_sector_size)=={3,5,10}
    assert set(pd.read_csv(root/"universe_mapping_sensitivity.csv").research_tier)=={
        "STABLE_IDENTITY_BASIC_LIQUID","STABLE_IDENTITY_MODERATE_LIQUID","STABLE_IDENTITY_BROAD","STATIC_UNIQUE_BROAD"}


def test_panel_membership_quintiles_influence_and_no_trading_fields():
    root=PROJECT/"reports/sector_momentum/research"
    panel=pd.read_parquet(PROJECT/"data/derived/sector_momentum_factor_panel.parquet")
    assert panel.research_tier.eq("STABLE_IDENTITY_BASIC_LIQUID").all()
    assert panel.minimum_sector_size.eq(5).all()
    assert panel.mapping_provenance.eq("STATIC_CURRENT_NO_EFFECTIVE_DATES").all()
    rank=pd.read_csv(root/"rank_ic_daily.csv")
    assert rank.loc[rank.quantile_available,"eligible_sector_count"].ge(15).all()
    loo=pd.read_csv(root/"leave_one_sector_out.csv")
    assert loo.removed_only_intended_sector.all() and loo.excluded_sector.nunique()==panel.sector.nunique()
    sample=loo[(loo.formation_horizon.eq(5))&loo.future_horizon.eq(1)].iloc[0]
    reduced=panel[panel.sector.ne(sample.excluded_sector)].copy()
    work=pair_work(reduced,5,1).sort_values(["date","factor","sector_code"],kind="stable")
    work["rank"]=work.groupby("date",sort=False).cumcount()+1
    work["eligible_sector_count"]=work.groupby("date",sort=False).sector_code.transform("size")
    count=work.eligible_sector_count
    work["quintile"]=(((work["rank"]-1)*5//count)+1).where(count.ge(15),0).astype(int)
    k=count.mul(.2).apply(__import__('math').ceil)
    work["top20"]=work["rank"].gt(count-k); work["bottom20"]=work["rank"].le(k)
    work["top3"]=count.ge(6)&work["rank"].gt(count-3); work["bottom3"]=count.ge(6)&work["rank"].le(3)
    exact=summarize_daily(daily_pair_statistics(work))
    assert abs(exact["mean_ic"]-sample.excluded_mean_ic)<1e-12
    for path in [PROJECT/"data/derived/sector_momentum_factor_panel.parquet",*root.glob("*.csv")]:
        columns=pd.read_parquet(path).columns if path.suffix==".parquet" else pd.read_csv(path,nrows=0).columns
        assert not any(token in column.lower() for column in columns for token in
                       ("combined","weighted_factor","portfolio","pnl","trading_return"))
