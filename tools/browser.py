"""
Browser tools — simple URL opening, page scraping, and Playwright automation.
Playwright functions open a VISIBLE Chrome window by default for tasks that
require user interaction (logins, form fills, etc.).  Sessions are persisted
so repeated visits skip the login step.
"""
import asyncio
import webbrowser
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

_SESSIONS_DIR = Path(__file__).parent.parent / "data" / "browser_sessions"


# ── Async helper ──────────────────────────────────────────────────────────────
def _run_async(coro):
    """Run an async coroutine safely from a synchronous context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception:
            pass


# ── Existing tools (unchanged) ────────────────────────────────────────────────
def open_url(url: str) -> str:
    """Open a URL in the default system browser."""
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
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text  = soup.get_text(separator="\n", strip=True)
        lines = [l for l in text.splitlines() if l.strip()]
        content = "\n".join(lines)
        return content[:3000] + ("..." if len(content) > 3000 else "")

    except Exception as e:
        return f"Failed to scrape {url}: {e}"


# ── Playwright helpers ────────────────────────────────────────────────────────
def _ensure_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def _safe_session_name(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name) or "default"


async def _launch_browser(playwright, headless: bool, channel: str = "chrome"):
    """Try to launch with installed Chrome; fall back to bundled Chromium."""
    try:
        return await playwright.chromium.launch(
            headless=headless,
            channel=channel,
            args=["--start-maximized"] if not headless else [],
        )
    except Exception:
        return await playwright.chromium.launch(
            headless=headless,
            args=["--window-size=1280,900"] if not headless else [],
        )


async def _launch_persistent(playwright, profile_dir: Path, headless: bool):
    """Try persistent context with installed Chrome; fall back to bundled."""
    opts = dict(
        headless=headless,
        args=["--start-maximized"] if not headless else [],
        no_viewport=not headless,
    )
    try:
        return await playwright.chromium.launch_persistent_context(
            str(profile_dir), channel="chrome", **opts
        )
    except Exception:
        opts.pop("no_viewport", None)
        opts["args"] = ["--window-size=1280,900"] if not headless else []
        return await playwright.chromium.launch_persistent_context(
            str(profile_dir), **opts
        )


# ── Public browser automation functions ──────────────────────────────────────
def browser_open_visible(url: str, wait_seconds: int = 60) -> str:
    """
    Open a URL in a visible Chrome window.
    Keeps the window open for `wait_seconds` so the user can interact.
    Good for reading, watching, or light interaction.
    """
    url = _ensure_url(url)

    async def _run():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await _launch_browser(p, headless=False)
            ctx  = await browser.new_context(no_viewport=True)
            page = await ctx.new_page()
            await page.goto(url)
            await page.wait_for_timeout(wait_seconds * 1000)
            await browser.close()
        return f"Browser closed after {wait_seconds}s."

    try:
        _run_async(_run())
        return f"Opened {url} in visible browser."
    except Exception as e:
        webbrowser.open(url)
        return f"Opened {url} in system browser (Playwright error: {e})."


def browser_login(url: str, service: str = "default", wait_seconds: int = 120) -> str:
    """
    Open URL in a visible Chrome window with a PERSISTENT session profile.
    The window stays open for `wait_seconds` so the user can sign in manually.
    After closing, cookies and login state are saved and reused on next call.

    Use this whenever the user asks to sign in, log in, or access a service
    that requires authentication.  Do NOT use headless mode for this tool.
    """
    url         = _ensure_url(url)
    profile_dir = _SESSIONS_DIR / _safe_session_name(service)
    profile_dir.mkdir(parents=True, exist_ok=True)

    async def _run():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            ctx  = await _launch_persistent(p, profile_dir, headless=False)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(url)
            # Stay open so the user can log in manually
            await page.wait_for_timeout(wait_seconds * 1000)
            await ctx.close()

    try:
        _run_async(_run())
        return (
            f"Login window for '{service}' closed. "
            f"Session saved to {profile_dir}. "
            f"Future visits will reuse this session automatically."
        )
    except Exception as e:
        webbrowser.open(url)
        return (
            f"Opened {url} in system browser. "
            f"Could not save session (Playwright error: {e}). "
            f"Please sign in manually."
        )


def browser_with_session(url: str, service: str = "default") -> str:
    """
    Open a URL using a previously saved login session for `service`.
    If no session exists yet, falls back to browser_login() so the user
    can sign in and save the session for next time.
    """
    url         = _ensure_url(url)
    profile_dir = _SESSIONS_DIR / _safe_session_name(service)

    if not profile_dir.exists():
        # No session yet — open for login
        return browser_login(url, service)

    async def _run():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            ctx  = await _launch_persistent(p, profile_dir, headless=False)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(url)
            await page.wait_for_timeout(30_000)   # 30 s visible window
            await ctx.close()

    try:
        _run_async(_run())
        return f"Opened {url} with saved '{service}' session."
    except Exception as e:
        webbrowser.open(url)
        return f"Opened {url} in system browser: {e}"


def browser_list_sessions() -> str:
    """List all saved browser sessions."""
    if not _SESSIONS_DIR.exists():
        return "No saved browser sessions."
    sessions = [d.name for d in _SESSIONS_DIR.iterdir() if d.is_dir()]
    if not sessions:
        return "No saved browser sessions."
    return "Saved sessions: " + ", ".join(sessions)
