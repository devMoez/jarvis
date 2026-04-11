"""
Self-Evolution System — Phase 10
Jarvis can discover, research, and build new tools for itself.

Three sub-systems:
  Tool Scout   — scans conversations for recurring tool gaps (things Jarvis tried but couldn't do)
  Researcher   — given a tool idea, researches the best API/library to implement it
  Builder      — generates the tool module code, writes it to tools/, registers it in main.py

Commands:
  /evolve gaps              — show detected tool gaps
  /evolve research <idea>   — research implementation for an idea
  /evolve build <idea>      — fully build + register a new tool (generates code via LLM)
  /evolve list              — list all auto-built tools
  /evolve undo <name>       — remove an auto-built tool
"""
from __future__ import annotations
import os, json, re, datetime, threading
from pathlib import Path

_DATA_DIR        = Path(__file__).parent.parent / "data"
_GAPS_FILE       = _DATA_DIR / "tool_gaps.json"
_BUILT_FILE      = _DATA_DIR / "evolved_tools.json"
_TOOLS_DIR       = Path(__file__).parent.parent / "tools"
_LOCK            = threading.Lock()


# ── Gap tracking ──────────────────────────────────────────────────────────────
def record_gap(description: str) -> None:
    """Record a detected tool gap (called from orchestrator when tool not found)."""
    with _LOCK:
        gaps = _load_gaps()
        key  = _normalize(description)
        if key in gaps:
            gaps[key]["count"] += 1
            gaps[key]["last"]   = datetime.datetime.now().isoformat()
        else:
            gaps[key] = {
                "description": description,
                "count":       1,
                "first":       datetime.datetime.now().isoformat(),
                "last":        datetime.datetime.now().isoformat(),
            }
        _save_gaps(gaps)


def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower().strip())[:120]


def _load_gaps() -> dict:
    if _GAPS_FILE.exists():
        try:
            return json.loads(_GAPS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_gaps(data: dict) -> None:
    _GAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _GAPS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_gaps(min_count: int = 2) -> list[dict]:
    gaps = _load_gaps()
    result = [v for v in gaps.values() if v["count"] >= min_count]
    return sorted(result, key=lambda x: x["count"], reverse=True)


def clear_gap(description: str) -> bool:
    with _LOCK:
        gaps = _load_gaps()
        key  = _normalize(description)
        if key in gaps:
            del gaps[key]
            _save_gaps(gaps)
            return True
        return False


# ── Evolved tools registry ─────────────────────────────────────────────────────
def _load_built() -> list[dict]:
    if _BUILT_FILE.exists():
        try:
            return json.loads(_BUILT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_built(data: list) -> None:
    _BUILT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _BUILT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_evolved_tools() -> list[dict]:
    return _load_built()


# ── Researcher ────────────────────────────────────────────────────────────────
def research_tool_idea(idea: str) -> str:
    """
    Ask the LLM to research the best way to implement a tool idea.
    Returns a structured research brief.
    """
    from core.api_manager import APIManager
    api = APIManager()

    prompt = f"""You are a senior Python developer helping to extend a personal AI assistant.

Tool idea: {idea}

Research and provide:
1. Best Python library or API for this (free tier preferred)
2. Required API key(s) / environment variable names
3. pip install command
4. A clear 2-3 sentence description of what the tool will do
5. The function signature: def tool_name(param1: type, ...) -> str

Keep it concise and practical. Format as numbered sections."""

    try:
        client = api.get_client()
        resp   = client.chat.completions.create(
            model=api.current_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            stream=False,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Research failed: {e}"


# ── Builder ───────────────────────────────────────────────────────────────────
def build_tool(idea: str, research_brief: str = "") -> dict:
    """
    Generate, write, and register a new tool.
    Returns {"success": bool, "tool_name": str, "file": str, "error": str}.
    """
    from core.api_manager import APIManager
    api = APIManager()

    context = f"\nResearch brief:\n{research_brief}" if research_brief else ""

    prompt = f"""You are a senior Python developer. Generate a complete, working Python tool module for a personal AI assistant.

Tool idea: {idea}{context}

Requirements:
- Single Python file, self-contained (no external project imports except os, json, datetime, pathlib, httpx, openai)
- Main function must return a human-readable string
- Handle errors gracefully (try/except, return error string — never raise)
- Use environment variables for API keys (os.getenv)
- Include a module docstring describing what it does
- ONLY output the Python code, nothing else — no markdown fences, no explanation

Example structure:
\"\"\"Module docstring\"\"\"
import os
from pathlib import Path

def tool_name(param: str) -> str:
    key = os.getenv("SOME_API_KEY", "").strip()
    if not key:
        return "Error: SOME_API_KEY not set"
    try:
        # implementation
        return result
    except Exception as e:
        return f"Error: {{e}}"
"""

    try:
        client = api.get_client()
        resp   = client.chat.completions.create(
            model=api.current_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            stream=False,
        )
        code = resp.choices[0].message.content.strip()
        # Strip markdown fences if LLM included them anyway
        code = re.sub(r'^```(?:python)?\n?', '', code, flags=re.MULTILINE)
        code = re.sub(r'\n?```$', '', code, flags=re.MULTILINE)
        code = code.strip()
    except Exception as e:
        return {"success": False, "tool_name": "", "file": "", "error": str(e)}

    # Extract module name from first def
    fn_match = re.search(r'^def (\w+)\(', code, re.MULTILINE)
    if not fn_match:
        return {"success": False, "tool_name": "", "file": "", "error": "Could not find function definition in generated code"}

    tool_name = fn_match.group(1)
    file_name = f"evolved_{tool_name}.py"
    file_path = _TOOLS_DIR / file_name

    # Write the file
    try:
        _TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        file_path.write_text(code, encoding="utf-8")
    except Exception as e:
        return {"success": False, "tool_name": tool_name, "file": str(file_path), "error": f"Write failed: {e}"}

    # Register in evolved_tools.json
    built = _load_built()
    built.append({
        "idea":      idea,
        "tool_name": tool_name,
        "file":      file_name,
        "built_at":  datetime.datetime.now().isoformat(),
    })
    _save_built(built)

    return {"success": True, "tool_name": tool_name, "file": str(file_path), "error": ""}


def undo_evolved_tool(tool_name: str) -> dict:
    """Remove an auto-built tool."""
    built = _load_built()
    entry = next((e for e in built if e["tool_name"] == tool_name), None)
    if not entry:
        return {"success": False, "error": f"No evolved tool named '{tool_name}'"}

    file_path = _TOOLS_DIR / entry["file"]
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        return {"success": False, "error": f"Could not delete file: {e}"}

    built = [e for e in built if e["tool_name"] != tool_name]
    _save_built(built)
    return {"success": True, "error": ""}
