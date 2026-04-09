"""
Post-conversation fact extractor.
After each conversation turn, extract memorable facts and store them.
Runs asynchronously so it doesn't slow down the main loop.
"""
import threading
import openai
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_FALLBACK_MODEL
from memory.long_term import store

_client = openai.OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_BASE_URL,
    default_headers={"HTTP-Referer": "https://jarvis.local", "X-Title": "Jarvis AI"},
)

EXTRACT_PROMPT = """Extract any personal facts, preferences, or important information about the user from this conversation.
Return ONLY a JSON array of strings, each string being one fact. Return [] if nothing notable.
Example: ["User's name is John", "User prefers dark mode", "User works as a software engineer"]

Conversation:
{conversation}

JSON array:"""


def extract_and_store_async(user_msg: str, assistant_msg: str) -> None:
    """Run fact extraction in a background thread."""
    t = threading.Thread(
        target=_extract_and_store,
        args=(user_msg, assistant_msg),
        daemon=True,
    )
    t.start()


def _extract_and_store(user_msg: str, assistant_msg: str) -> None:
    conversation = f"User: {user_msg}\nJarvis: {assistant_msg}"
    try:
        response = _client.chat.completions.create(
            model=LLM_FALLBACK_MODEL,  # use fast/cheap model for extraction
            messages=[
                {"role": "user", "content": EXTRACT_PROMPT.format(conversation=conversation)}
            ],
            temperature=0,
            max_tokens=256,
        )
        import json
        content = response.choices[0].message.content.strip()
        facts = json.loads(content)
        for fact in facts:
            if fact and len(fact) > 5:
                store(fact)
    except Exception:
        pass  # silent — extraction is best-effort
