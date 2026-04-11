"""
Book & file finder.

Sources (in order):
  1. Library Genesis  — libgen.is JSON + search API
  2. Anna's Archive   — scrapes search results as fallback
  3. Open Library     — metadata fallback (no download links)

Auto-download: if a direct file URL is found, downloads to ./downloads/
"""
import os
import re
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

_DOWNLOADS = Path("downloads")
_HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_TIMEOUT = 15


# ── LibGen ────────────────────────────────────────────────────────────────────
def _libgen_search(query: str, max_results: int = 5) -> list[dict]:
    """Search LibGen and return book metadata with MD5 hashes."""
    url = (
        f"https://libgen.is/search.php"
        f"?req={quote_plus(query)}&res={max_results}&view=simple&phrase=1&column=def"
    )
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS) as client:
            r = client.get(url)
            r.raise_for_status()
    except Exception:
        # Try mirror
        try:
            url2 = url.replace("libgen.is", "libgen.rs")
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS) as client:
                r = client.get(url2)
                r.raise_for_status()
        except Exception:
            return []

    soup  = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", {"id": "pc"}) or soup.find("table", class_="c")
    if not table:
        return []

    books = []
    rows  = table.find_all("tr")[1:]   # skip header
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 9:
            continue
        try:
            # Column layout: id, author, title, publisher, year, pages, language, size, extension, mirror1, mirror2...
            book_id    = cells[0].get_text(strip=True)
            authors    = cells[1].get_text(strip=True)[:80]
            title_cell = cells[2]
            title      = title_cell.get_text(strip=True)[:120]
            # MD5 is in the title link href: /book/index.php?md5=<hash>
            md5_link   = title_cell.find("a", href=re.compile(r"md5=", re.I))
            md5        = ""
            if md5_link:
                m = re.search(r"md5=([a-fA-F0-9]+)", md5_link["href"])
                md5 = m.group(1) if m else ""
            year  = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            lang  = cells[6].get_text(strip=True) if len(cells) > 6 else ""
            size  = cells[7].get_text(strip=True) if len(cells) > 7 else ""
            ext   = cells[8].get_text(strip=True) if len(cells) > 8 else ""

            if title and (md5 or book_id):
                books.append({
                    "id":      book_id,
                    "md5":     md5,
                    "title":   title,
                    "authors": authors,
                    "year":    year,
                    "lang":    lang,
                    "size":    size,
                    "ext":     ext,
                })
        except Exception:
            continue

    return books


def _libgen_download_url(md5: str) -> str:
    """Get the direct download link from the LibGen book page."""
    page_url = f"https://library.lol/main/{md5}"
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS) as client:
            r = client.get(page_url)
            r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # The download link is in an <a> tag with text "GET" or "Cloudflare"
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "get.php" in href or "cloudflare-ipfs" in href or href.endswith((".pdf", ".epub", ".djvu", ".fb2", ".mobi")):
                return href if href.startswith("http") else urljoin(page_url, href)
        # Fallback: look for any link on the page that has a file extension
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r"\.(pdf|epub|djvu|fb2|mobi|azw3)(\?|$)", href, re.I):
                return href if href.startswith("http") else urljoin(page_url, href)
    except Exception:
        pass
    return f"https://library.lol/main/{md5}"


# ── Anna's Archive (fallback) ─────────────────────────────────────────────────
def _annas_search(query: str, max_results: int = 5) -> list[dict]:
    """Scrape Anna's Archive search results."""
    url = f"https://annas-archive.org/search?q={quote_plus(query)}"
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS) as client:
            r = client.get(url)
            r.raise_for_status()
    except Exception:
        return []

    soup    = BeautifulSoup(r.text, "html.parser")
    results = []
    # Anna's Archive uses a specific layout — find book result cards
    for card in soup.select("div.h-[125px], div[class*='result']")[:max_results]:
        try:
            title_el = card.find("h3") or card.find("div", class_=re.compile("title", re.I))
            link_el  = card.find("a", href=True)
            title    = title_el.get_text(strip=True) if title_el else ""
            link     = link_el["href"] if link_el else ""
            if link and not link.startswith("http"):
                link = "https://annas-archive.org" + link
            if title or link:
                results.append({"title": title, "url": link, "source": "anna"})
        except Exception:
            continue

    # Simpler fallback: grab any links to /md5/ pages
    if not results:
        for a in soup.find_all("a", href=re.compile(r"/md5/"))[:max_results]:
            href = a["href"]
            if not href.startswith("http"):
                href = "https://annas-archive.org" + href
            results.append({
                "title":  a.get_text(strip=True)[:100],
                "url":    href,
                "source": "anna",
            })

    return results


# ── Downloader ────────────────────────────────────────────────────────────────
def _download_file(url: str, filename: str) -> str:
    """Download a file to ./downloads/<filename>. Returns path or error."""
    _DOWNLOADS.mkdir(parents=True, exist_ok=True)
    dest = _DOWNLOADS / filename
    try:
        with httpx.Client(timeout=60, follow_redirects=True, headers=_HEADERS) as client:
            with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=32768):
                        f.write(chunk)
        return str(dest)
    except Exception as e:
        return f"Download failed: {e}"


def _safe_filename(title: str, ext: str) -> str:
    safe = re.sub(r'[\\/*?:"<>|]', "", title)[:80].strip()
    if ext and not ext.startswith("."):
        ext = "." + ext
    return safe + (ext or ".pdf")


# ── Public tool ───────────────────────────────────────────────────────────────
def find_book(query: str, auto_download: bool = True) -> str:
    """
    Search for a book by title or author on Library Genesis (with Anna's Archive fallback).
    Returns formatted results with download links.
    If auto_download is True and a direct file URL is found, downloads to ./downloads/.
    """
    books = _libgen_search(query, max_results=5)

    # ── LibGen found results ──────────────────────────────────────────────────
    if books:
        lines = [f"[LibGen] Found {len(books)} result(s) for: {query}\n"]
        download_done = False

        for i, b in enumerate(books, 1):
            lines.append(f"{i}. {b['title']}")
            if b["authors"]:
                lines.append(f"   Author(s): {b['authors']}")
            details = " | ".join(x for x in [b["year"], b["lang"], b["size"], b["ext"].upper()] if x)
            if details:
                lines.append(f"   {details}")

            if b["md5"]:
                dl_url = _libgen_download_url(b["md5"])
                lines.append(f"   Download: {dl_url}")

                # Auto-download the first result
                if auto_download and not download_done and i == 1:
                    fname   = _safe_filename(b["title"], b.get("ext", "pdf"))
                    result  = _download_file(dl_url, fname)
                    if not result.startswith("Download failed"):
                        lines.append(f"   ✓ Saved to: {result}")
                        download_done = True
                    else:
                        lines.append(f"   ✗ Auto-download failed — use link above manually.")
            else:
                lines.append(f"   Page: https://libgen.is/search.php?req={quote_plus(b['title'])}")
            lines.append("")

        return "\n".join(lines)

    # ── Fallback: Anna's Archive ──────────────────────────────────────────────
    anna = _annas_search(query, max_results=5)
    if anna:
        lines = [
            f"[LibGen unavailable — Anna's Archive] Results for: {query}\n",
            f"Note: Anna's Archive links open a detail page with download options.\n",
        ]
        for i, a in enumerate(anna, 1):
            lines.append(f"{i}. {a.get('title', 'Unknown title')}")
            lines.append(f"   {a.get('url', '')}")
            lines.append("")
        return "\n".join(lines)

    return (
        f"No results found for '{query}' on LibGen or Anna's Archive.\n"
        f"Try searching manually:\n"
        f"  https://libgen.is/search.php?req={quote_plus(query)}\n"
        f"  https://annas-archive.org/search?q={quote_plus(query)}"
    )
