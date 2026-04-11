"""
Multi-provider API key management.
Primary (and only) provider: OpenRouter — routes to any model via one key.
"""
import os
from pathlib import Path
from typing import Optional
import openai

_ENV_FILE = Path(__file__).parent.parent / ".env"

# ── Provider registry ─────────────────────────────────────────────────────────
PROVIDERS: dict[str, dict] = {
    "openrouter": {
        "display":  "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key":  "OPENROUTER_API_KEY",
        "models":   [
            "meta-llama/llama-4-maverick",
        ],
        "headers":  {
            "HTTP-Referer": "https://github.com/jarvis-ai",
            "X-Title":      "Jarvis",
        },
    },
}

# ── Model tiers ───────────────────────────────────────────────────────────────
# light → fast model for simple ops (search, file I/O, short Q&A, open app)
# heavy → best model for research, writing, planning, coding, long reasoning
_TIER_MODELS: dict[str, list[tuple[str, str]]] = {
    "light": [("openrouter", "meta-llama/llama-4-maverick")],
    "heavy": [("openrouter", "meta-llama/llama-4-maverick")],
}

# Input aliases → canonical provider name
_ALIASES = {
    "or":    "openrouter",
    "orouter": "openrouter",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_key(provider: str) -> str:
    return os.environ.get(PROVIDERS[provider]["env_key"], "")


def _update_env_file(env_key: str, value: str) -> None:
    """Write or replace a key=value in .env, preserving all other lines."""
    lines: list[str] = []
    found = False

    if _ENV_FILE.exists():
        with open(_ENV_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

    for i, line in enumerate(lines):
        stripped = line.split("=", 1)[0].strip()
        if stripped == env_key:
            lines[i] = f"{env_key}={value}\n"
            found = True
            break

    if not found:
        lines.append(f"{env_key}={value}\n")

    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ── Public API ────────────────────────────────────────────────────────────────
def add_key(provider_input: str, key: str) -> tuple[bool, str]:
    """
    Add/update an API key for a provider.
    Saves to .env and sets os.environ immediately.
    Returns (success, message).
    """
    name = _ALIASES.get(provider_input.lower(), provider_input.lower())
    if name not in PROVIDERS:
        avail = ", ".join(PROVIDERS) + "  (aliases: " + ", ".join(_ALIASES) + ")"
        return False, f"Unknown provider '{provider_input}'. Available: {avail}"

    env_key = PROVIDERS[name]["env_key"]
    os.environ[env_key] = key.strip()
    _update_env_file(env_key, key.strip())
    return True, f"{PROVIDERS[name]['display']} key saved."


def list_providers() -> list[dict]:
    """Return status of every provider."""
    result = []
    for name, cfg in PROVIDERS.items():
        raw_key = _get_key(name)
        configured = bool(raw_key)
        if raw_key and len(raw_key) > 12:
            preview = f"{raw_key[:8]}...{raw_key[-4:]}"
        elif raw_key:
            preview = "***"
        else:
            preview = ""
        result.append({
            "name":       name,
            "display":    cfg["display"],
            "configured": configured,
            "preview":    preview,
            "models":     cfg["models"],
        })
    return result


def make_client(provider: str, api_key: str = "") -> Optional[openai.OpenAI]:
    """Create an OpenAI-compatible client. api_key overrides env lookup."""
    key = api_key or _get_key(provider)
    if not key:
        return None
    cfg = PROVIDERS[provider]
    return openai.OpenAI(
        api_key=key,
        base_url=cfg["base_url"],
        default_headers=cfg.get("headers", {}),
    )


# ── APIManager class ──────────────────────────────────────────────────────────
class APIManager:
    """Ordered (provider, model, key) fallback chain."""

    def __init__(self):
        self._flat: list[tuple[str, str, str]] = []
        self._index: int = 0
        self._build_chain()

    def _build_chain(self) -> None:
        chain: list[tuple[str, str, str]] = []
        key = _get_key("openrouter")
        if key:
            for m in PROVIDERS["openrouter"]["models"]:
                chain.append(("openrouter", m, key))
        self._flat = chain
        self._index = 0

    def rebuild(self) -> None:
        """Rebuild after adding a new key."""
        old_model = self.current_model
        self._build_chain()
        for i, (_, m, _k) in enumerate(self._flat):
            if m == old_model:
                self._index = i
                return

    # ── Properties ───────────────────────────────────────────────────────────
    @property
    def current(self) -> Optional[tuple[str, str, str]]:
        if not self._flat:
            return None
        return self._flat[self._index % len(self._flat)]

    @property
    def current_model(self) -> str:
        c = self.current
        return c[1] if c else "none"

    @property
    def current_provider(self) -> str:
        c = self.current
        return c[0] if c else "none"

    @property
    def chain_length(self) -> int:
        return len(self._flat)

    def get_client(self) -> Optional[openai.OpenAI]:
        c = self.current
        if not c:
            return None
        provider, _model, key = c
        return make_client(provider, api_key=key)

    def set_tier(self, tier: str) -> None:
        """Move the chain index to the best available model for this tier."""
        for i, (provider, model, _key) in enumerate(self._flat):
            for t_provider, t_model in _TIER_MODELS.get(tier, []):
                if provider == t_provider and model == t_model:
                    self._index = i
                    return

    def try_next(self) -> bool:
        """Advance to next entry. Returns False if all options exhausted."""
        if not self._flat:
            return False
        nxt = self._index + 1
        if nxt >= len(self._flat):
            self._index = 0
            return False
        self._index = nxt
        return True

    def reset(self) -> None:
        self._index = 0

    def __len__(self) -> int:
        return len(self._flat)
