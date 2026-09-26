#!/usr/bin/env python3
"""Check actual artifacts against source snapshot; emit Phase-2 acceptance report."""

import argparse
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from mft_research.data.manifest import load_config, local_path
from mft_research.data.validation import validate_dataset, write_acceptance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/research_data.yaml")
    parser.add_argument("--pytest-xml")
    args = parser.parse_args()
    config = load_config(PROJECT, local_path(PROJECT, args.config))
    checks = validate_dataset(PROJECT, config)
    xml = local_path(PROJECT, args.pytest_xml) if args.pytest_xml else None
    print(write_acceptance(PROJECT, config, checks, xml))
    print("Acceptance report: reports/phase2_dataset_acceptance.md")


if __name__ == "__main__":
    main()
