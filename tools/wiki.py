"""Wikipedia lookup — no API key needed."""
import urllib.parse
import httpx


def wiki_search(topic: str) -> str:
    """Return Wikipedia summary + key facts for a topic."""
    topic_enc = urllib.parse.quote(topic)
    try:
        # Step 1: search for best matching page title
        search_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={topic_enc}"
            "&format=json&srlimit=1"
        )
        r = httpx.get(search_url, timeout=10)
        r.raise_for_status()
        hits = r.json().get("query", {}).get("search", [])
        if not hits:
            return f"No Wikipedia article found for: {topic}"
        title = hits[0]["title"]

        # Step 2: fetch the intro extract
        title_enc = urllib.parse.quote(title)
        extract_url = (
            "https://en.wikipedia.org/w/api.php"
            f"?action=query&titles={title_enc}"
            "&prop=extracts&exintro=true&explaintext=true"
            "&format=json&redirects=1"
        )
        r2 = httpx.get(extract_url, timeout=10)
        r2.raise_for_status()
        pages = r2.json().get("query", {}).get("pages", {})
        page  = next(iter(pages.values()))
        extract = (page.get("extract") or "").strip()
        if not extract:
            return f"Wikipedia has no summary for: {title}"

        # Trim to first ~1500 chars for terminal readability
        if len(extract) > 1500:
            extract = extract[:1497] + "..."
        url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
        return f"[Wikipedia] {title}\n{url}\n\n{extract}"

    except Exception as e:
        return f"Wikipedia error: {e}"
