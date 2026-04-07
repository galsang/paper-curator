#!/usr/bin/env python3
"""Paper Curator: Daily paper recommendations for NLP researchers."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from scrapers import fetch_all
from curator import curate_papers
from notifiers import format_markdown, send_slack, send_notion


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Daily Paper Curator")
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument("--dry-run", action="store_true", help="Fetch & curate but don't notify")
    parser.add_argument("--slack", action="store_true", help="Send to Slack")
    parser.add_argument("--notion", action="store_true", help="Send to Notion")
    parser.add_argument("--save", action="store_true", help="Save markdown to file")
    parser.add_argument("--output-dir", default="output", help="Output directory for saved files")
    args = parser.parse_args()

    # Load environment variables
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Load config
    config = load_config(args.config)
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"=== Paper Curator - {today} ===\n")

    # Step 1: Fetch papers from all sources
    all_papers = fetch_all(config)

    total = sum(len(v) for v in all_papers.values())
    if total == 0:
        print("[!] No papers fetched. Check your internet connection.")
        sys.exit(1)
    print(f"\n[*] Total papers fetched: {total}\n")

    # Step 2: Curate with Claude Code CLI (Max plan)
    curated = curate_papers(all_papers, config)

    # Step 3: Output
    markdown = format_markdown(curated, today)

    # Always print to stdout
    print("\n" + "=" * 60)
    print(markdown)
    print("=" * 60 + "\n")

    # Save to file
    if args.save or args.dry_run:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"papers_{today}.md"
        output_file.write_text(markdown)
        print(f"[*] Saved to {output_file}")

        # Also save raw JSON for reference
        json_file = output_dir / f"papers_{today}.json"
        json_file.write_text(json.dumps(curated, ensure_ascii=False, indent=2))
        print(f"[*] JSON saved to {json_file}")

    # Notify
    if not args.dry_run:
        if args.slack or config.get("notifications", {}).get("slack", {}).get("enabled"):
            send_slack(curated, today)

        if args.notion or config.get("notifications", {}).get("notion", {}).get("enabled"):
            send_notion(curated, today)

    print("\n[*] Done!")


if __name__ == "__main__":
    main()
