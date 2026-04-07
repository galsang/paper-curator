"""Notification handlers: Slack and Notion."""

from __future__ import annotations

import os
from datetime import datetime

import httpx
from notion_client import Client as NotionClient


def format_markdown(curated: dict, date: str) -> str:
    """Format curated papers as markdown."""
    lines = [f"# Paper Recommendations - {date}\n"]

    # Group recommended by source
    by_source = {}
    for paper in curated.get("recommended", []):
        src = paper.get("source", "unknown")
        by_source.setdefault(src, []).append(paper)

    source_labels = {
        "arxiv": "arxiv cs.CL/AI/LG",
        "alphaxiv": "alphaXiv (Community Trending)",
        "huggingface": "HuggingFace Papers",
    }

    for source in ["arxiv", "alphaxiv", "huggingface"]:
        papers = by_source.get(source, [])
        if not papers:
            continue
        label = source_labels.get(source, source)
        lines.append(f"\n## {label}\n")
        lines.append("| # | Paper | Area | Score | Why |")
        lines.append("|---|-------|------|-------|-----|")
        for i, p in enumerate(papers, 1):
            title = p.get("title", "")
            url = p.get("url", "")
            area = p.get("related_area", "")
            score = p.get("relevance_score", "")
            reason = p.get("reason", "")
            stars = "+" * int(score) if isinstance(score, (int, float)) else str(score)
            link = f"[{title}]({url})" if url else title
            lines.append(f"| {i} | {link} | {area} | {stars} | {reason} |")

    # Hype section
    hype = curated.get("hype", [])
    if hype:
        lines.append("\n## Hype & Trending\n")
        lines.append("| # | Paper | Topic | Why |")
        lines.append("|---|-------|-------|-----|")
        for i, p in enumerate(hype, 1):
            title = p.get("title", "")
            url = p.get("url", "")
            topic = p.get("hype_topic", "")
            reason = p.get("reason", "")
            link = f"[{title}]({url})" if url else title
            lines.append(f"| {i} | {link} | {topic} | {reason} |")

    return "\n".join(lines)


def format_slack_blocks(curated: dict, date: str) -> list[dict]:
    """Format curated papers as Slack Block Kit message."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Paper Recommendations - {date}"},
        },
        {"type": "divider"},
    ]

    by_source = {}
    for paper in curated.get("recommended", []):
        src = paper.get("source", "unknown")
        by_source.setdefault(src, []).append(paper)

    source_emoji = {"arxiv": ":page_facing_up:", "alphaxiv": ":fire:", "huggingface": ":hugging_face:"}
    source_labels = {
        "arxiv": "arxiv",
        "alphaxiv": "alphaXiv Trending",
        "huggingface": "HuggingFace Papers",
    }

    for source in ["arxiv", "alphaxiv", "huggingface"]:
        papers = by_source.get(source, [])
        if not papers:
            continue

        emoji = source_emoji.get(source, ":newspaper:")
        label = source_labels.get(source, source)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{label}*",
            },
        })

        paper_lines = []
        for i, p in enumerate(papers, 1):
            title = p.get("title", "")
            url = p.get("url", "")
            area = p.get("related_area", "")
            score = p.get("relevance_score", 0)
            reason = p.get("reason", "")
            stars = ":star:" * min(int(score), 5) if isinstance(score, (int, float)) else ""
            link = f"<{url}|{title}>" if url else title
            paper_lines.append(f"{i}. {link}\n    _{area}_ {stars} | {reason}")

        # Slack has 3000 char limit per text block, split if needed
        text = "\n".join(paper_lines)
        for chunk_start in range(0, len(text), 2900):
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text[chunk_start:chunk_start + 2900]},
            })
        blocks.append({"type": "divider"})

    # Hype section
    hype = curated.get("hype", [])
    if hype:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":rocket: *Hype & Trending*"},
        })
        hype_lines = []
        for i, p in enumerate(hype, 1):
            title = p.get("title", "")
            url = p.get("url", "")
            topic = p.get("hype_topic", "")
            reason = p.get("reason", "")
            link = f"<{url}|{title}>" if url else title
            hype_lines.append(f"{i}. {link}\n    `{topic}` | {reason}")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(hype_lines)},
        })

    return blocks


def send_slack(curated: dict, date: str, webhook_url: str | None = None) -> bool:
    """Send curated papers to Slack via webhook."""
    url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        print("[slack] No webhook URL configured. Skipping.")
        return False

    blocks = format_slack_blocks(curated, date)
    payload = {"blocks": blocks}

    try:
        resp = httpx.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        print(f"[slack] Message sent successfully.")
        return True
    except Exception as e:
        print(f"[slack] Error: {e}")
        return False


def send_notion(curated: dict, date: str) -> bool:
    """Create a Notion page with curated papers."""
    api_key = os.getenv("NOTION_API_KEY")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not api_key or not database_id:
        print("[notion] API key or database ID not configured. Skipping.")
        return False

    try:
        notion = NotionClient(auth=api_key)

        # Build page children (blocks)
        children = []

        by_source = {}
        for paper in curated.get("recommended", []):
            src = paper.get("source", "unknown")
            by_source.setdefault(src, []).append(paper)

        source_labels = {
            "arxiv": "arxiv cs.CL/AI/LG",
            "alphaxiv": "alphaXiv Trending",
            "huggingface": "HuggingFace Papers",
        }

        for source in ["arxiv", "alphaxiv", "huggingface"]:
            papers = by_source.get(source, [])
            if not papers:
                continue

            label = source_labels.get(source, source)
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": label}}],
                },
            })

            for i, p in enumerate(papers, 1):
                title = p.get("title", "")
                url = p.get("url", "")
                area = p.get("related_area", "")
                score = p.get("relevance_score", 0)
                reason = p.get("reason", "")

                text_content = f"{i}. [{area}] ({'*' * int(score)}) {reason}"
                block = {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": title, "link": {"url": url} if url else None},
                                "annotations": {"bold": True},
                            },
                            {
                                "type": "text",
                                "text": {"content": f"\n{text_content}"},
                            },
                        ],
                    },
                }
                children.append(block)

        # Hype section
        hype = curated.get("hype", [])
        if hype:
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Hype & Trending"}}],
                },
            })
            for i, p in enumerate(hype, 1):
                title = p.get("title", "")
                url = p.get("url", "")
                topic = p.get("hype_topic", "")
                reason = p.get("reason", "")
                children.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": title, "link": {"url": url} if url else None},
                                "annotations": {"bold": True},
                            },
                            {
                                "type": "text",
                                "text": {"content": f"\n[{topic}] {reason}"},
                            },
                        ],
                    },
                })

        # Discover the title property name dynamically
        title_prop_name = "Name"
        try:
            search_results = notion.search(query="")
            for r in search_results.get("results", []):
                rid = r.get("id", "").replace("-", "")
                if rid == database_id.replace("-", "") or r.get("object") in ("database", "data_source"):
                    for prop_name, prop_val in r.get("properties", {}).items():
                        if prop_val.get("type") == "title":
                            title_prop_name = prop_name
                            break
                    if title_prop_name != "Name":
                        break
        except Exception:
            pass

        print(f"    Using title property: {title_prop_name!r}")

        # Create the page
        notion.pages.create(
            parent={"database_id": database_id},
            properties={
                title_prop_name: {
                    "title": [
                        {"text": {"content": f"Paper Recommendations - {date}"}},
                    ],
                },
                "Date": {
                    "date": {"start": date},
                },
            },
            children=children[:100],  # Notion limit: 100 blocks per request
        )
        print(f"[notion] Page created successfully.")
        return True
    except Exception as e:
        print(f"[notion] Error: {e}")
        return False
