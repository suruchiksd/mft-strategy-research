"""Static-sector source audit and historical coverage diagnostics.

This module intentionally contains no sector-return, momentum, ranking, or
portfolio calculation.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


MAPPING_STATUSES = ("STATIC_CURRENT_UNIQUE", "STATIC_CURRENT_CONFLICT", "UNMAPPED")


def parse_sector_filename(path: Path) -> tuple[str, str]:
    """Parse the final underscore only, preserving underscores in sector names."""
    parts = path.stem.rsplit("_", 1)
    if len(parts) != 2 or not parts[0] or not re.fullmatch(r"[A-Z]{2}", parts[1]):
        raise ValueError(f"Invalid sector filename: {path.name}")
    return parts[0], parts[1]


def audit_sector_files(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, list[dict]]]:
    inventory: list[dict] = []
    issues: list[dict] = []
    memberships: dict[str, list[dict]] = defaultdict(list)
    for path in sorted(root.glob("*.csv")):
        sector, code = parse_sector_filename(path)
        seen: Counter[str] = Counter()
        raw_rows = 0
        blank_rows = 0
        malformed_rows = 0
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for line, row in enumerate(csv.reader(stream), start=1):
                raw_rows += 1
                if not row or (len(row) == 1 and not row[0].strip()):
                    blank_rows += 1
                    issues.append({"source_file": str(path), "source_row": line,
                                   "issue": "BLANK_RECORD", "symbol": "", "detail": "ignored"})
                    continue
                symbol = row[0].strip() if len(row) == 1 else ""
                if len(row) != 1 or not re.fullmatch(r"[A-Z0-9&_\-]+", symbol):
                    malformed_rows += 1
                    issues.append({"source_file": str(path), "source_row": line,
                                   "issue": "MALFORMED_RECORD", "symbol": symbol,
                                   "detail": repr(row)})
                    continue
                seen[symbol] += 1
                memberships[symbol].append({"sector": sector, "sector_code": code,
                                             "source_file": str(path), "source_row": line})
        for symbol, count in sorted(seen.items()):
            if count > 1:
                issues.append({"source_file": str(path), "source_row": "",
                               "issue": "DUPLICATE_SYMBOL", "symbol": symbol,
                               "detail": f"{count} rows; preserved in audit"})
        inventory.append({
            "record_kind": "CURATED_SECTOR_FILE", "path": str(path), "filename": path.name,
            "sector": sector, "sector_code": code, "row_count": raw_rows,
            "distinct_symbols": len(seen), "blank_rows": blank_rows,
            "duplicate_rows": sum(max(0, value - 1) for value in seen.values()),
            "malformed_rows": malformed_rows, "schema": "HEADERLESS_SINGLE_SYMBOL_COLUMN",
            "security_key": "NSE_SYMBOL", "has_effective_dates": False,
            "provenance": "manually_curated_current_static",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    conflict_rows = []
    for symbol, raw_matches in sorted(memberships.items()):
        matches = sorted({(x["sector"], x["sector_code"], x["source_file"]) for x in raw_matches})
        if len(matches) > 1:
            conflict_rows.append({"symbol": symbol, "assignment_count": len(matches),
                                  "sector_candidates": "|".join(f"{s}:{c}" for s, c, _ in matches),
                                  "source_files": "|".join(p for _, _, p in matches),
                                  "resolution": "UNRESOLVED"})
    return (pd.DataFrame(inventory),
            pd.DataFrame(issues, columns=["source_file", "source_row", "issue", "symbol", "detail"]),
            pd.DataFrame(conflict_rows), memberships)


def _csv_header_and_rows(path: Path) -> tuple[str, int]:
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, [])
        return "|".join(value.strip() for value in header), sum(1 for _ in reader)


def alternative_source_inventory(config: dict) -> pd.DataFrame:
    """Record local classification candidates and derived uses without treating them as history."""
    roots = {key: Path(config[key]) for key in
             ("bhavcopy_universe_root", "bhavcopy_archive_root", "market_data_platform_root")}
    rows: list[dict] = []
    n50 = [roots["bhavcopy_archive_root"] / "nifty_50_with_sectors.csv",
           roots["market_data_platform_root"] / "data/reference/nifty_50_with_sectors.csv"]
    for path in n50:
        header, count = _csv_header_and_rows(path)
        rows.append({"record_kind": "ALTERNATIVE_STATIC_MAPPING", "path": str(path),
                     "filename": path.name, "sector": "", "sector_code": "", "row_count": count,
                     "distinct_symbols": count, "blank_rows": 0, "duplicate_rows": 0,
                     "malformed_rows": 0, "schema": header, "security_key": "stocks_name_symbol",
                     "has_effective_dates": False, "provenance": "current_nifty50_static_unknown_origin",
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    universe_root = roots["bhavcopy_universe_root"]
    derived = sorted(path for path in universe_root.glob("*.csv")
                     if any(token in path.name for token in ("ranked_universe", "top5_", "top10_", "top20_", "trade_plan")))
    families: dict[str, list[Path]] = defaultdict(list)
    for path in derived:
        family = re.sub(r"_\d{8}", "_<DATE>", path.name)
        family = family.replace("_latest", "_<LATEST>")
        families[family].append(path)
    for family, paths in sorted(families.items()):
        header, count = _csv_header_and_rows(paths[-1])
        if "SECTOR" not in header.upper():
            continue
        rows.append({"record_kind": "DERIVED_STATIC_LABEL_OUTPUT_FAMILY",
                     "path": "|".join(str(path) for path in paths), "filename": family,
                     "sector": "", "sector_code": "", "row_count": count,
                     "distinct_symbols": "", "blank_rows": "", "duplicate_rows": "",
                     "malformed_rows": "", "schema": header, "security_key": "TckrSymb",
                     "has_effective_dates": False,
                     "provenance": f"{len(paths)} derived snapshots; labels loaded from curated sector CSVs",
                     "sha256": ""})
    analytical = universe_root / "research_sector_performance.csv"
    header, count = _csv_header_and_rows(analytical)
    rows.append({"record_kind": "DERIVED_AGGREGATE_NOT_MAPPING", "path": str(analytical),
                 "filename": analytical.name, "sector": "", "sector_code": "", "row_count": count,
                 "distinct_symbols": "", "blank_rows": "", "duplicate_rows": "", "malformed_rows": "",
                 "schema": header, "security_key": "none_sector_aggregate",
                 "has_effective_dates": False, "provenance": "analysis derived from curated files",
                 "sha256": hashlib.sha256(analytical.read_bytes()).hexdigest()})
    rows.append({"record_kind": "ACCEPTED_IDENTITY_AUXILIARY", "path": config["historical_daily"],
                 "filename": Path(config["historical_daily"]).name, "sector": "", "sector_code": "",
                 "row_count": 3062267, "distinct_symbols": 3381, "blank_rows": "", "duplicate_rows": 0,
                 "malformed_rows": "", "schema": "symbol|date|ISIN(new-format only)|security_name(new-format only)",
                 "security_key": "exact_observed_symbol; partial_ISIN_from_2024-07-08",
                 "has_effective_dates": False,
                 "provenance": "accepted Phase-5 Bhavcopy-derived identity evidence; no classification fields",
                 "sha256": "verified_through_phase5_manifest"})
    return pd.DataFrame(rows)


def build_mapping(symbols: pd.DataFrame, memberships: dict[str, list[dict]]) -> pd.DataFrame:
    rows = []
    for item in symbols.sort_values("symbol", kind="stable").itertuples(index=False):
        raw = memberships.get(item.symbol, [])
        matches = sorted({(x["sector"], x["sector_code"], x["source_file"]) for x in raw})
        status = "STATIC_CURRENT_UNIQUE" if len(matches) == 1 else "STATIC_CURRENT_CONFLICT" if matches else "UNMAPPED"
        ambiguous = bool(item.identity_ambiguity)
        historical = ("IDENTITY_AMBIGUOUS" if ambiguous else
                      "STATIC_CURRENT_UNIQUE_NOT_EFFECTIVE_DATED" if status == "STATIC_CURRENT_UNIQUE" else status)
        rows.append({"symbol": item.symbol, "observed_symbol": item.symbol,
                     "canonical_identity": pd.NA if ambiguous else item.symbol,
                     "sector": matches[0][0] if status == "STATIC_CURRENT_UNIQUE" else pd.NA,
                     "sector_code": matches[0][1] if status == "STATIC_CURRENT_UNIQUE" else pd.NA,
                     "mapping_status": status,
                     "mapping_source": "|".join(match[2] for match in matches),
                     "sector_candidates": "|".join(f"{s}:{c}" for s, c, _ in matches),
                     "identity_status": item.continuity_status,
                     "identity_ambiguous": ambiguous,
                     "historical_validity_status": historical,
                     "historically_verified": False,
                     "first_observed_date": pd.to_datetime(item.first_date).date(),
                     "last_observed_date": pd.to_datetime(item.last_date).date()})
    return pd.DataFrame(rows)


def mapping_summary(inventory: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    curated = inventory[inventory.record_kind.eq("CURATED_SECTOR_FILE")]
    rows = []
    for item in curated.itertuples(index=False):
        part = mapping[mapping.sector_code.eq(item.sector_code)]
        conflicts = mapping.mapping_status.eq("STATIC_CURRENT_CONFLICT") & mapping.sector_candidates.fillna("").str.contains(f":{item.sector_code}", regex=False)
        rows.append({"sector": item.sector, "sector_code": item.sector_code, "source_file": item.path,
                     "source_rows": item.row_count, "source_distinct_symbols": item.distinct_symbols,
                     "source_duplicate_rows": item.duplicate_rows,
                     "historical_unique_symbols": part.symbol.nunique(),
                     "historical_stable_identity_symbols": part.loc[~part.identity_ambiguous, "symbol"].nunique(),
                     "historical_conflict_symbols_involving_sector": mapping.loc[conflicts, "symbol"].nunique()})
    return pd.DataFrame(rows)


def _describe(values: pd.Series, prefix: str = "") -> dict:
    if values.empty:
        return {f"{prefix}min": np.nan, f"{prefix}p10": np.nan, f"{prefix}p25": np.nan,
                f"{prefix}median": np.nan, f"{prefix}mean": np.nan, f"{prefix}p75": np.nan,
                f"{prefix}p90": np.nan, f"{prefix}max": np.nan}
    return {f"{prefix}min": values.min(), f"{prefix}p10": values.quantile(.10),
            f"{prefix}p25": values.quantile(.25), f"{prefix}median": values.median(),
            f"{prefix}mean": values.mean(), f"{prefix}p75": values.quantile(.75),
            f"{prefix}p90": values.quantile(.90), f"{prefix}max": values.max()}


def historical_coverage(daily: pd.DataFrame, mapping: pd.DataFrame, universe_columns: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = daily.merge(mapping, on="symbol", how="left", validate="many_to_one")
    work["year"] = pd.to_datetime(work.date).dt.year
    work["usable_mapping"] = work.mapping_status.eq("STATIC_CURRENT_UNIQUE") & ~work.identity_ambiguous
    coverage_rows: list[dict] = []
    size_frames: list[pd.DataFrame] = []
    validity_rows: list[dict] = []
    for universe, column in universe_columns.items():
        eligible = work[work[column].fillna(False)].copy()
        for year, group in eligible.groupby("year", sort=True):
            symbols = group.drop_duplicates("symbol")
            unique = symbols.mapping_status.eq("STATIC_CURRENT_UNIQUE")
            usable = unique & ~symbols.identity_ambiguous
            conflict = symbols.mapping_status.eq("STATIC_CURRENT_CONFLICT")
            unmapped = symbols.mapping_status.eq("UNMAPPED")
            obs_unique = group.mapping_status.eq("STATIC_CURRENT_UNIQUE")
            obs_usable = obs_unique & ~group.identity_ambiguous
            sector_symbol_counts = symbols.loc[usable].groupby(["sector", "sector_code"]).size()
            coverage_rows.append({"year": year, "universe": universe,
                "eligible_symbols": len(symbols), "eligible_observations": len(group),
                "uniquely_mapped_symbols": int(unique.sum()), "conflicted_symbols": int(conflict.sum()),
                "unmapped_symbols": int(unmapped.sum()), "ambiguous_identity_symbols": int(symbols.identity_ambiguous.sum()),
                "usable_mapping_symbols": int(usable.sum()), "unique_mapping_pct": 100 * unique.mean(),
                "usable_mapping_pct": 100 * usable.mean(), "unique_mapping_observations": int(obs_unique.sum()),
                "usable_mapping_observations": int(obs_usable.sum()),
                "usable_observation_pct": 100 * obs_usable.mean(),
                "represented_sectors": int(sector_symbol_counts.size), **_describe(sector_symbol_counts, "annual_symbol_")})
            for status, sub in group.groupby("historical_validity_status", dropna=False, sort=True):
                validity_rows.append({"year": year, "universe": universe, "historical_validity_status": status,
                                      "symbols": sub.symbol.nunique(), "observations": len(sub),
                                      "observation_pct": 100 * len(sub) / len(group),
                                      "historically_verified": status == "HISTORICALLY_VERIFIED"})
        usable_daily = eligible[eligible.usable_mapping]
        if len(usable_daily):
            sizes = (usable_daily.groupby(["date", "year", "sector", "sector_code"], sort=True).size()
                     .rename("stock_count").reset_index())
            sizes.insert(0, "universe", universe)
            for threshold in (3, 5, 10):
                sizes[f"at_least_{threshold}"] = sizes.stock_count.ge(threshold)
            size_frames.append(sizes)
    sizes = pd.concat(size_frames, ignore_index=True).sort_values(["universe", "date", "sector_code"], kind="stable")
    viability_rows = []
    for (universe, year), group in sizes.groupby(["universe", "year"], sort=True):
        dates = group.date.nunique()
        for threshold in (3, 5, 10):
            retained = group.stock_count.ge(threshold)
            per_date = group.loc[retained].groupby("date").size().reindex(sorted(group.date.unique()), fill_value=0)
            total_symbol_obs = group.stock_count.sum()
            kept_symbol_obs = group.loc[retained, "stock_count"].sum()
            viability_rows.append({"year": year, "universe": universe, "threshold": threshold,
                "dates": dates, "sector_date_observations": len(group),
                "retained_sector_date_observations": int(retained.sum()),
                "sector_date_retained_pct": 100 * retained.mean(),
                "mapped_symbol_date_observations": int(total_symbol_obs),
                "retained_symbol_date_observations": int(kept_symbol_obs),
                "excluded_symbol_date_observations_small_sector": int(total_symbol_obs - kept_symbol_obs),
                "symbol_observation_retained_pct": 100 * kept_symbol_obs / total_symbol_obs,
                "mean_usable_sectors_per_date": per_date.mean(), "median_usable_sectors_per_date": per_date.median(),
                "min_usable_sectors_per_date": per_date.min(), "max_usable_sectors_per_date": per_date.max()})
    return (pd.DataFrame(coverage_rows), sizes, pd.DataFrame(viability_rows),
            pd.DataFrame(validity_rows))


def concentration(sizes: pd.DataFrame) -> pd.DataFrame:
    daily_rows = []
    for (universe, date), group in sizes.groupby(["universe", "date"], sort=True):
        counts = group.stock_count.sort_values(ascending=False)
        total = counts.sum()
        daily_rows.append({"universe": universe, "date": date, "year": pd.Timestamp(date).year,
                           "largest_sector_share_pct": 100 * counts.iloc[0] / total,
                           "top3_sector_share_pct": 100 * counts.iloc[:3].sum() / total,
                           "singleton_sectors": int(counts.eq(1).sum()), "sectors_lt3": int(counts.lt(3).sum()),
                           "sectors_lt5": int(counts.lt(5).sum()), "sectors_ge10": int(counts.ge(10).sum()),
                           "represented_sectors": len(counts)})
    daily = pd.DataFrame(daily_rows)
    return (daily.groupby(["year", "universe"], sort=True).agg(
        dates=("date", "nunique"), median_largest_sector_share_pct=("largest_sector_share_pct", "median"),
        mean_largest_sector_share_pct=("largest_sector_share_pct", "mean"),
        max_largest_sector_share_pct=("largest_sector_share_pct", "max"),
        median_top3_sector_share_pct=("top3_sector_share_pct", "median"),
        median_singleton_sectors=("singleton_sectors", "median"),
        median_sectors_lt3=("sectors_lt3", "median"), median_sectors_lt5=("sectors_lt5", "median"),
        median_sectors_ge10=("sectors_ge10", "median"),
        median_represented_sectors=("represented_sectors", "median")).reset_index())


def tier_summary(daily: pd.DataFrame, mapping: pd.DataFrame, sizes: pd.DataFrame, config: dict) -> pd.DataFrame:
    merged = daily.merge(mapping, on="symbol", how="left", validate="many_to_one")
    rows = []
    for tier, spec in config["research_tiers"].items():
        mask = merged[config["universe_columns"][spec["universe"]]].fillna(False)
        if spec["require_unique_mapping"]:
            mask &= merged.mapping_status.eq("STATIC_CURRENT_UNIQUE")
        if spec["require_stable_identity"]:
            mask &= ~merged.identity_ambiguous
        part = merged[mask]
        counts = part.groupby(["date", "sector", "sector_code"]).size() if len(part) else pd.Series(dtype=float)
        rows.append({"tier": tier, "role": spec["role"], "universe": spec["universe"],
                     "require_unique_mapping": spec["require_unique_mapping"],
                     "require_stable_identity": spec["require_stable_identity"],
                     "symbols": part.symbol.nunique(), "historical_observations": len(part),
                     "observation_pct_of_universe": 100 * len(part) / max(1, int(merged[config["universe_columns"][spec["universe"]]].sum())),
                     "sector_count": part.sector.nunique(), "median_stocks_per_sector_date": counts.median() if len(counts) else np.nan,
                     "sector_date_pct_ge3": 100 * counts.ge(3).mean() if len(counts) else np.nan,
                     "sector_date_pct_ge5": 100 * counts.ge(5).mean() if len(counts) else np.nan,
                     "sector_date_pct_ge10": 100 * counts.ge(10).mean() if len(counts) else np.nan,
                     "known_bias": "STATIC_CURRENT_CLASSIFICATION_NO_EFFECTIVE_DATES",
                     "recommended_primary": tier == config["recommended_primary_tier"]})
    return pd.DataFrame(rows)


def historical_bias_label(validity: pd.DataFrame) -> str:
    total = validity.observations.sum()
    verified = validity.loc[validity.historically_verified, "observations"].sum()
    pct = 100 * verified / total if total else 0
    return "SEVERE" if pct < 25 else "MATERIAL" if pct < 60 else "MODERATE" if pct < 90 else "LOW"

