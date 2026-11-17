"""Tiny JSON state in the workspace's data/ folder, committed back by the workflow so jobs aren't re-sent."""
from __future__ import annotations

import json
from datetime import date, timedelta

from . import workspace

KEEP_DAYS = 60


def _p(name):
    return workspace.path("data", name)


def _load(p) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() and p.read_text().strip() else {}


def _save(p, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=1, sort_keys=True), encoding="utf-8")


def seen_ids() -> set[str]:
    return set(_load(_p("seen_jobs.json")))


def mark_seen(ids: list[str], today: date) -> None:
    p = _p("seen_jobs.json")
    d = _load(p)
    for i in ids:
        d.setdefault(i, today.isoformat())
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    _save(p, {k: v for k, v in d.items() if v >= cutoff})


def last_digest_date() -> str | None:
    return _load(_p("state.json")).get("last_digest_date")


def set_last_digest_date(day: date) -> None:
    p = _p("state.json")
    s = _load(p)
    s["last_digest_date"] = day.isoformat()
    _save(p, s)
