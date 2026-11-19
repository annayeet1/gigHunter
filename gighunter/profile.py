"""Load the matcher's view of you from two files.

aboutme.md   : facts (what you HAVE): skills, years, experience. Also the resume truth source.
JobParams.md : preferences (what you WANT): titles, level, location, salary, dealbreakers, bonus terms.

If a key appears in both, JobParams.md wins for preference keys. A missing JobParams.md falls back
to any preference keys still in aboutme.md, so older profiles keep working.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from . import workspace
from .models import Profile

PREFERENCE_KEYS = {"target_titles", "target_seniority", "work_modes", "locations",
                   "min_salary_usd", "dealbreakers", "bonus_keywords", "remote_regions"}


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


def load_vocab() -> list[str]:
    """Common tech skills used only to detect gaps (skills a listing asks for that you don't list).
    Engine list plus optional workspace additions in config/tech_skills.yaml."""
    terms = list(_yaml(workspace.resource("defaults", "tech_skills.yaml")).get("skills", []))
    terms += list(_yaml(workspace.path("config", "tech_skills.yaml")).get("skills", []))
    return list(dict.fromkeys(str(t).lower() for t in terms))


def load_sites() -> list[dict]:
    return _yaml(workspace.path("config", "sites.yaml")).get("sources", [])


# Delimiters are lines that are exactly '---'; dashes inside comments (# -----) must not count.
_FRONT_MATTER = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)^---[ \t]*(?:\r?\n|\Z)(.*)\Z", re.S | re.M)


def read_front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = _FRONT_MATTER.match(text)
    if not m:
        raise ValueError(f"{path} must start with a YAML front-matter block: a '---' line, "
                         "YAML, then a closing '---' line")
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        raise ValueError(f"{path}: front matter must be YAML key: value pairs")
    return fm, m.group(2)


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

    skills, context = {}, {}
    for k, v in (about.get("skills") or {}).items():
        if _is_todo(k):
            continue
        name = str(k).lower()
        if isinstance(v, dict):            # e.g. clarity: {weight: 3, requires_any: [epic, caboodle]}
            skills[name] = int(v.get("weight", 1))
            if v.get("requires_any"):
                context[name] = [str(c) for c in v["requires_any"]]
        else:
            skills[name] = int(v)
    seniority = prefs.get("target_seniority") or about.get("current_seniority") or about.get("seniority") or "mid"

    return Profile(
        name=about.get("name", ""),
        target_titles=_clean(prefs.get("target_titles")),
        years_experience=float(about.get("years_experience") or 0),
        seniority=[str(s).lower() for s in (seniority if isinstance(seniority, list) else [seniority])],
        work_modes=[m.lower() for m in (prefs.get("work_modes") or ["remote"])],
        locations=_clean(prefs.get("locations")),
        skills=skills,
        dealbreakers=[d.lower() for d in _clean(prefs.get("dealbreakers"))],
        bonus_keywords=[b.lower() for b in _clean(prefs.get("bonus_keywords"))],
        min_salary_usd=int(prefs.get("min_salary_usd") or 0),
        body=_strip_todo_lines(body),
        ideal_job=_strip_todo_lines(ideal),
        raw={"about": about, "params": params},
        skill_context=context,
        **({"remote_regions": [str(r).lower() for r in prefs["remote_regions"]]} if prefs.get("remote_regions") else {}),
    )
