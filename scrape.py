#!/usr/bin/env python3
"""Scrape papers from all sources and save raw results as JSON."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from scrapers import fetch_all


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"=== Scraping papers - {today} ===\n")

    all_papers = fetch_all(config)
    total = sum(len(v) for v in all_papers.values())
    print(f"\n[*] Total papers fetched: {total}")

    # Convert to serializable format
    output = {}
    for source, papers in all_papers.items():
        output[source] = [p.to_dict() for p in papers]

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"raw_{today}.json"
    out_file.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"[*] Saved to {out_file}")


if __name__ == "__main__":
    main()
