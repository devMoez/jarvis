import webbrowser
import httpx
from bs4 import BeautifulSoup


def open_url(url: str) -> str:
    """Open a URL in the default browser."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url} in browser."


def scrape_page(url: str) -> str:
    """Fetch and extract readable text from a webpage."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Collapse blank lines
        lines = [l for l in text.splitlines() if l.strip()]
        content = "\n".join(lines)
        return content[:3000] + ("..." if len(content) > 3000 else "")

    except Exception as e:
        return f"Failed to scrape {url}: {e}"
