"""
Persistent skills — custom behaviors Jarvis always follows.
Stored in data/skills.json. Injected into every system prompt.
"""
import json
import os
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


def add_skill(instruction: str) -> dict:
    """Add a persistent skill. Returns the new skill entry."""
    skills = _load()
    skill_id = (max((s["id"] for s in skills), default=0) + 1)
    skill = {"id": skill_id, "instruction": instruction.strip()}
    skills.append(skill)
    _save(skills)
    return skill


def remove_skill(skill_id: int) -> bool:
    """Remove a skill by ID. Returns True if removed."""
    skills = _load()
    new_skills = [s for s in skills if s["id"] != skill_id]
    if len(new_skills) == len(skills):
        return False
    _save(new_skills)
    return True


def clear_skills() -> int:
    """Remove all skills. Returns count removed."""
    skills = _load()
    _save([])
    return len(skills)


def get_skills_prompt() -> str:
    """Return skills formatted for system prompt injection."""
    skills = _load()
    if not skills:
        return ""
    lines = ["[Permanent skills — always follow these]"]
    for s in skills:
        lines.append(f"- {s['instruction']}")
    return "\n".join(lines)
