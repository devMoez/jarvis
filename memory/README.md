# Ultron Memory System - Database Backend

This replaces the slow JSON file loading with a fast SQLite database + caching layer.

## Files

- `mem_db.py` - SQLite database initialization and core functions
- `mem_cache.py` - Caching layer with automatic invalidation
- `ultron_memory.db` - SQLite database (replaces ultron_memory.json for active data)
- `ultron_memory.json` - Kept for backward compatibility, now populated from cache on demand

## Usage

### Getting Data
```python
from mem_cache import (
    get_user_preferences,
    get_user_instructions, 
    get_session_info,
    get_patterns
)

prefs = get_user_preferences()
instructions = get_user_instructions()
session = get_session_info()
patterns = get_patterns()
```

### Setting Data
```python
from mem_cache import (
    set_user_preferences,
    set_user_instructions,
    set_session_info,
    set_patterns
)

set_user_preferences({"identity": "ultron", "communicationMode": "caveman-full"})
set_user_instructions(["Always identify as ultron"])
set_session_info({"startTime": "2026-05-08T10:00:00Z"})
set_patterns({"prefers_short_answers": {"count": 5, "suggested": True, "description": "User prefers short answers"}})
```

### Pattern Tracking
```python
from mem_cache import increment_pattern_key

# Returns True if pattern should be suggested (count >= 3 and not yet suggested)
should_suggest = increment_pattern_key("prefers_short_answers", "User prefers short answers")
```

## Performance

- Memory access: ~0.2ms (vs 30-40s previously)
- Cache TTL: 5 minutes (automatically refreshed from DB)
- Automatic cache invalidation on data writes

## Migration

Existing data from `ultron_memory.json` and `patterns.py` should be migrated to the database.
The cache builder will populate initial values from existing JSON files if database is empty.

## Notes

- `ultron_memory.db` is the source of truth
- `ultron_memory.json` is regenerated from cache on read (for compatibility)
- Patterns are now stored in database table instead of `data/patterns.json`