# Short-term memory is handled directly in core/conversation.py
# This module is a no-op placeholder for future extensions (e.g. summarization when context fills up)

def summarize_if_needed(messages: list, max_tokens: int = 6000) -> list:
    """If message history is getting large, return it as-is (future: summarize old turns)."""
    return messages
