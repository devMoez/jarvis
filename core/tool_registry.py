from typing import Any, Callable

# ── Tool definitions (OpenAI function-calling format) ─────────────────────────
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web using DuckDuckGo. Use this for current events, facts, or anything you don't know.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {"type": "integer", "description": "Number of results (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in the default browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to open"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_page",
            "description": "Fetch and read the text content of a webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to scrape"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application on the computer by name (e.g. 'notepad', 'chrome', 'spotify').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the app to open"},
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get system information: current time, date, battery level, or clipboard content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "enum": ["time", "date", "battery", "clipboard", "all"],
                        "description": "What info to retrieve",
                    },
                },
                "required": ["info_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or append text to a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Content to write"},
                    "mode": {"type": "string", "enum": ["write", "append"], "default": "write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: Desktop)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a fact or piece of information in long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact or information to remember"},
                },
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Send a Windows desktop notification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["title", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run any shell/terminal command on the computer and return its output. Use this for anything that needs a command line.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run"},
                    "background": {"type": "boolean", "description": "Run in a separate terminal window (default false)", "default": False},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move or rename a file or folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source path"},
                    "destination": {"type": "string", "description": "Destination path"},
                },
                "required": ["source", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file or folder to a new location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "destination": {"type": "string"},
                },
                "required": ["source", "destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or folder permanently.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to delete"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "system_power",
            "description": "Control system power state: shutdown, restart, hibernate, sleep, lock screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["shutdown", "restart", "hibernate", "sleep", "lock", "cancel"],
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "install_software",
            "description": "Install software using winget (default), pip, or choco.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package": {"type": "string", "description": "Package name to install"},
                    "manager": {"type": "string", "enum": ["winget", "pip", "choco"], "default": "winget"},
                },
                "required": ["package"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files by name pattern on the computer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_pattern": {"type": "string", "description": "Filename or pattern e.g. '*.pdf' or 'report.docx'"},
                    "search_dir": {"type": "string", "description": "Directory to search in (default C:\\Users)", "default": "C:\\Users"},
                },
                "required": ["name_pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_open_visible",
            "description": (
                "Open a URL in a VISIBLE Chrome window so the user can see and interact with it. "
                "Use for browsing, watching, or any task where the user wants to see the browser."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open"},
                    "wait_seconds": {"type": "integer", "description": "Seconds to keep window open (default 60)", "default": 60},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_login",
            "description": (
                "Open a URL in a visible Chrome window for the user to sign in / log in manually. "
                "Saves the login session (cookies) so future visits skip the login step. "
                "ALWAYS use this — never open_url — when the task involves signing in, logging in, "
                "or accessing a service that requires authentication (Google, Gmail, YouTube, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url":          {"type": "string", "description": "Login page URL"},
                    "service":      {"type": "string", "description": "Service name for session storage e.g. 'google', 'github'"},
                    "wait_seconds": {"type": "integer", "description": "Seconds to keep window open for login (default 120)", "default": 120},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_with_session",
            "description": (
                "Open a URL using a previously saved login session. "
                "Use this when the user has logged in before and you want to open the page already authenticated. "
                "If no session exists, automatically opens for login first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url":     {"type": "string", "description": "URL to open"},
                    "service": {"type": "string", "description": "Service name matching a saved session e.g. 'google'"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deep_research",
            "description": (
                "Research a topic in depth by finding top sources via Tavily and scraping their full content. "
                "Use this when the user asks to 'research', 'deep dive', 'investigate', or 'write a report' on a topic. "
                "Returns all scraped content for synthesis into a complete report."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic":       {"type": "string",  "description": "The topic or question to research"},
                    "max_sources": {"type": "integer", "description": "Number of sources to scrape (default 5)", "default": 5},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_book",
            "description": (
                "Search for a book, PDF, or ebook by title or author on Library Genesis (with Anna's Archive fallback). "
                "Returns download links and optionally auto-downloads to ./downloads/. "
                "Use this when the user asks to find, download, or get a book."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query":         {"type": "string",  "description": "Book title, author, or ISBN"},
                    "auto_download": {"type": "boolean", "description": "Auto-download the first result (default true)", "default": True},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wiki_search",
            "description": "Look up a topic on Wikipedia. Returns a summary and key facts. Use when the user asks about a person, place, concept, or historical event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The topic to look up on Wikipedia"},
                },
                "required": ["topic"],
            },
        },
    },
]


class ToolRegistry:
    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        self._handlers[name] = fn

    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        if name not in self._handlers:
            return f"Error: unknown tool '{name}'"
        try:
            result = self._handlers[name](**args)
            return str(result) if result is not None else "Done."
        except Exception as e:
            return f"Error running {name}: {e}"

    @staticmethod
    def get_definitions() -> list[dict]:
        return TOOL_DEFINITIONS
