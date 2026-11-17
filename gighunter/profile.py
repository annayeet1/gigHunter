"""Load the matcher's view of you from two files.

aboutme.md   : facts (what you HAVE): skills, years, experience. Also the resume truth source.
JobParams.md : preferences (what you WANT): titles, level, location, salary, dealbreakers, bonus terms.

If a key appears in both, JobParams.md wins for preference keys. A missing JobParams.md falls back
to any preference keys still in aboutme.md, so older profiles keep working.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from . import workspace
from .models import Profile

PREFERENCE_KEYS = {"target_titles", "target_seniority", "work_modes", "locations",
                   "min_salary_usd", "dealbreakers", "bonus_keywords"}


def _yaml(p: Path) -> dict:
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_settings() -> dict:
    """Engine defaults overlaid with the workspace's config/settings.yaml."""
    s = _deep_merge(_yaml(workspace.resource("defaults", "settings.yaml")),
                    _yaml(workspace.path("config", "settings.yaml")))
    total = sum(s.get("weights", {}).values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"settings weights must sum to 1.0 (got {total:.2f})")
    return s


def load_aliases() -> dict[str, list[str]]:
    """Built-in skill aliases plus the workspace's additions (lists are unioned)."""
    out = {k.lower(): list(v or []) for k, v in _yaml(workspace.resource("defaults", "skill_aliases.yaml")).items()}
    for k, v in _yaml(workspace.path("config", "skill_aliases.yaml")).items():
        out[k.lower()] = list(dict.fromkeys(out.get(k.lower(), []) + list(v or [])))
    return out


def load_sites() -> list[dict]:
    return _yaml(workspace.path("config", "sites.yaml")).get("sources", [])


def read_front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path} must start with a YAML front-matter block (---)")
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body


def _is_todo(x) -> bool:
    return str(x).strip().upper().startswith("TODO")


def _clean(xs) -> list:
    return [x for x in (xs or []) if x and not _is_todo(x)]


def _strip_todo_lines(md: str) -> str:
    return "\n".join(l for l in md.splitlines() if "TODO" not in l and not l.startswith(">"))


def load_profile(about_path: Path | None = None, params_path: Path | None = None) -> Profile:
    about, body = read_front_matter(about_path or workspace.path("aboutme.md"))
    params_path = params_path or workspace.path("JobParams.md")
    params, ideal = read_front_matter(params_path) if params_path.exists() else ({}, "")

    prefs = {k: about[k] for k in PREFERENCE_KEYS if k in about}   # legacy fallback
    prefs.update({k: v for k, v in params.items() if k in PREFERENCE_KEYS})

    skills = {str(k).lower(): int(v) for k, v in (about.get("skills") or {}).items() if not _is_todo(k)}
    seniority = prefs.get("target_seniority") or about.get("current_seniority") or about.get("seniority") or "mid"

    return Profile(
        name=about.get("name", ""),
        target_titles=_clean(prefs.get("target_titles")),
        years_experience=float(about.get("years_experience") or 0),
        seniority=str(seniority).lower(),
        work_modes=[m.lower() for m in (prefs.get("work_modes") or ["remote"])],
        locations=_clean(prefs.get("locations")),
        skills=skills,
        dealbreakers=[d.lower() for d in _clean(prefs.get("dealbreakers"))],
        bonus_keywords=[b.lower() for b in _clean(prefs.get("bonus_keywords"))],
        min_salary_usd=int(prefs.get("min_salary_usd") or 0),
        body=_strip_todo_lines(body),
        ideal_job=_strip_todo_lines(ideal),
        raw={"about": about, "params": params},
    )
