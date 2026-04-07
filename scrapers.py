"""Paper scrapers for arxiv, alphaXiv, and HuggingFace Papers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

import feedparser
import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
HTTP_CLIENT_KWARGS = {"timeout": 30, "follow_redirects": True, "headers": HEADERS}


@dataclass
class Paper:
    title: str
    paper_id: str
    source: str  # "arxiv", "alphaxiv", "huggingface"
    url: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    categories: list[str] = field(default_factory=list)
    votes: int = 0
    comments: int = 0
    visits: int = 0
    published: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "paper_id": self.paper_id,
            "source": self.source,
            "url": self.url,
            "authors": self.authors[:3],
            "abstract": self.abstract[:200] if self.abstract else "",
            "categories": self.categories[:3],
            "votes": self.votes,
            "visits": self.visits,
        }


def fetch_arxiv(categories: list[str], max_per_category: int = 50) -> list[Paper]:
    """Fetch recent papers from arxiv via Atom feed API."""
    papers = []
    seen_ids = set()

    for cat in categories:
        url = (
            f"http://export.arxiv.org/api/query?"
            f"search_query=cat:{cat}&start=0&max_results={max_per_category}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )
        try:
            # Fetch via httpx with headers, then parse
            resp = httpx.get(url, **HTTP_CLIENT_KWARGS)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                arxiv_id = entry.id.split("/abs/")[-1]
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)

                authors = [a.get("name", "") for a in entry.get("authors", [])]
                categories_list = [t["term"] for t in entry.get("tags", [])]

                papers.append(Paper(
                    title=entry.title.replace("\n", " ").strip(),
                    paper_id=arxiv_id,
                    source="arxiv",
                    url=f"https://arxiv.org/abs/{arxiv_id}",
                    authors=authors[:5],
                    abstract=entry.summary.replace("\n", " ").strip(),
                    categories=categories_list,
                    published=entry.get("published", ""),
                ))
        except Exception as e:
            print(f"[arxiv] Error fetching {cat}: {e}")

    return papers


def fetch_alphaxiv() -> list[Paper]:
    """Scrape trending papers from alphaXiv."""
    papers = []
    url = "https://www.alphaxiv.org/"

    try:
        resp = httpx.get(url, **HTTP_CLIENT_KWARGS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find paper cards/entries
        for article in soup.select("article, [class*='paper'], [class*='card']"):
            title_el = article.select_one("h2, h3, [class*='title']")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title or len(title) < 10:
                continue

            # Extract link
            link_el = article.select_one("a[href*='arxiv'], a[href*='alphaxiv']")
            paper_url = link_el["href"] if link_el else ""
            paper_id = ""
            if paper_url:
                match = re.search(r"(\d{4}\.\d{4,5})", paper_url)
                if match:
                    paper_id = match.group(1)

            # Extract metrics
            text = article.get_text()
            votes = 0
            visits = 0
            vote_match = re.search(r"(\d[\d,]*)\s*(?:vote|upvote)", text, re.I)
            if vote_match:
                votes = int(vote_match.group(1).replace(",", ""))
            visit_match = re.search(r"(\d[\d,]*)\s*(?:visit|view)", text, re.I)
            if visit_match:
                visits = int(visit_match.group(1).replace(",", ""))

            papers.append(Paper(
                title=title,
                paper_id=paper_id,
                source="alphaxiv",
                url=paper_url or f"https://www.alphaxiv.org/",
                votes=votes,
                visits=visits,
            ))
    except Exception as e:
        print(f"[alphaxiv] Error: {e}")

    # Fallback: if scraping fails, try a simpler approach
    if not papers:
        papers = _fetch_alphaxiv_fallback()

    return papers


def _fetch_alphaxiv_fallback() -> list[Paper]:
    """Fallback scraper for alphaXiv using broader selectors."""
    papers = []
    try:
        resp = httpx.get(
            "https://www.alphaxiv.org/explore",
            **HTTP_CLIENT_KWARGS,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for link in soup.select("a[href*='/abs/']"):
            title = link.get_text(strip=True)
            if title and len(title) > 15:
                href = link["href"]
                match = re.search(r"(\d{4}\.\d{4,5})", href)
                paper_id = match.group(1) if match else ""
                papers.append(Paper(
                    title=title,
                    paper_id=paper_id,
                    source="alphaxiv",
                    url=f"https://arxiv.org/abs/{paper_id}" if paper_id else href,
                ))
    except Exception as e:
        print(f"[alphaxiv fallback] Error: {e}")
    return papers


def fetch_huggingface(days: int = 3) -> list[Paper]:
    """Fetch trending papers from HuggingFace via API."""
    papers = []
    seen_ids = set()

    today = datetime.now()
    dates = [(today.replace(day=today.day - i)).strftime("%Y-%m-%d") for i in range(days)]

    for date in dates:
        # Try the API endpoint first (more reliable than scraping)
        api_url = f"https://huggingface.co/api/daily_papers?date={date}"
        try:
            resp = httpx.get(api_url, **HTTP_CLIENT_KWARGS)
            resp.raise_for_status()
            data = resp.json()

            for item in data:
                paper = item.get("paper", {})
                paper_id = paper.get("id", "")
                title = paper.get("title", "")

                if not paper_id or paper_id in seen_ids:
                    continue
                seen_ids.add(paper_id)

                authors = [a.get("name", "") for a in paper.get("authors", [])]
                votes = item.get("numUpvotes", 0)
                comments = item.get("numComments", 0)

                papers.append(Paper(
                    title=title,
                    paper_id=paper_id,
                    source="huggingface",
                    url=f"https://huggingface.co/papers/{paper_id}",
                    authors=authors[:5],
                    abstract=paper.get("summary", "")[:200],
                    votes=votes,
                    comments=comments,
                    published=date,
                ))
            continue
        except Exception:
            pass

        # Fallback: scrape the HTML page
        url = f"https://huggingface.co/papers?date={date}"
        try:
            resp = httpx.get(url, **HTTP_CLIENT_KWARGS)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for article in soup.select("article, [class*='paper']"):
                title_el = article.select_one("h3, h2, [class*='title']")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                if not title or len(title) < 10:
                    continue

                link_el = article.select_one("a[href*='/papers/']")
                paper_url = ""
                paper_id = ""
                if link_el:
                    href = link_el.get("href", "")
                    match = re.search(r"(\d{4}\.\d{4,5})", href)
                    if match:
                        paper_id = match.group(1)
                        paper_url = f"https://huggingface.co/papers/{paper_id}"

                if paper_id in seen_ids:
                    continue
                seen_ids.add(paper_id)

                # Extract vote count
                votes = 0
                vote_el = article.select_one("[class*='vote'], [class*='like']")
                if vote_el:
                    vote_text = vote_el.get_text(strip=True)
                    nums = re.findall(r"\d[\d,]*", vote_text)
                    if nums:
                        votes = int(nums[0].replace(",", ""))

                papers.append(Paper(
                    title=title,
                    paper_id=paper_id,
                    source="huggingface",
                    url=paper_url,
                    votes=votes,
                    published=date,
                ))
        except Exception as e:
            print(f"[huggingface] Error for {date}: {e}")

    return papers


def fetch_all(config: dict) -> dict[str, list[Paper]]:
    """Fetch papers from all sources."""
    arxiv_cfg = config.get("sources", {}).get("arxiv", {})
    categories = arxiv_cfg.get("categories", ["cs.CL"])
    max_per_cat = arxiv_cfg.get("max_papers_per_category", 50)

    print("[*] Fetching arxiv papers...")
    arxiv_papers = fetch_arxiv(categories, max_per_cat)
    print(f"    -> {len(arxiv_papers)} papers")

    print("[*] Fetching alphaXiv papers...")
    alphaxiv_papers = fetch_alphaxiv()
    print(f"    -> {len(alphaxiv_papers)} papers")

    print("[*] Fetching HuggingFace papers...")
    hf_papers = fetch_huggingface(days=3)
    print(f"    -> {len(hf_papers)} papers")

    return {
        "arxiv": arxiv_papers,
        "alphaxiv": alphaxiv_papers,
        "huggingface": hf_papers,
    }
