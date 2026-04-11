"""Semantic Scholar academic paper search — no API key required."""
import httpx
import urllib.parse

_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
_FIELDS = "title,authors,year,abstract,citationCount,externalIds,openAccessPdf"


def search_papers(query: str, limit: int = 5) -> str:
    """
    Search Semantic Scholar for academic papers.
    Returns title, authors, year, abstract snippet, citation count, and link.
    """
    try:
        params = {
            "query":  query,
            "limit":  min(limit, 10),
            "fields": _FIELDS,
        }
        r = httpx.get(_BASE, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        papers = data.get("data", [])

        if not papers:
            return f"No academic papers found for: {query}"

        lines = [f"[Semantic Scholar] {len(papers)} results for: {query}\n"]
        for i, p in enumerate(papers, 1):
            title    = p.get("title") or "Untitled"
            year     = p.get("year") or "n.d."
            authors  = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
            if len(p.get("authors") or []) > 3:
                authors += " et al."
            cites    = p.get("citationCount", 0)
            abstract = (p.get("abstract") or "No abstract available.")
            if len(abstract) > 300:
                abstract = abstract[:297] + "..."

            # Build URL
            ext = p.get("externalIds") or {}
            doi = ext.get("DOI")
            pid = p.get("paperId", "")
            url = f"https://doi.org/{doi}" if doi else f"https://www.semanticscholar.org/paper/{pid}"

            # Open access PDF
            pdf = (p.get("openAccessPdf") or {}).get("url", "")

            lines.append(f"{i}. {title} ({year})")
            if authors:
                lines.append(f"   Authors: {authors}")
            lines.append(f"   Citations: {cites}")
            lines.append(f"   {abstract}")
            lines.append(f"   {url}")
            if pdf:
                lines.append(f"   PDF: {pdf}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"Semantic Scholar error: {e}"
