import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'ultron_memory.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Preferences table
    c.execute('''CREATE TABLE IF NOT EXISTS preferences
                 (key TEXT PRIMARY KEY, value TEXT)''')
    # Session table (for simple key-value session state)
    c.execute('''CREATE TABLE IF NOT EXISTS session
                 (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # Patterns table
    c.execute('''CREATE TABLE IF NOT EXISTS patterns
                 (pattern_key TEXT PRIMARY KEY, count INTEGER, suggested BOOLEAN, description TEXT)''')
    # Session interactions table (stores inputs/outputs)
    c.execute('''CREATE TABLE IF NOT EXISTS session_interactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER NOT NULL,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  user_input TEXT,
                  assistant_output TEXT)''')
    # Session summaries table (stores brief summaries of completed sessions)
    c.execute('''CREATE TABLE IF NOT EXISTS session_summaries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER NOT NULL,
                  summary TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # Extracted facts table (for quick lookup of user preferences, etc.)
    c.execute('''CREATE TABLE IF NOT EXISTS extracted_facts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id INTEGER NOT NULL,
                  fact_type TEXT NOT NULL,
                  fact_key TEXT NOT NULL,
                  fact_value TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # Session metadata table (tracks session count, current session id, etc.)
    c.execute('''CREATE TABLE IF NOT EXISTS session_metadata
                 (key TEXT PRIMARY KEY, value TEXT)''')
    # Initialize session count if not exists
    c.execute('''INSERT OR IGNORE INTO session_metadata (key, value)
                 VALUES ("session_count", "0")''')
    c.execute('''INSERT OR IGNORE INTO session_metadata (key, value)
                 VALUES ("current_session_id", "0")''')
    conn.commit()
    conn.close()

def set_pref(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)''',
              (key, json.dumps(value) if not isinstance(value, str) else value))
    conn.commit()
    conn.close()

def get_pref(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT value FROM preferences WHERE key=?''', (key,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row[0])
        except:
            return row[0]
    return None

def set_session(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO session (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)''',
              (key, json.dumps(value) if not isinstance(value, str) else value))
    conn.commit()
    conn.close()

def get_session(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT value FROM session WHERE key=?''', (key,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row[0])
        except:
            return row[0]
    return None

# Pattern functions
def set_pattern(pattern_key, count, suggested, description):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO patterns (pattern_key, count, suggested, description)
                 VALUES (?, ?, ?, ?)''',
              (pattern_key, count, suggested, description))
    conn.commit()
    conn.close()

def get_pattern(pattern_key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT count, suggested, description FROM patterns WHERE pattern_key=?''', (pattern_key,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"count": row[0], "suggested": bool(row[1]), "description": row[2]}
    return None

def increment_pattern(pattern_key, description):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT count, suggested, description FROM patterns WHERE pattern_key=?''', (pattern_key,))
    row = c.fetchone()
    if row:
        count = row[0] + 1
        suggested = row[1]
        # Keep the description if exists, else use the provided one
        desc = row[2] if row[2] else description
        c.execute('''UPDATE patterns SET count=?, description=? WHERE pattern_key=?''',
                  (count, desc, pattern_key))
    else:
        count = 1
        suggested = False
        desc = description
        c.execute('''INSERT INTO patterns (pattern_key, count, suggested, description)
                     VALUES (?, ?, ?, ?)''',
                  (pattern_key, count, suggested, desc))
    conn.commit()
    conn.close()
    return count >= 3 and not suggested  # Return True if we should suggest

def get_all_patterns():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT pattern_key, count, suggested, description FROM patterns''')
    rows = c.fetchall()
    conn.close()
    result = {}
    for row in rows:
        result[row[0]] = {"count": row[1], "suggested": bool(row[2]), "description": row[3]}
    return result

if __name__ == '__main__':
    init_db()
    print('Database initialized')