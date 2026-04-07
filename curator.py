"""Paper curation using Claude Code CLI (uses Max plan subscription)."""

from __future__ import annotations

import json
import subprocess
import sys

from scrapers import Paper


def build_prompt(all_papers: dict[str, list[Paper]], config: dict) -> str:
    """Build the curation prompt."""
    profile = config.get("research_profile", {})
    feedback = config.get("feedback", {})

    interests = "\n".join(f"  - {i}" for i in profile.get("interests", []))
    recent = "\n".join(f"  - {p}" for p in profile.get("recent_papers", []))
    prefer = "\n".join(f"  - {p}" for p in feedback.get("prefer", []))
    avoid = "\n".join(f"  - {a}" for a in feedback.get("avoid", []))
    extra = "\n".join(f"  - {k}" for k in feedback.get("extra_keywords", []))

    # Prepare paper data
    papers_text_parts = []
    for source, papers in all_papers.items():
        paper_dicts = [p.to_dict() for p in papers]
        papers_text_parts.append(
            f"## Source: {source} ({len(papers)} papers)\n"
            f"{json.dumps(paper_dicts, ensure_ascii=False, indent=1)}"
        )

    return f"""You are a paper recommendation assistant for an NLP researcher.

## Researcher Profile
- Lab: {profile.get('lab', 'NLP Lab')}
- Research Interests:
{interests}

- Recent Publications:
{recent}

## User Preferences
PRIORITIZE:
{prefer}

AVOID:
{avoid}

Additional keywords:
{extra}

## Task
From the papers below, select top 10 per source (arxiv, alphaxiv, huggingface) for recommendations,
and top 10 "hype" papers (agents, RLHF, reasoning, trending) regardless of direct relevance.

For recommended papers: include relevance_score (1-5), reason in Korean, related_area.
For hype papers: include reason in Korean, hype_topic.

Return ONLY valid JSON (no markdown fences) with this structure:
{{
  "recommended": [
    {{
      "paper_id": "2604.xxxxx",
      "title": "...",
      "source": "arxiv|alphaxiv|huggingface",
      "url": "...",
      "relevance_score": 5,
      "reason": "한국어로 추천 이유",
      "related_area": "RAG"
    }}
  ],
  "hype": [
    {{
      "paper_id": "2604.xxxxx",
      "title": "...",
      "source": "arxiv|alphaxiv|huggingface",
      "url": "...",
      "reason": "한국어로 주목 이유",
      "hype_topic": "LLM Agents"
    }}
  ]
}}

## Papers

{chr(10).join(papers_text_parts)}"""


def curate_papers(all_papers: dict[str, list[Paper]], config: dict) -> dict:
    """Use Claude Code CLI for curation (Max plan, no API key needed)."""
    prompt = build_prompt(all_papers, config)

    print("[*] Calling Claude Code CLI for curation...")
    print("    (Using your Max plan subscription)")

    try:
        # Pipe prompt via stdin to avoid argument length limits
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json", "--model", "sonnet", "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            print(f"[!] Claude CLI error: {result.stderr[:500]}")
            print(f"    stdout: {result.stdout[:500]}")
            sys.exit(1)

        # Parse CLI output - the JSON output format wraps the response
        cli_output = result.stdout.strip()

        # claude --output-format json returns {"result": "...", ...}
        try:
            cli_json = json.loads(cli_output)
            text = cli_json.get("result", cli_output)
        except json.JSONDecodeError:
            text = cli_output

        # Extract the recommendation JSON from the response text
        # Remove markdown code fences if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        # Try parsing as JSON
        try:
            curated = json.loads(text.strip())
        except json.JSONDecodeError:
            # Find JSON object boundaries
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                curated = json.loads(text[start:end])
            else:
                raise ValueError(f"Could not parse response as JSON:\n{text[:500]}")

        rec_count = len(curated.get("recommended", []))
        hype_count = len(curated.get("hype", []))
        print(f"    -> {rec_count} recommended, {hype_count} hype papers")
        return curated

    except subprocess.TimeoutExpired:
        print("[!] Claude CLI timed out (120s). Try again.")
        sys.exit(1)
    except FileNotFoundError:
        print("[!] 'claude' command not found. Make sure Claude Code CLI is installed.")
        print("    Install: npm install -g @anthropic-ai/claude-code")
        sys.exit(1)
