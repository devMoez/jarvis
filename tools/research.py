"""
Deep research tool.

Pipeline:
  1. Tavily finds the top N URLs with snippets
  2. Crawl4AI scrapes full content from each URL (falls back to httpx)
  3. Returns all raw content so the LLM can synthesize a report

The synthesis step is done by the orchestrator — this tool just gathers the content.
"""
import asyncio
import os
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from tools.search import search_tavily_raw


# ── Async helpers ─────────────────────────────────────────────────────────────
def _new_loop_run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception:
            pass


async def _crawl4ai_scrape(url: str) -> str:
    """Scrape a single URL with Crawl4AI. Returns markdown content."""
    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
            # Handle both old and new Crawl4AI API shapes
            md = getattr(result, "markdown", None)
            if md is not None:
                if hasattr(md, "fit_markdown"):
                    return (md.fit_markdown or md.raw_markdown or "")[:6000]
                return str(md)[:6000]
            return (getattr(result, "extracted_content", None) or "")[:6000]
    except Exception:
        return ""


def _httpx_scrape(url: str) -> str:
    """Lightweight httpx + BS4 fallback scraper."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            r = client.get(url, headers=headers)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text  = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]
        return "\n".join(lines)[:5000]
    except Exception:
        return ""


def _scrape_url(url: str) -> str:
    """Try Crawl4AI first; fall back to httpx scraper."""
    content = _new_loop_run(_crawl4ai_scrape(url))
    if content and len(content) > 200:
        return content
    return _httpx_scrape(url)


# ── Public tool ───────────────────────────────────────────────────────────────
def deep_research(topic: str, max_sources: int = 5) -> str:
    """
    Research a topic by finding top URLs via Tavily and scraping full content.
    Returns all gathered content so Jarvis can synthesize a complete report.

    Steps:
      1. Tavily search for top URLs
      2. Scrape each URL (Crawl4AI → httpx fallback)
      3. Return combined raw content with source labels
    """
    # Step 1 — find URLs
    raw_results = search_tavily_raw(topic, max_results=max_sources)

    if not raw_results:
        # Tavily not configured — fall back to DuckDuckGo search results only
        from tools.search import _search_duckduckgo
        return (
            f"[Research — Tavily not configured, showing web snippets only]\n\n"
            + _search_duckduckgo(topic, 5)
            + "\n\nNote: Install Tavily (TAVILY_API_KEY in .env) for full content scraping."
        )

    # Step 2 — scrape each URL
    sources: list[dict] = []
    for r in raw_results[:max_sources]:
        url     = r.get("url", "")
        title   = r.get("title", url)
        snippet = r.get("content", "")

        if not url:
            continue

        full_content = _scrape_url(url)
        sources.append({
            "title":   title,
            "url":     url,
            "snippet": snippet,
            "content": full_content or snippet,
        })

    if not sources:
        return f"Could not gather research content for: {topic}"

    # Step 3 — format for LLM synthesis
    lines = [
        f"[Research data for: {topic}]",
        f"[{len(sources)} sources scraped — synthesize into a complete report]\n",
    ]
    for i, s in enumerate(sources, 1):
        lines.append(f"--- SOURCE {i}: {s['title']} ---")
        lines.append(f"URL: {s['url']}")
        lines.append(s["content"][:4000])
        lines.append("")

    return "\n".join(lines)
