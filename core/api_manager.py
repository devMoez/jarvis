"""
OpenRouter-only API manager with stable task routing.

Behavior:
  - One fixed router model decides which lane to use.
  - Each lane uses one fixed response model.
  - Jarvis only rotates API keys, not response models, during a turn.
"""
import os
import re
from pathlib import Path
from typing import Iterable, Optional

import openai

_ENV_FILE = Path(__file__).parent.parent / ".env"
_OR_ENV_BASE = "OPENROUTER_API_KEY"
_OR_BASE = "https://openrouter.ai/api/v1"
_OR_HEADERS = {
    "HTTP-Referer": "https://github.com/moez-f/jarvis-ai",
    "X-Title": "Jarvis AI Assistant",
}

_ROUTER_MODEL = "google/gemini-2.5-pro-exp:free"
_TIER_MODELS: dict[str, str] = {
    "light": "google/gemini-2.5-pro-exp:free",
    "heavy": "google/gemini-2.5-pro-exp:free",
    "coder": "google/gemini-2.5-pro-exp:free",
}
_DEFAULT_TIER = "light"

_ALIASES = {
    "or": "openrouter",
    "orouter": "openrouter",
    "openrouter": "openrouter",
}

_CODER_KEYWORDS = (
    "code", "coding", "script", "program", "debug", "implement", "refactor",
    "optimize", "bug", "fix", "function", "class", "module", "tool",
    "automation", "automate", "workflow", "n8n", "api", "json", "yaml",
    "python", "javascript", "typescript", "powershell", "terminal", "command",
    "repo", "repository", "playwright", "test", "tests", "open", "launch",
    "run", "start", "execute", "app", "application",
)
_HEAVY_KEYWORDS = (
    "research", "analyze", "analyse", "plan", "design", "compare", "review",
    "investigate", "study", "evaluate", "report", "essay", "letter",
    "document", "translate", "summarize", "difference between", "how does",
    "how do i", "help me understand", "walk me through", "what is the",
    "why does", "why is", "can you explain", "tell me about", "search",
    "look up", "latest", "browse", "website", "web", "scrape", "news",
)


def _slot_env_key(slot: int) -> str:
    return _OR_ENV_BASE if slot <= 1 else f"{_OR_ENV_BASE}_{slot}"


def _or_env_names() -> list[str]:
    slots: dict[int, str] = {1: _OR_ENV_BASE}
    for env_name in os.environ:
        if env_name == _OR_ENV_BASE:
            continue
        match = re.fullmatch(rf"{_OR_ENV_BASE}_(\d+)", env_name)
        if match:
            slots[int(match.group(1))] = env_name
    return [slots[idx] for idx in sorted(slots)]


def _or_keys() -> list[str]:
    keys: list[str] = []
    for env_name in _or_env_names():
        raw = os.environ.get(env_name, "").strip()
        if raw and raw not in keys:
            keys.append(raw)
    return keys


def _load_env_lines() -> list[str]:
    if not _ENV_FILE.exists():
        return []
    with open(_ENV_FILE, "r", encoding="utf-8") as f:
        return f.readlines()


def _write_env_lines(lines: list[str]) -> None:
    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _update_env_file(env_key: str, value: str) -> None:
    lines = _load_env_lines()
    found = False
    for idx, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == env_key:
            lines[idx] = f"{env_key}={value}\n"
            found = True
            break
    if not found:
        lines.append(f"{env_key}={value}\n")
    _write_env_lines(lines)


def _rewrite_prefixed_env(prefix: str, entries: dict[str, str]) -> None:
    remaining = dict(entries)
    kept: list[str] = []

    for line in _load_env_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            kept.append(line)
            continue

        env_key = line.split("=", 1)[0].strip()
        if env_key == prefix or env_key.startswith(f"{prefix}_"):
            if env_key in remaining:
                kept.append(f"{env_key}={remaining.pop(env_key)}\n")
            continue

        kept.append(line)

    for env_key, value in remaining.items():
        kept.append(f"{env_key}={value}\n")

    _write_env_lines(kept)


def _preview(raw: str) -> str:
    return f"{raw[:8]}...{raw[-4:]}" if len(raw) > 12 else ("***" if raw else "")


def _make_client(key: str) -> Optional[openai.OpenAI]:
    if not key:
        return None
    return openai.OpenAI(
        api_key=key,
        base_url=_OR_BASE,
        default_headers=_OR_HEADERS,
        timeout=90.0,
    )


def _heuristic_route(text: str) -> str:
    lower = text.lower()
    if any(kw in lower for kw in _CODER_KEYWORDS):
        return "coder"
    if len(text) > 220 or any(kw in lower for kw in _HEAVY_KEYWORDS):
        return "heavy"
    return "light"


def configure_openrouter_keys(keys: Iterable[str]) -> tuple[bool, str]:
    clean_keys: list[str] = []
    for raw in keys:
        key = raw.strip()
        if key and key not in clean_keys:
            clean_keys.append(key)

    if not clean_keys:
        return False, "No OpenRouter keys provided."

    updates = {_slot_env_key(idx): key for idx, key in enumerate(clean_keys, start=1)}
    for env_key, key in updates.items():
        os.environ[env_key] = key

    for env_name in list(os.environ):
        if env_name == _OR_ENV_BASE or env_name.startswith(f"{_OR_ENV_BASE}_"):
            if env_name not in updates:
                os.environ.pop(env_name, None)

    _rewrite_prefixed_env(_OR_ENV_BASE, updates)
    return True, f"Loaded {len(clean_keys)} OpenRouter key(s)."


def add_key(provider_input: str, key: str) -> tuple[bool, str]:
    provider = provider_input.lower().strip()
    normalized = _ALIASES.get(provider, provider)
    clean_key = key.strip()
    if not clean_key:
        return False, "API key cannot be empty."

    if normalized == "openrouter":
        os.environ[_OR_ENV_BASE] = clean_key
        _update_env_file(_OR_ENV_BASE, clean_key)
        return True, "OpenRouter key saved to slot 1."

    slot_match = re.fullmatch(r"openrouter[_-]?(\d+)", provider)
    if slot_match:
        slot = max(1, int(slot_match.group(1)))
        env_key = _slot_env_key(slot)
        os.environ[env_key] = clean_key
        _update_env_file(env_key, clean_key)
        return True, f"OpenRouter key saved to slot {slot}."

    return False, f"Unknown provider '{provider_input}'. Use: openrouter, openrouter2, openrouter3..."


def list_providers() -> list[dict]:
    or_keys = _or_keys()
    return [
        {
            "name": "openrouter",
            "display": "OpenRouter",
            "configured": bool(or_keys),
            "preview": _preview(or_keys[0] if or_keys else ""),
            "models": [_ROUTER_MODEL, *_TIER_MODELS.values()],
            "key_count": len(or_keys),
            "extra": f"{len(or_keys)} key(s) in pool" if or_keys else "pool empty",
        }
    ]


def has_configured_provider() -> bool:
    return bool(_or_keys())


def describe_tiers() -> dict[str, str]:
    return {
        "router": _ROUTER_MODEL,
        "light": _TIER_MODELS["light"],
        "heavy": _TIER_MODELS["heavy"],
        "coder": _TIER_MODELS["coder"],
    }


class APIManager:
    """
    Stable OpenRouter-only manager.

    The selected tier stays fixed for a request. Only API keys rotate.
    """

    def __init__(self):
        self._tier: str = _DEFAULT_TIER
        self._chain: list[tuple[str, str, str, dict, str]] = []
        self._index: int = 0
        self._or_key_idx: int = 0
        self._build()

    def _build(self) -> None:
        or_keys = _or_keys()
        chain: list[tuple[str, str, str, dict, str]] = []
        if or_keys:
            model = _TIER_MODELS.get(self._tier, _TIER_MODELS[_DEFAULT_TIER])
            chain.append(("openrouter", model, _OR_BASE, _OR_HEADERS, or_keys[0]))
        self._chain = chain
        self._index = 0
        self._or_key_idx = 0

    def rebuild(self) -> None:
        self._build()

    def set_tier(self, tier: str) -> None:
        if tier in _TIER_MODELS and tier != self._tier:
            self._tier = tier
            self._build()

    def reset(self) -> None:
        self._index = 0
        self._or_key_idx = 0

    def route_task(self, text: str) -> str:
        keys = _or_keys()
        if not keys:
            return _heuristic_route(text)

        messages = [
            {
                "role": "system",
                "content": (
                    "Classify the user request into exactly one label: light, heavy, or coder.\n"
                    "light = normal chat, simple questions, casual greetings, jokes.\n"
                    "heavy = deep research, planning, complex analysis, long documents.\n"
                    "coder = technical tasks, code, scripts, automation, opening/launching apps, system commands, tools.\n"
                    "Reply with only one word: light, heavy, or coder."
                ),
            },
            {"role": "user", "content": text[:4000]},
        ]

        for key in keys:
            client = _make_client(key)
            if client is None:
                continue
            try:
                resp = client.chat.completions.create(
                    model=_ROUTER_MODEL,
                    messages=messages,
                    max_tokens=4,
                    temperature=0,
                    stream=False,
                )
                content = (resp.choices[0].message.content or "").strip().lower()
                for tier in ("light", "heavy", "coder"):
                    if tier in content:
                        return tier
            except Exception:
                continue

        return _heuristic_route(text)

    @property
    def current(self) -> Optional[tuple[str, str, str, dict, str]]:
        if not self._chain:
            return None
        return self._chain[self._index % len(self._chain)]

    @property
    def current_model(self) -> str:
        current = self.current
        return current[1] if current else "none"

    @property
    def current_provider(self) -> str:
        current = self.current
        return current[0] if current else "none"

    @property
    def current_tier(self) -> str:
        return self._tier

    @property
    def chain_length(self) -> int:
        return len(self._chain)

    def get_client(self) -> Optional[openai.OpenAI]:
        current = self.current
        if not current:
            return None
        return _make_client(current[4])

    def try_next(self) -> bool:
        if not self._chain:
            return False

        or_keys = _or_keys()
        self._or_key_idx += 1
        if self._or_key_idx >= len(or_keys):
            self._or_key_idx = 0
            return False

        provider, model, base_url, headers, _old_key = self._chain[0]
        self._chain[0] = (provider, model, base_url, headers, or_keys[self._or_key_idx])
        return True

    def __len__(self) -> int:
        return len(self._chain)
