"""
Persistent skills — custom behaviors Jarvis always follows.
Stored in data/skills.json. Injected into every system prompt.

source field:
  "auto"   — learned automatically, protected from delete/clear
  "manual" — added by user, can be removed freely
"""
import json
from pathlib import Path

SKILLS_FILE = Path("data/skills.json")


def _load() -> list[dict]:
    if not SKILLS_FILE.exists():
        return []
    try:
        return json.loads(SKILLS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(skills: list[dict]) -> None:
    SKILLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SKILLS_FILE.write_text(json.dumps(skills, indent=2), encoding="utf-8")


def list_skills() -> list[dict]:
    return _load()


def add_skill(instruction: str, source: str = "manual") -> dict:
    """Add a persistent skill. source = 'manual' | 'auto'"""
    skills = _load()
    # Deduplicate — skip if identical instruction already exists
    if any(s["instruction"].strip() == instruction.strip() for s in skills):
        return next(s for s in skills if s["instruction"].strip() == instruction.strip())
    skill_id = (max((s["id"] for s in skills), default=0) + 1)
    skill = {"id": skill_id, "instruction": instruction.strip(), "source": source}
    skills.append(skill)
    _save(skills)
    return skill


def remove_skill(skill_id: int) -> tuple[bool, str]:
    """
    Remove a skill by ID.
    Returns (success, reason).
    Auto-learned skills are protected — cannot be deleted.
    """
    skills = _load()
    target = next((s for s in skills if s["id"] == skill_id), None)
    if target is None:
        return False, "not_found"
    if target.get("source") == "auto":
        return False, "protected"
    new_skills = [s for s in skills if s["id"] != skill_id]
    _save(new_skills)
    return True, "ok"


def clear_skills() -> int:
    """Remove only manual skills. Auto-learned skills are preserved."""
    skills = _load()
    protected = [s for s in skills if s.get("source") == "auto"]
    removed = len(skills) - len(protected)
    _save(protected)
    return removed


def get_skills_prompt() -> str:
    """Return skills formatted for system prompt injection."""
    skills = _load()
    if not skills:
        return ""
    lines = ["[Permanent skills — always follow these]"]
    for s in skills:
        lines.append(f"- {s['instruction']}")
    return "\n".join(lines)
