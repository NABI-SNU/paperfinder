from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, List

from importlib.resources import files

import feedparser
import google.generativeai as genai


# === DATA LOADING ===

def _read_lines(filename: str) -> List[str]:
    data_path = files(__package__).joinpath("data").joinpath(filename)
    with data_path.open("r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


RSS_FEED_URLS = _read_lines("rsslist.txt")
RESEARCH_KEYWORDS = _read_lines("keywordlist.txt")
PREVIOUS_PAPER_TITLES = _read_lines("paperlist.txt")


# === FETCHING ===

def fetch_recent_entries_single(feed_url: str, days_back: int = 30) -> List[dict]:
    """Return entries from a single RSS/Atom feed published within ``days_back`` days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    parsed = feedparser.parse(feed_url)

    recent: List[dict] = []
    for entry in parsed.entries:
        tt = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if not tt:
            continue

        published_dt = datetime(*tt[:6], tzinfo=timezone.utc)
        if published_dt < cutoff:
            continue

        recent.append(
            {
                "title": entry.title,
                "summary": entry.summary,
                "link": entry.link,
                "published": published_dt.strftime("%Y-%m-%d"),
                "published_dt": published_dt,
                "feed": feed_url,
            }
        )
    return recent


def fetch_recent_entries_multi(feed_urls: Iterable[str], days_back: int = 30, *, dedupe: bool = True) -> List[dict]:
    """Collect recent entries from multiple feeds and sort newest first."""
    all_items: List[dict] = []
    for url in feed_urls:
        all_items.extend(fetch_recent_entries_single(url, days_back))

    if dedupe:
        seen = set()
        unique_items = []
        for item in all_items:
            if item["link"] not in seen:
                unique_items.append(item)
                seen.add(item["link"])
        all_items = unique_items

    all_items.sort(key=lambda d: d["published_dt"], reverse=True)
    return all_items


# === SCORING ===

def score_papers(
    model: genai.GenerativeModel,
    entries: List[dict],
    keywords: List[str],
    previous_titles: List[str],
) -> str:
    """Use Gemini to rank papers based on relevance."""
    recent_section = "\n".join(
        "- Title: {0}\n  Abstract: {1}".format(e["title"], e["summary"]) for e in entries
    )

    prompt = (
        "You're an expert research assistant. Given a set of recent research papers, "
        "your task is to identify 3–5 papers that are likely to be of high interest, "
        "based on these research keywords and previously liked papers.\n\n"
        "## Research Keywords:\n"
        f"{', '.join(keywords)}\n\n"
        "## Previously Liked Papers:\n"
        + "\n".join(f"- {title}" for title in previous_titles)
        + "\n\n## Recent Papers:\n"
        + recent_section
        + "\n\nList the top 3–5 papers most likely to be of interest. For each, briefly "
        "explain why it matches the interests.\nRespond in bullet points. Each "
        "bullet should include the paper title and a brief rationale."
    )

    response = model.generate_content(prompt)
    return response.text.strip()


# === CLI ENTRY ===

def run(api_key: str) -> None:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    print("Fetching recent papers...")
    entries = fetch_recent_entries_multi(RSS_FEED_URLS)

    if not entries:
        print("No recent entries found.")
        return

    print(f"Evaluating {len(entries)} papers using Gemini...")
    result = score_papers(model, entries, RESEARCH_KEYWORDS, PREVIOUS_PAPER_TITLES)

    print("\nTop Recommended Papers:\n")
    print(result)
