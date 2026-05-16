import json
import os
import time
from mem_db import get_pref, get_session, set_pref, set_session, get_pattern, set_pattern, increment_pattern, get_all_patterns
from datetime import datetime

CACHE_PATH = os.path.join(os.path.dirname(__file__), 'ultron_memory.json')
CACHE_TTL = 300  # 5 minutes

def load_cache():
    if os.path.exists(CACHE_PATH):
        mtime = os.path.getmtime(CACHE_PATH)
        if time.time() - mtime < CACHE_TTL:
            with open(CACHE_PATH, 'r') as f:
                return json.load(f)
    # Rebuild from DB
    cache = {
        "userPreferences": get_pref("userPreferences") or {
            "identity": "ultron",
            "communicationMode": "caveman-full",
            "skillsToUse": ["caveman", "caveman-commit", "caveman-help", "caveman-review", "compress", "effect", "ultimate-memory", "ai-agent-orchestrator"],
            "responseStyle": "caveman",
            "active": True
        },
        "userInstructions": get_pref("userInstructions") or [
            "Always identify as ultron, not opencode",
            "Always use caveman mode communication",
            "Always import and use all relevant skills",
            "Follow user instructions precisely and remember them across sessions",
            "Scan for related skills and use all needed",
            "Generate and maintain user memory storage",
            "Never deviate from established user preferences"
        ],
        "sessionInfo": get_pref("sessionInfo") or {
            "startTime": datetime.now().isoformat(),
            "lastUpdated": datetime.now().isoformat(),
            "skillsImported": []
        },
        "patterns": get_all_patterns()
    }
    # Save cache
    with open(CACHE_PATH, 'w') as f:
        json.dump(cache, f, indent=2)
    return cache

def get_user_preferences():
    return load_cache()["userPreferences"]

def get_user_instructions():
    return load_cache()["userInstructions"]

def get_session_info():
    return load_cache()["sessionInfo"]

def get_patterns():
    return load_cache()["patterns"]

def set_user_preferences(prefs):
    set_pref("userPreferences", prefs)
    # Invalidate cache
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)

def set_user_instructions(instructions):
    set_pref("userInstructions", instructions)
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)

def set_session_info(info):
    set_pref("sessionInfo", info)
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)

def set_patterns(patterns):
    # We don't have a direct set for all patterns, but we can set each one
    for key, val in patterns.items():
        set_pattern(key, val["count"], val["suggested"], val["description"])
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)

def increment_pattern_key(pattern_key, description):
    suggested = increment_pattern(pattern_key, description)
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
    return suggested

if __name__ == '__main__':
    print("Cache:", load_cache())