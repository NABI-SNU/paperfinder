from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

import argparse
import feedparser
import google.generativeai as genai

# === CONFIGURATION ===

# Example input
RSS_FEED_URLS = open("rsslist.txt", "r").readlines()
RSS_FEED_URLS = [url.strip() for url in RSS_FEED_URLS]
RESEARCH_KEYWORDS = open("keywordlist.txt", "r").readlines()
RESEARCH_KEYWORDS = [keyword.strip() for keyword in RESEARCH_KEYWORDS]
PREVIOUS_PAPER_TITLES = open("paperlist.txt", "r").readlines()
PREVIOUS_PAPER_TITLES = [title.strip() for title in PREVIOUS_PAPER_TITLES]

def fetch_recent_entries_single(feed_url: str, days_back: int = 30) -> List[dict]:
    """
    Return entries from a single RSS/Atom feed that were published within
    the last `days_back` days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    parsed = feedparser.parse(feed_url)

    recent: List[dict] = []
    for entry in parsed.entries:
        # pick whichever date field exists
        tt = getattr(entry, "published_parsed", None) or getattr(
            entry, "updated_parsed", None
        )
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
                "published_dt": published_dt,  # keep dt object for sorting
                "feed": feed_url,  # optional: track origin
            }
        )
    return recent

def fetch_recent_entries_multi(
    feed_urls: Iterable[str], days_back: int = 30, dedupe: bool = True
) -> List[dict]:
    """
    Collect recent entries from *all* feeds, sort descending by date,
    and return the combined list.
    """
    all_items: List[dict] = []
    for url in feed_urls:
        all_items.extend(fetch_recent_entries_single(url, days_back))

    # optional de-duplication (by link)
    if dedupe:
        seen = set()
        unique_items = []
        for item in all_items:
            if item["link"] not in seen:
                unique_items.append(item)
                seen.add(item["link"])
        all_items = unique_items

    # newest first
    all_items.sort(key=lambda d: d["published_dt"], reverse=True)
    return all_items


def score_papers(
    model: genai.GenerativeModel,
    entries: List[dict],
    keywords: List[str],
    previous_titles: List[str],
) -> List[str]:
    """Use Gemini to rank papers based on relevance."""
    prompt = f"""
You're an expert research assistant. Given a set of recent research papers, your task is to identify 3–5 papers that are likely to be of high interest, based on these research keywords and previously liked papers.

## Research Keywords:
{', '.join(keywords)}

## Previously Liked Papers:
{chr(10).join(f"- {title}" for title in previous_titles)}

## Recent Papers:
{chr(10).join(f"- Title: {entry['title']}\n  Abstract: {entry['summary']}" for entry in entries)}

List the top 3–5 papers most likely to be of interest. For each, briefly explain why it matches the interests.
Respond in bullet points. Each bullet should include the paper title and a brief rationale.
    """

    response = model.generate_content(prompt)
    return response.text.strip()


# === MAIN FUNCTION ===
def main(args):
    GEMINI_API_KEY = args.api_key
    genai.configure(api_key=GEMINI_API_KEY)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api_key", type=str, required=True)
    args = parser.parse_args()
    main(args)
