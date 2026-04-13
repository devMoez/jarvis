"""
Cloudflare-only API manager with stable task routing.
"""
import os
from pathlib import Path
from typing import Optional

import openai

_ENV_FILE = Path(__file__).parent.parent / ".env"
_CF_ENV_ACCOUNT = "CLOUDFLARE_ACCOUNT_ID"
_CF_ENV_EMAIL = "CLOUDFLARE_AUTH_EMAIL"
_CF_ENV_KEY = "CLOUDFLARE_GLOBAL_API_KEY"
_CF_ENV_TOKEN = "CLOUDFLARE_API_TOKEN"
_CF_ENV_ACCOUNT_2 = "CLOUDFLARE_ACCOUNT_ID_2"
_CF_ENV_TOKEN_2 = "CLOUDFLARE_API_TOKEN_2"
_CF_ENV_ACCOUNT_3 = "CLOUDFLARE_ACCOUNT_ID_3"
_CF_ENV_TOKEN_3 = "CLOUDFLARE_API_TOKEN_3"
_CF_BASE_TMPL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1"

_CF_ROUTER_MODEL = "@cf/google/gemma-4-26b-a4b-it"
_TIER_MODELS: dict[str, str] = {
    "light": "@cf/google/gemma-4-26b-a4b-it",
    "heavy": "@cf/nvidia/nemotron-3-120b-a12b",
    "coder": "@cf/moonshotai/kimi-k2.5",
}
_DEFAULT_TIER = "light"

_ALIASES = {
    "cf": "cloudflare",
    "cloudflare": "cloudflare",
    "cloudflare-account": "cloudflare-account",
    "cloudflare-email": "cloudflare-email",
    "cloudflare-key": "cloudflare-key",
    "cloudflare-token": "cloudflare-token",
    "cloudflare-account-2": "cloudflare-account-2",
    "cloudflare-token-2": "cloudflare-token-2",
    "cloudflare-account-3": "cloudflare-account-3",
    "cloudflare-token-3": "cloudflare-token-3",
}

_CODER_KEYWORDS = (
    "code", "coding", "script", "program", "debug", "implement", "refactor",
    "optimize", "bug", "fix", "function", "class", "module", "tool",
    "automation", "automate", "workflow", "n8n", "api", "json", "yaml",
    "python", "javascript", "typescript", "powershell", "terminal", "command",
    "repo", "repository", "playwright", "test", "tests", "open", "launch",
    "run", "start", "execute", "app", "application", "browser", "file",
    "system command", "scheduler",
)
_HEAVY_KEYWORDS = (
    "research", "deep research", "analyze", "analyse", "plan", "design",
    "compare", "review", "investigate", "study", "evaluate", "report",
    "essay", "letter", "document", "translate", "summarize", "academic",
    "paper", "proposal", "cv", "long-form",
)


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


def _preview(raw: str) -> str:
    return f"{raw[:8]}...{raw[-4:]}" if len(raw) > 12 else ("***" if raw else "")


def _cf_global_creds() -> Optional[tuple[str, str, str]]:
    account = os.environ.get(_CF_ENV_ACCOUNT, "").strip()
    email = os.environ.get(_CF_ENV_EMAIL, "").strip()
    key = os.environ.get(_CF_ENV_KEY, "").strip()
    if account and email and key:
        return account, email, key
    return None


def _cf_headers_global(email: str, key: str) -> dict:
    return {
        "X-Auth-Email": email,
        "X-Auth-Key": key,
        "Content-Type": "application/json",
    }


def _cf_headers_token(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _cf_token_creds() -> list[tuple[str, str]]:
    creds: list[tuple[str, str]] = []
    account_1 = os.environ.get(_CF_ENV_ACCOUNT, "").strip()
    token_1 = os.environ.get(_CF_ENV_TOKEN, "").strip()
    if account_1 and token_1:
        creds.append((account_1, token_1))

    account_2 = os.environ.get(_CF_ENV_ACCOUNT_2, "").strip()
    token_2 = os.environ.get(_CF_ENV_TOKEN_2, "").strip()
    if account_2 and token_2:
        creds.append((account_2, token_2))

    account_3 = os.environ.get(_CF_ENV_ACCOUNT_3, "").strip()
    token_3 = os.environ.get(_CF_ENV_TOKEN_3, "").strip()
    if account_3 and token_3:
        creds.append((account_3, token_3))
    return creds


def _make_client(key: str, base_url: str, headers: dict) -> Optional[openai.OpenAI]:
    if not key:
        return None
    return openai.OpenAI(
        api_key=key,
        base_url=base_url,
        default_headers=headers,
        timeout=90.0,
    )


def _heuristic_route(text: str) -> str:
    lower = text.lower()
    if any(kw in lower for kw in _CODER_KEYWORDS):
        return "coder"
    if len(text) > 220 or any(kw in lower for kw in _HEAVY_KEYWORDS):
        return "heavy"
    return "light"


def configure_openrouter_keys(_keys) -> tuple[bool, str]:
    return False, "OpenRouter is disabled. Jarvis uses Cloudflare only."


def add_key(provider_input: str, key: str) -> tuple[bool, str]:
    provider = provider_input.lower().strip()
    normalized = _ALIASES.get(provider, provider)
    clean_key = key.strip()
    if not clean_key:
        return False, "API key cannot be empty."

    if normalized == "cloudflare-account":
        os.environ[_CF_ENV_ACCOUNT] = clean_key
        _update_env_file(_CF_ENV_ACCOUNT, clean_key)
        return True, "Cloudflare account id saved."

    if normalized == "cloudflare-email":
        os.environ[_CF_ENV_EMAIL] = clean_key
        _update_env_file(_CF_ENV_EMAIL, clean_key)
        return True, "Cloudflare auth email saved."

    if normalized == "cloudflare-key":
        os.environ[_CF_ENV_KEY] = clean_key
        _update_env_file(_CF_ENV_KEY, clean_key)
        return True, "Cloudflare global API key saved."

    if normalized == "cloudflare-token":
        os.environ[_CF_ENV_TOKEN] = clean_key
        _update_env_file(_CF_ENV_TOKEN, clean_key)
        return True, "Cloudflare API token saved."

    if normalized == "cloudflare-account-2":
        os.environ[_CF_ENV_ACCOUNT_2] = clean_key
        _update_env_file(_CF_ENV_ACCOUNT_2, clean_key)
        return True, "Cloudflare fallback account id #2 saved."

    if normalized == "cloudflare-token-2":
        os.environ[_CF_ENV_TOKEN_2] = clean_key
        _update_env_file(_CF_ENV_TOKEN_2, clean_key)
        return True, "Cloudflare fallback API token #2 saved."

    if normalized == "cloudflare-account-3":
        os.environ[_CF_ENV_ACCOUNT_3] = clean_key
        _update_env_file(_CF_ENV_ACCOUNT_3, clean_key)
        return True, "Cloudflare fallback account id #3 saved."

    if normalized == "cloudflare-token-3":
        os.environ[_CF_ENV_TOKEN_3] = clean_key
        _update_env_file(_CF_ENV_TOKEN_3, clean_key)
        return True, "Cloudflare fallback API token #3 saved."

    if normalized == "cloudflare":
        parts = [p.strip() for p in clean_key.split(",")]
        if len(parts) == 3 and all(parts):
            account, email, api_key = parts
            os.environ[_CF_ENV_ACCOUNT] = account
            os.environ[_CF_ENV_EMAIL] = email
            os.environ[_CF_ENV_KEY] = api_key
            _update_env_file(_CF_ENV_ACCOUNT, account)
            _update_env_file(_CF_ENV_EMAIL, email)
            _update_env_file(_CF_ENV_KEY, api_key)
            return True, "Cloudflare credentials saved."
        if len(parts) == 2 and all(parts):
            account, token = parts
            os.environ[_CF_ENV_ACCOUNT] = account
            os.environ[_CF_ENV_TOKEN] = token
            _update_env_file(_CF_ENV_ACCOUNT, account)
            _update_env_file(_CF_ENV_TOKEN, token)
            return True, "Cloudflare account + API token saved."
        return False, "Use: /add-api cloudflare <account_id,email,global_api_key> OR <account_id,api_token>"

    return False, (
        f"Unknown provider '{provider_input}'. "
        "Use: cloudflare-account, cloudflare-email, cloudflare-key, cloudflare-token, "
        "cloudflare-account-2, cloudflare-token-2, cloudflare-account-3, cloudflare-token-3, or cloudflare"
    )


def list_providers() -> list[dict]:
    global_creds = _cf_global_creds()
    token_creds = _cf_token_creds()
    previews: list[str] = []
    if global_creds:
        previews.append(_preview(global_creds[2]))
    for _, tok in token_creds:
        previews.append(_preview(tok))
    configured = bool(global_creds or token_creds)
    return [
        {
            "name": "cloudflare",
            "display": "Cloudflare AI",
            "configured": configured,
            "preview": ", ".join(previews[:3]),
            "models": list(_TIER_MODELS.values()),
            "key_count": len(previews),
            "extra": "fallback-ready" if configured and len(previews) > 1 else ("configured" if configured else "missing credentials"),
        }
    ]


def has_configured_provider() -> bool:
    return bool(_cf_global_creds() or _cf_token_creds())


def describe_tiers() -> dict[str, str]:
    return {
        "router": _CF_ROUTER_MODEL,
        "light": _TIER_MODELS["light"],
        "heavy": _TIER_MODELS["heavy"],
        "coder": _TIER_MODELS["coder"],
    }


class APIManager:
    """Stable Cloudflare-only manager."""

    def __init__(self):
        self._tier: str = _DEFAULT_TIER
        self._chain: list[tuple[str, str, str, dict, str]] = []
        self._index: int = 0
        self._build()

    def _build(self) -> None:
        global_creds = _cf_global_creds()
        token_creds = _cf_token_creds()
        chain: list[tuple[str, str, str, dict, str]] = []
        model = _TIER_MODELS.get(self._tier, _TIER_MODELS[_DEFAULT_TIER])
        if global_creds:
            account, email, key = global_creds
            chain.append(
                (
                    "cloudflare",
                    model,
                    _CF_BASE_TMPL.format(account_id=account),
                    _cf_headers_global(email, key),
                    key,
                )
            )
        for i, (account, token) in enumerate(token_creds, start=1):
            chain.append(
                (
                    f"cloudflare-token-{i}",
                    model,
                    _CF_BASE_TMPL.format(account_id=account),
                    _cf_headers_token(token),
                    token,
                )
            )
        self._chain = chain
        self._index = 0

    def rebuild(self) -> None:
        self._build()

    def set_tier(self, tier: str) -> None:
        if tier in _TIER_MODELS and tier != self._tier:
            self._tier = tier
            self._build()

    def reset(self) -> None:
        self._index = 0

    def route_task(self, text: str) -> str:
        current = self.current
        if not current:
            return _heuristic_route(text)
        client = _make_client(key=current[4], base_url=current[2], headers=current[3])
        if client is None:
            return _heuristic_route(text)

        messages = [
            {
                "role": "system",
                "content": (
                    "Classify the user request into exactly one label: light, heavy, or coder.\n"
                    "light = normal chat, simple questions, quick summaries, humanized responses.\n"
                    "heavy = deep research, academic writing, long-form documents and analysis.\n"
                    "coder = tool calling, browser automation, file ops, scheduler/n8n, system commands, multi-step execution.\n"
                    "Reply with only one word: light, heavy, or coder."
                ),
            },
            {"role": "user", "content": text[:4000]},
        ]
        try:
            resp = client.chat.completions.create(
                model=_CF_ROUTER_MODEL,
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
            pass

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
        return _make_client(key=current[4], base_url=current[2], headers=current[3])

    def try_next(self) -> bool:
        if not self._chain:
            return False
        if self._index + 1 < len(self._chain):
            self._index += 1
            return True
        return False

    def __len__(self) -> int:
        return len(self._chain)
