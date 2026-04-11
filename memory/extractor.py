"""
Adaptive learning extractor.

After each turn:
  1. Extract personal facts  → auto-store to long-term memory
  2. Detect profile fields   → auto-update profile (name, language, timezone)
  3. Detect behavioral patterns → record in pattern tracker
                                  → when threshold hit, queue a skill suggestion

Runs fully async so it never slows the main loop.
Uses APIManager so it benefits from the same provider chain as the main orchestrator.
"""
import json
import threading

from core.api_manager import APIManager
from memory.long_term import store
from memory import patterns as _patterns
from core import profile as _profile

# Lightweight extractor manager — shared instance
_extractor_api = APIManager()

# ── Extraction prompt ─────────────────────────────────────────────────────────
_EXTRACT_PROMPT = """Analyze this single conversation turn and return a JSON object with these keys:

"facts": list of strings — personal facts about the user worth remembering long-term.
  Examples: "User's name is Sara", "User works as a doctor", "User has a dog named Max"
  Only include facts explicitly stated or clearly implied. Return [] if none.

"profile": object — fields to update in the user profile. Only include keys that are clearly stated.
  Allowed keys: "name", "timezone", "language", "preferences" (object of key→value pairs)
  Example: {{"name": "Sara", "preferences": {{"reply_style": "brief"}}}}
  Return {{}} if nothing new.

"patterns": list of objects with keys "key" (stable snake_case identifier), "description" (instruction for Jarvis to always do).
  Only include if the user clearly prefers or repeatedly asks for a specific behavior.
  Examples:
    {{"key": "prefers_urdu", "description": "Always respond in Urdu when the user writes in Urdu"}}
    {{"key": "wants_sources", "description": "Always include sources when giving factual information"}}
    {{"key": "prefers_brief", "description": "Keep all replies under 2 sentences unless asked to elaborate"}}
  Return [] if no clear behavioral preference is shown.

Conversation turn:
User: {user_msg}
Jarvis: {assistant_msg}

Return ONLY valid JSON. No explanation."""


def extract_and_store_async(user_msg: str, assistant_msg: str) -> None:
    """Kick off extraction in a background thread."""
    threading.Thread(
        target=_run,
        args=(user_msg, assistant_msg),
        daemon=True,
        name="Extractor",
    ).start()


def _run(user_msg: str, assistant_msg: str) -> None:
    try:
        client = _extractor_api.get_client()
        if client is None:
            return

        resp = client.chat.completions.create(
            model=_extractor_api.current_model,
            messages=[{
                "role": "user",
                "content": _EXTRACT_PROMPT.format(
                    user_msg=user_msg,
                    assistant_msg=assistant_msg,
                ),
            }],
            temperature=0,
            max_tokens=400,
        )
        raw = resp.choices[0].message.content.strip()

        # Strip markdown code fences if model wraps in ```json
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
    except Exception:
        return   # silent — extraction is best-effort

    # 1. Store personal facts
    for fact in data.get("facts", []):
        if fact and len(fact) > 5:
            store(fact)

    # 2. Auto-update profile
    profile_update = data.get("profile", {})
    if profile_update.get("name"):
        _profile.set_field("name", profile_update["name"])
    if profile_update.get("timezone"):
        _profile.set_field("timezone", profile_update["timezone"])
    if profile_update.get("language"):
        _profile.set_field("language", profile_update["language"])
    for k, v in profile_update.get("preferences", {}).items():
        _profile.set_preference(k, str(v))

    # 3. Record behavioral patterns (threshold → queued suggestion)
    for p in data.get("patterns", []):
        key  = p.get("key", "")
        desc = p.get("description", "")
        if key and desc:
            _patterns.record(key, desc)
