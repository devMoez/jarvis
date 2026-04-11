"""
n8n Integration — Phase 9
Trigger n8n workflows from Jarvis via webhook.

Setup:
  1. Set N8N_WEBHOOK_URL in .env (e.g. https://your-n8n.example.com/webhook/)
  2. Set N8N_API_KEY in .env (optional — for n8n REST API calls)

Commands:
  /n8n trigger <workflow-name-or-id> [key=value ...]  — trigger a workflow
  /n8n list                                            — list saved workflow shortcuts
  /n8n add <name> <webhook-url>                        — save a webhook shortcut
  /n8n remove <name>                                   — remove a shortcut
  /n8n status                                          — ping n8n and show version

Workflow data can include any JSON-serializable key=value pairs.
The base webhook URL is read from N8N_WEBHOOK_URL; named shortcuts override it.
"""
from __future__ import annotations
import os, json, datetime
from pathlib import Path

_SHORTCUTS_FILE = Path(__file__).parent.parent / "data" / "n8n_shortcuts.json"


# ── Shortcut management ────────────────────────────────────────────────────────
def _load_shortcuts() -> dict:
    if _SHORTCUTS_FILE.exists():
        try:
            return json.loads(_SHORTCUTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_shortcuts(data: dict) -> None:
    _SHORTCUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SHORTCUTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def add_shortcut(name: str, webhook_url: str) -> None:
    data = _load_shortcuts()
    data[name.lower()] = {"url": webhook_url, "added": datetime.datetime.now().isoformat()}
    _save_shortcuts(data)


def remove_shortcut(name: str) -> bool:
    data = _load_shortcuts()
    if name.lower() in data:
        del data[name.lower()]
        _save_shortcuts(data)
        return True
    return False


def list_shortcuts() -> dict:
    return _load_shortcuts()


# ── Trigger a workflow ─────────────────────────────────────────────────────────
def trigger_workflow(
    name_or_url: str,
    payload:     dict | None = None,
    method:      str = "POST",
) -> dict:
    """
    Trigger an n8n workflow via webhook.
    name_or_url: shortcut name OR full webhook URL
    payload:     data dict sent as JSON body (POST) or query params (GET)
    Returns {"success": bool, "status": int, "response": any, "error": str}.
    """
    shortcuts = _load_shortcuts()
    key = name_or_url.lower()

    if key in shortcuts:
        url = shortcuts[key]["url"]
    elif name_or_url.startswith("http"):
        url = name_or_url
    else:
        # Try appending to base N8N_WEBHOOK_URL
        base = os.getenv("N8N_WEBHOOK_URL", "").rstrip("/")
        if not base:
            return {
                "success": False, "status": 0, "response": None,
                "error": f"Unknown workflow '{name_or_url}' and no N8N_WEBHOOK_URL set",
            }
        url = f"{base}/{name_or_url}"

    if payload is None:
        payload = {}
    payload.setdefault("source", "jarvis")
    payload.setdefault("timestamp", datetime.datetime.now().isoformat())

    try:
        import httpx
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv("N8N_API_KEY", "").strip()
        if api_key:
            headers["X-N8N-API-KEY"] = api_key

        if method.upper() == "GET":
            r = httpx.get(url, params=payload, headers=headers, timeout=30)
        else:
            r = httpx.post(url, json=payload, headers=headers, timeout=30)

        try:
            body = r.json()
        except Exception:
            body = r.text

        return {"success": r.status_code < 400, "status": r.status_code, "response": body, "error": ""}
    except Exception as e:
        return {"success": False, "status": 0, "response": None, "error": str(e)}


# ── n8n REST API — list/run workflows ─────────────────────────────────────────
def n8n_api_list_workflows() -> dict:
    """
    List workflows via n8n REST API.
    Requires N8N_BASE_URL and N8N_API_KEY.
    """
    base = os.getenv("N8N_BASE_URL", "").rstrip("/")
    key  = os.getenv("N8N_API_KEY", "").strip()
    if not base or not key:
        return {"success": False, "error": "N8N_BASE_URL and N8N_API_KEY required"}

    try:
        import httpx
        r = httpx.get(
            f"{base}/api/v1/workflows",
            headers={"X-N8N-API-KEY": key},
            timeout=15,
        )
        if r.status_code != 200:
            return {"success": False, "error": f"n8n API {r.status_code}: {r.text[:200]}"}
        return {"success": True, "workflows": r.json().get("data", [])}
    except Exception as e:
        return {"success": False, "error": str(e)}


def n8n_ping() -> dict:
    """Ping n8n instance and return version info."""
    base = os.getenv("N8N_BASE_URL", "").rstrip("/")
    key  = os.getenv("N8N_API_KEY", "").strip()
    if not base:
        return {"success": False, "error": "N8N_BASE_URL not set"}

    try:
        import httpx
        headers = {}
        if key:
            headers["X-N8N-API-KEY"] = key
        r = httpx.get(f"{base}/healthz", headers=headers, timeout=10)
        if r.status_code == 200:
            return {"success": True, "status": "online", "base_url": base}
        return {"success": False, "error": f"n8n returned {r.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Parse CLI key=value args into a dict ──────────────────────────────────────
def parse_kv_args(args: list[str]) -> dict:
    """Parse ["key=value", "foo=bar"] → {"key": "value", "foo": "bar"}"""
    data: dict = {}
    for arg in args:
        if "=" in arg:
            k, _, v = arg.partition("=")
            # Try to coerce types
            if v.lower() == "true":
                data[k] = True
            elif v.lower() == "false":
                data[k] = False
            else:
                try:
                    data[k] = int(v)
                except ValueError:
                    try:
                        data[k] = float(v)
                    except ValueError:
                        data[k] = v
    return data
