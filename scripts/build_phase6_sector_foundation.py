#!/usr/bin/env python3
"""Build the Phase-6 static-sector foundation and coverage audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from mft_research.data.manifest import canonical_json, sha256
from mft_research.sector_foundation import (alternative_source_inventory, audit_sector_files,
    build_mapping, concentration, historical_bias_label, historical_coverage, mapping_summary,
    tier_summary)


def local(value: str) -> Path:
    path = (PROJECT / value).resolve()
    if not path.is_relative_to(PROJECT):
        raise ValueError("Phase-6 output path escaped project")
    return path


def load_config() -> dict:
    config = yaml.safe_load((PROJECT / "config/phase6_sector_foundation.yaml").read_text())
    expected = {"BROAD_EQ", "BASIC_LIQUID", "MODERATE_LIQUID", "STRICT_SENSITIVITY"}
    if set(config["universe_columns"]) != expected:
        raise ValueError("All four accepted Phase-5 universes must be preserved")
    if tuple(config["viability_thresholds"]) != (3, 5, 10):
        raise ValueError("Frozen Phase-6 viability thresholds changed")
    if config["identity_policy"]["fuzzy_matching"] or config["identity_policy"]["stitch_aliases"]:
        raise ValueError("Phase-6 identity policy forbids fuzzy matching and stitching")
    return config


def verify_phase5(config: dict) -> dict:
    manifest = json.loads(local(config["phase5_manifest"]).read_text())
    for name, digest in manifest["output_sha256"].items():
        path = (local(config["historical_daily"]) if name == "historical_nse_daily.parquet" else
                PROJECT / "reports/phase5_point_in_time_csrs.md" if name == "phase5_point_in_time_csrs.md" else
                PROJECT / "reports/csrs/point_in_time" / name)
        if sha256(path) != digest:
            raise RuntimeError(f"Accepted Phase-5 artifact changed: {name}")
    return {"phase5_build_id": manifest["build_id"],
            "historical_daily_sha256": manifest["output_sha256"]["historical_nse_daily.parquet"],
            "verified_output_count": len(manifest["output_sha256"])}


def code_fingerprint() -> str:
    paths = [PROJECT / "config/phase6_sector_foundation.yaml",
             PROJECT / "scripts/build_phase6_sector_foundation.py",
             PROJECT / "src/mft_research/sector_foundation.py"] + sorted(PROJECT.glob("tests/test_phase6*.py"))
    records = [{"path": str(path.relative_to(PROJECT)), "sha256": sha256(path)} for path in sorted(paths)]
    return hashlib.sha256(canonical_json(records).encode()).hexdigest()


def render_report(outputs: dict[str, pd.DataFrame], mapping: pd.DataFrame, config: dict) -> tuple[str, str]:
    inventory = outputs["sector_source_inventory.csv"]
    curated = inventory[inventory.record_kind.eq("CURATED_SECTOR_FILE")]
    conflicts = outputs["sector_mapping_conflicts.csv"]
    coverage = outputs["historical_sector_coverage.csv"]
    viability = outputs["sector_viability_by_year.csv"]
    concentration_frame = outputs["sector_concentration.csv"]
    tiers = outputs["sector_research_tiers.csv"]
    stable = mapping.mapping_status.eq("STATIC_CURRENT_UNIQUE") & ~mapping.identity_ambiguous
    source_distinct = int(curated.distinct_symbols.sum() - outputs["sector_mapping_conflicts.csv"].assignment_count.sum() + len(outputs["sector_mapping_conflicts.csv"]))
    source_unique = source_distinct - len(outputs["sector_mapping_conflicts.csv"])
    historical_symbols = len(mapping)
    unmapped = mapping.mapping_status.eq("UNMAPPED").sum()
    static_unique = mapping.mapping_status.eq("STATIC_CURRENT_UNIQUE").sum()
    stable_count = stable.sum()
    bias = historical_bias_label(outputs["historical_validity_summary.csv"])
    primary = tiers[tiers.recommended_primary].iloc[0]
    liquid_cov = coverage.groupby("universe").usable_observation_pct.mean()
    basic_viable = viability[(viability.universe.eq("BASIC_LIQUID")) & viability.threshold.eq(5)].symbol_observation_retained_pct.mean()
    # Static labels can support conditional sensitivity work, but cannot be called point-in-time classification.
    decision = "CONDITIONAL PASS" if primary.sector_count >= 20 and basic_viable >= 75 else "RESEARCH FURTHER"
    yearly = coverage[["year", "universe", "eligible_symbols", "usable_mapping_symbols",
                       "usable_mapping_pct", "represented_sectors"]].copy()
    viability_summary = (viability.groupby(["universe", "threshold"], sort=True)
                         .agg(mean_symbol_retained_pct=("symbol_observation_retained_pct", "mean"),
                              median_usable_sectors_per_date=("median_usable_sectors_per_date", "median"))
                         .reset_index())
    primary_viability = viability[viability.universe.eq("BASIC_LIQUID")][
        ["year", "threshold", "median_usable_sectors_per_date", "min_usable_sectors_per_date",
         "max_usable_sectors_per_date", "symbol_observation_retained_pct"]]
    concentration_summary = (concentration_frame.groupby("universe", sort=True)
        .agg(median_largest_sector_share_pct=("median_largest_sector_share_pct", "median"),
             median_top3_sector_share_pct=("median_top3_sector_share_pct", "median"),
             median_sectors_ge10=("median_sectors_ge10", "median")).reset_index())
    chronic = (outputs["sector_size_distribution.csv"].groupby(["universe", "sector", "sector_code"])
               .agg(median_stock_count=("stock_count", "median"), pct_dates_ge3=("at_least_3", "mean"),
                    pct_dates_ge5=("at_least_5", "mean"), dates=("date", "nunique")).reset_index())
    chronic["pct_dates_ge3"] *= 100; chronic["pct_dates_ge5"] *= 100
    chronic = chronic[(chronic.universe.eq("BASIC_LIQUID")) & chronic.median_stock_count.lt(3)].sort_values(["median_stock_count", "sector"])
    def table(frame: pd.DataFrame, decimals: int = 2) -> str:
        def value(x):
            if pd.isna(x): return ""
            return f"{x:.{decimals}f}" if isinstance(x, float) else str(x)
        return "\n".join(["| " + " | ".join(frame.columns) + " |",
                          "| " + " | ".join(["---"] * len(frame.columns)) + " |"] +
                         ["| " + " | ".join(value(x) for x in row) + " |" for row in frame.itertuples(index=False, name=None)])
    lines = ["# Phase 6 — Sector Relative Momentum data and methodology foundation", "",
             f"**Foundation decision: {decision}**", "", f"**Historical-sector bias: {bias}**", "",
             "## 1. Executive summary", "",
             f"The source audit found {len(curated)} current, headerless sector files representing {curated.sector_code.nunique()} categories. They contain {int(curated.row_count.sum()):,} physical rows, {int(curated.blank_rows.sum())} blank row, {int(curated.duplicate_rows.sum())} duplicate rows, {source_distinct:,} distinct symbols, {source_unique:,} uniquely assigned symbols, and {len(conflicts)} symbols assigned to multiple files. No local classification source has historical effective dates.", "",
             f"Direct exact-symbol matching maps {static_unique:,} of {historical_symbols:,} Phase-5 tickers uniquely; {unmapped:,} are unmapped and {mapping.mapping_status.eq('STATIC_CURRENT_CONFLICT').sum():,} conflict. Requiring a non-ambiguous Phase-5 symbol identity leaves {stable_count:,} symbols. Every usable historical observation still relies on a static current label; none is historically verified.", "",
             f"The recommended Phase-7 primary research tier is `{primary.tier}`. It retains {int(primary.historical_observations):,} symbol-date observations across {int(primary.sector_count)} sectors. It supports conditional static-classification research, not a genuinely point-in-time sector study.", "",
             "## 2. Source audit", "",
             "All 40 curated files parse deterministically by the final underscore in the filename. `construction_supplies_CS.csv` and `sugar_SU.csv` each contain one repeated symbol; `chemicals_CM.csv` contains one blank record. No malformed nonblank record was found. Duplicate physical rows are reported but do not create duplicate membership assignments.", "",
             "The only separate mapping-shaped local source is a 50-row `stocks_name,sector` Nifty file duplicated byte-for-byte in two projects. It is current/static, has no effective dates, uses broader labels, and cannot establish historical classification. Ranked-universe snapshots and `research_sector_performance.csv` derive their labels from the curated files, so they add no independent provenance. Accepted Bhavcopy identity fields provide partial ISIN evidence only from the new format and contain no sector fields.", "",
             "## 3. Mapping contract", "",
             "`sector_research_mapping.parquet` contains one row per exact Phase-5 observed symbol. Conflicts remain null and unresolved; unmapped names remain null. No fuzzy matching or alias stitching occurs. Non-ambiguous exact observed symbols retain themselves as the local identity key; ambiguous identities have no canonical identity assigned.", "",
             "The provenance states are `STATIC_CURRENT_UNIQUE`, `STATIC_CURRENT_CONFLICT`, and `UNMAPPED`. Historical validity separately records `IDENTITY_AMBIGUOUS`. `HISTORICALLY_VERIFIED` has zero rows because no effective dates were found.", "",
             "## 4. Historical mapping coverage", "", table(yearly), "",
             "Liquid universes improve mapping coverage because the curated files focus on currently active securities. That improvement does not turn static labels into historical labels.", "",
             "Average usable observation coverage by universe:", "", table(liquid_cov.rename("usable_observation_pct").reset_index()), "",
             "## 5. Sector-size viability", "", table(viability_summary), "",
             "Thresholds are diagnostics only. They do not change Phase-5 universe membership and no factor or rank is calculated. A five-name threshold retains enough mapped symbol observations in the Basic Liquid tier to be a defensible primary Phase-7 floor, while three and ten names must remain prespecified sensitivity views.", "",
             "Basic Liquid stable-identity viability by year:", "", table(primary_viability), "",
             "Chronically sparse Basic Liquid sectors (median contemporaneous membership below three):", "",
             table(chronic[["sector", "sector_code", "median_stock_count", "pct_dates_ge3", "pct_dates_ge5", "dates"]]), "",
             "## 6. Concentration", "", table(concentration_summary), "",
             "The sector universe is uneven: finance, software, healthcare, automobiles, and capital goods contain many names, while several specialist categories remain sparse. Phase 7 must weight sectors as sector observations rather than allowing stock count alone to make large sectors dominate a sector-level cross-section.", "",
             "## 7. Static-mapping bias", "",
             f"Historical-sector bias is classified **{bias}** because 0% of classifications are effective-dated or historically verified. In Broad EQ, static unique labels cover {float(tiers.loc[tiers.tier.eq('STATIC_UNIQUE_BROAD'), 'observation_pct_of_universe'].iloc[0]):.2f}% of historical symbol-date observations; the stable-identity subset covers {float(tiers.loc[tiers.tier.eq('STABLE_IDENTITY_BROAD'), 'observation_pct_of_universe'].iloc[0]):.2f}%. There are {int(mapping.identity_ambiguous.sum())} ambiguous symbol identities, including {int((mapping.identity_ambiguous & mapping.mapping_status.eq('STATIC_CURRENT_UNIQUE')).sum())} that otherwise have a unique current mapping. Static mappings can misstate past sector membership after restructurings, business changes, symbol changes, mergers, and delistings. Identity filtering removes objectively ambiguous symbol histories but cannot validate the historical sector itself.", "",
             "This limitation is strongest among historical names absent from the current mapping and among categories with many conflicts, notably agriculture/sugar and chemicals/fertilisers. It cannot be corrected from the available local data.", "",
             "## 8. Proposed Phase-7 tiers", "", table(tiers), "",
             f"Primary: `{config['recommended_primary_tier']}` with a prespecified minimum sector size of five. Sensitivities: the same tier at three and ten names; `STABLE_IDENTITY_MODERATE_LIQUID` for liquidity; `STABLE_IDENTITY_BROAD` for breadth; and `STATIC_UNIQUE_BROAD` to measure identity-filter impact. Results must be labelled static-current-classification historical research.", "",
             "## 9. Decision", "",
             f"**{decision}**. Factor 2 can be researched responsibly only as a conditional static-classification study. Coverage and sector sizes are sufficient in the stable-identity liquid tier, but the absence of effective-dated classifications prevents an unconditional point-in-time claim.", "",
             "## 10. Exact Phase-7 design", "",
             "1. Freeze the four tiers and sector-size thresholds (3, 5, 10), with Stable Identity + Basic Liquid and at least five contemporaneous names as primary.",
             "2. Preregister sector-return aggregation, formation horizons, outcome labels, tie handling, and interval safety before viewing factor results.",
             "3. Calculate sector momentum only within each contemporaneous tier/date, report all prespecified parameter cells, and keep stock-level and sector-level sample counts explicit.",
             "4. Repeat chronological holdout, non-overlap, dependence-aware uncertainty, concentration, sector influence, and static-mapping sensitivity analyses.",
             "5. Keep Factor 1B reversal, Volume + Momentum, factor combinations, trading rules, and portfolios outside Phase 7.", "",
             "No sector return, sector momentum, ranking, combined score, or portfolio/trading P&L was generated in Phase 6.", ""]
    return "\n".join(lines), decision


def build(config: dict) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, str, dict]:
    sector_inventory, issues, conflicts, memberships = audit_sector_files(Path(config["sector_root"]))
    inventory = pd.concat([sector_inventory, alternative_source_inventory(config)], ignore_index=True)
    identity = pd.read_csv(local(config["phase5_identity"]), keep_default_na=False)
    identity["identity_ambiguity"] = identity.identity_ambiguity.astype(str).str.lower().eq("true")
    mapping = build_mapping(identity, memberships)
    historical = pd.read_parquet(local(config["historical_daily"]), columns=["date", "symbol", *config["universe_columns"].values()])
    coverage, sizes, viability, validity = historical_coverage(historical, mapping, config["universe_columns"])
    conflict_symbols = set(conflicts.symbol) if len(conflicts) else set()
    conflicts["observed_in_phase5"] = conflicts.symbol.isin(set(mapping.symbol)) if len(conflicts) else pd.Series(dtype=bool)
    conflicts["first_observed_date"] = conflicts.symbol.map(mapping.set_index("symbol").first_observed_date) if len(conflicts) else pd.Series(dtype=object)
    outputs = {
        "sector_source_inventory.csv": inventory,
        "sector_source_issues.csv": issues,
        "sector_mapping_conflicts.csv": conflicts,
        "sector_mapping_summary.csv": mapping_summary(sector_inventory, mapping),
        "historical_sector_coverage.csv": coverage,
        "sector_size_distribution.csv": sizes,
        "sector_viability_by_year.csv": viability,
        "sector_concentration.csv": concentration(sizes),
        "unmapped_historical_symbols.csv": mapping[mapping.mapping_status.eq("UNMAPPED")].copy(),
        "identity_sector_issues.csv": mapping[mapping.identity_ambiguous | mapping.symbol.isin(conflict_symbols)].copy(),
        "historical_validity_summary.csv": validity,
        "sector_research_tiers.csv": tier_summary(historical, mapping, sizes, config),
    }
    report, decision = render_report(outputs, mapping, config)
    metadata = {"decision": decision, "historical_sector_bias": historical_bias_label(validity),
                "sector_file_count": len(sector_inventory), "source_distinct_symbols": len(memberships),
                "historical_symbols": len(mapping), "conflict_symbols": len(conflicts),
                "source_files": sector_inventory[["path", "sha256"]].to_dict("records")}
    return outputs, mapping, report, metadata


def acceptance_checks(outputs: dict[str, pd.DataFrame], mapping: pd.DataFrame, metadata: dict, config: dict) -> list[dict]:
    checks = {
        "40 curated sector files": metadata["sector_file_count"] == 40,
        "all 3381 historical symbols represented": len(mapping) == 3381 and mapping.symbol.nunique() == 3381,
        "all four universes represented": set(outputs["historical_sector_coverage.csv"].universe) == set(config["universe_columns"]),
        "all viability thresholds represented": set(outputs["sector_viability_by_year.csv"].threshold) == {3, 5, 10},
        "conflicts unresolved": outputs["sector_mapping_conflicts.csv"].resolution.eq("UNRESOLVED").all(),
        "unmapped sectors remain null": mapping.loc[mapping.mapping_status.eq("UNMAPPED"), "sector"].isna().all(),
        "conflict sectors remain null": mapping.loc[mapping.mapping_status.eq("STATIC_CURRENT_CONFLICT"), "sector"].isna().all(),
        "no historically verified mappings claimed": not mapping.historically_verified.any(),
        "no effective-dated source claimed": not outputs["sector_source_inventory.csv"].has_effective_dates.astype(bool).any(),
        "no fuzzy identity key assigned": mapping.loc[mapping.identity_ambiguous, "canonical_identity"].isna().all(),
        "no factor or trading columns": not any(any(token in c.lower() for token in ("momentum", "return", "rank", "portfolio", "pnl")) for frame in outputs.values() for c in frame.columns),
    }
    return [{"check": key, "passed": bool(value)} for key, value in checks.items()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    config = load_config()
    accepted = verify_phase5(config)
    outputs, mapping, report, metadata = build(config)
    checks = acceptance_checks(outputs, mapping, metadata, config)
    if not all(item["passed"] for item in checks):
        raise AssertionError([item for item in checks if not item["passed"]])
    report_dir = local(config["report_dir"])
    report_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase6-staging-", dir=report_dir) as temporary:
        stage = Path(temporary)
        for name, frame in outputs.items():
            frame.to_csv(stage / name, index=False, float_format="%.12g")
        mapping.to_parquet(stage / "sector_research_mapping.parquet", index=False, compression="zstd")
        (stage / "phase6_sector_foundation.md").write_text(report)
        (stage / "phase6_acceptance.json").write_text(canonical_json(checks))
        names = list(outputs) + ["sector_research_mapping.parquet", "phase6_sector_foundation.md", "phase6_acceptance.json"]
        hashes = {name: sha256(stage / name) for name in names}
        key = {"accepted_input": accepted, "code_sha256": code_fingerprint(), "config": config,
               "source_files": metadata["source_files"], "output_sha256": hashes}
        build_id = hashlib.sha256(canonical_json(key).encode()).hexdigest()
        manifest_path = report_dir / "phase6_build_manifest.json"
        destinations = {name: report_dir / name for name in outputs}
        destinations.update({"sector_research_mapping.parquet": local(config["mapping_output"]),
                             "phase6_sector_foundation.md": local(config["final_report"]),
                             "phase6_acceptance.json": report_dir / "phase6_acceptance.json"})
        if args.verify_rebuild:
            prior = json.loads(manifest_path.read_text())
            if prior["build_id"] != build_id or prior["output_sha256"] != hashes:
                raise AssertionError("Phase-6 rebuild identity differs")
            for name, digest in hashes.items():
                if sha256(destinations[name]) != digest:
                    raise AssertionError(f"Phase-6 output differs: {name}")
            proof = {"build_id": build_id, "byte_identical": True, "output_count": len(hashes),
                     "command": ".venv/bin/python scripts/build_phase6_sector_foundation.py --verify-rebuild"}
            (report_dir / "phase6_rebuild_verification.json").write_text(canonical_json(proof))
            print(f"PASS deterministic Phase-6 rebuild: {len(hashes)} outputs; build {build_id}")
            return
        for name, destination in destinations.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage / name, destination)
        manifest = {**key, "build_id": build_id, "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    **{key: value for key, value in metadata.items() if key != "source_files"}}
        manifest_path.write_text(canonical_json(manifest))
        print(f"Built Phase 6: {metadata['historical_symbols']:,} historical symbols; {metadata['conflict_symbols']} conflicts")
        print(f"Historical-sector bias: {metadata['historical_sector_bias']}; decision: {metadata['decision']}")
        print(outputs["sector_research_tiers.csv"].to_string(index=False))


if __name__ == "__main__":
    main()
