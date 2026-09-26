"""Preserve curated classifications without guessing missing/conflicting mappings."""

import csv
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd


def read_sectors(root: Path, symbols: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    memberships = defaultdict(set)
    issues = []
    for path in sorted(root.glob("*.csv")):
        sector, code = path.stem.rsplit("_", 1)
        seen = set()
        with path.open(newline="", encoding="utf-8-sig") as stream:
            for line, row in enumerate(csv.reader(stream), start=1):
                if not row or (len(row) == 1 and not row[0].strip()):
                    issues.append((path.name, line, "BLANK_RECORD", ""))
                    continue
                if len(row) != 1 or not re.fullmatch(r"[A-Z0-9&_\-]+", row[0].strip()):
                    raise ValueError(f"Malformed sector record: {path}:{line}")
                symbol = row[0].strip()
                if symbol in seen:
                    issues.append((path.name, line, "DUPLICATE_RECORD", symbol))
                seen.add(symbol)
                memberships[symbol].add((sector, code, path.name))
    rows = []
    for symbol in symbols:
        matches = sorted(memberships[symbol])
        status = "UNIQUE" if len(matches) == 1 else "UNMAPPED" if not matches else "CONFLICT"
        rows.append({"symbol": symbol, "sector": matches[0][0] if status == "UNIQUE" else None,
                     "sector_code": matches[0][1] if status == "UNIQUE" else None,
                     "sector_mapping_status": status,
                     "sector_source_files": "|".join(m[2] for m in matches),
                     "sector_candidates": "|".join(f"{m[0]}:{m[1]}" for m in matches),
                     "sector_basis": "current_curated_mapping_no_historical_effective_dates"})
    return pd.DataFrame(rows), pd.DataFrame(issues, columns=["source_file", "source_row", "issue", "symbol"])
