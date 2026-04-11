"""
Web search tools.
Uses Tavily when TAVILY_API_KEYS (or TAVILY_API_KEY) is set — rotates through
all keys automatically when one fails or exhausts credits.
Falls back to DuckDuckGo when all Tavily keys are unavailable.
"""
import os


def _get_tavily_keys() -> list[str]:
    """Return all configured Tavily keys in priority order."""
    # Multi-key comma-separated list takes precedence
    multi = os.getenv("TAVILY_API_KEYS", "").strip()
    if multi:
        return [k.strip() for k in multi.split(",") if k.strip()]
    # Single-key fallback
    single = os.getenv("TAVILY_API_KEY", "").strip()
    return [single] if single else []


def search_web(query: str, max_results: int = 5) -> str:
    """
    Search the web. Rotates through all Tavily keys on failure; falls back to DuckDuckGo.
    """
    for key in _get_tavily_keys():
        result = _search_tavily(query, max_results, key)
        if not result.startswith("Tavily error"):
            return result
    return _search_duckduckgo(query, max_results)


def search_tavily_raw(query: str, max_results: int = 5) -> list[dict]:
    """
    Return raw Tavily result list: [{title, url, content, score}, ...]
    Rotates through all configured keys. Returns [] if all fail or none configured.
    """
    for key in _get_tavily_keys():
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=key)
            resp   = client.search(query, max_results=max_results, include_raw_content=False)
            results = resp.get("results", [])
            if results:
                return results
        except Exception:
            continue   # try next key
    return []


def _search_tavily(query: str, max_results: int, api_key: str) -> str:
    try:
        from tavily import TavilyClient
        client  = TavilyClient(api_key=api_key)
        resp    = client.search(query, max_results=max_results)
        results = resp.get("results", [])
        if not results:
            return "No results found."

        lines = [f"[Tavily] {len(results)} results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   {r.get('url', '')}")
            snippet = r.get("content", "")[:250]
            if snippet:
                lines.append(f"   {snippet}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"Tavily error: {e}"


def _search_duckduckgo(query: str, max_results: int) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return "No results found."

        lines = [f"[DuckDuckGo] {len(results)} results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', 'No title')}")
            lines.append(f"   {r.get('href', '')}")
            lines.append(f"   {r.get('body', '')[:200]}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"Search failed: {e}"
