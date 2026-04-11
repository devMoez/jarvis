"""TODO list — data/todos.json"""
import json, datetime
from pathlib import Path

_FILE = Path(__file__).parent.parent / "data" / "todos.json"
_PRIORITIES = {"high": 0, "med": 1, "medium": 1, "low": 2}


def _load() -> list:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(items: list) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def add_todo(task: str, priority: str = "med") -> dict:
    priority = priority.lower()
    if priority not in _PRIORITIES:
        priority = "med"
    items = _load()
    item = {
        "id":       max((i["id"] for i in items), default=0) + 1,
        "task":     task,
        "priority": priority,
        "done":     False,
        "created":  datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    items.append(item)
    _save(items)
    return item


def list_todos(show_done: bool = False) -> list:
    items = _load()
    if not show_done:
        items = [i for i in items if not i["done"]]
    return sorted(items, key=lambda x: _PRIORITIES.get(x.get("priority", "med"), 1))


def done_todo(n: int) -> tuple[bool, str]:
    items = _load()
    active = [i for i in items if not i["done"]]
    if n < 1 or n > len(active):
        return False, f"No task #{n} in active list."
    target_id = active[n - 1]["id"]
    for item in items:
        if item["id"] == target_id:
            item["done"] = True
            item["completed"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            _save(items)
            return True, item["task"]
    return False, "Task not found."


def remove_todo(n: int) -> tuple[bool, str]:
    items  = _load()
    active = [i for i in items if not i["done"]]
    if n < 1 or n > len(active):
        return False, f"No task #{n}."
    target_id = active[n - 1]["id"]
    new = [i for i in items if i["id"] != target_id]
    task = active[n - 1]["task"]
    _save(new)
    return True, task


def clear_done() -> int:
    items = _load()
    before = len(items)
    _save([i for i in items if not i["done"]])
    return before - len([i for i in items if not i["done"]])
