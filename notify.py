#!/usr/bin/env python3
"""Send pre-curated paper JSON to Slack and/or Notion."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from notifiers import format_markdown, send_slack, send_notion


def main():
    parser = argparse.ArgumentParser(description="Send curated papers to Slack/Notion")
    parser.add_argument("json_file", help="Path to curated papers JSON file")
    parser.add_argument("--slack", action="store_true")
    parser.add_argument("--notion", action="store_true")
    parser.add_argument("--date", default=None, help="Date string (default: today)")
    args = parser.parse_args()

    load_dotenv()

    with open(args.json_file) as f:
        curated = json.load(f)

    date = args.date or datetime.now().strftime("%Y-%m-%d")

    if args.slack:
        send_slack(curated, date)
    if args.notion:
        send_notion(curated, date)

    if not args.slack and not args.notion:
        print(format_markdown(curated, date))


if __name__ == "__main__":
    main()
