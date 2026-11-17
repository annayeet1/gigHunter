"""Email schedule from config/schedule.toml.

STANDARD LIBRARY ONLY: the GitHub workflow runs this as a cheap gate *before* installing
dependencies, so hourly runs that shouldn't send exit in seconds.

    python -m gighunter.schedule            print whether a digest is due now
    python -m gighunter.schedule --github   also write send=true|false to $GITHUB_OUTPUT

A digest is due when ALL of these hold:
  enabled; today (local) is in `days`; no digest has gone out today; and local time is in
  [send_time - early_minutes, send_time + catch_up_minutes].
The workflow runs hourly at :55, so with early_minutes=10 a 09:00 send goes out at ~08:55-09:10.
"""
from __future__ import annotations

import json
import os
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import workspace

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class Schedule:
    enabled: bool = True
    timezone: str = "America/Chicago"
    send_time: time = time(9, 0)
    days: tuple[str, ...] = tuple(DAYS)
    min_match_score: float = 60
    max_listings: int = 25
    send_when_empty: bool = True
    early_minutes: int = 10
    catch_up_minutes: int = 120

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_schedule(path: Path | None = None) -> Schedule:
    path = path or workspace.path("config", "schedule.toml")
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    errors = []
    s = Schedule()
    s.enabled = bool(raw.get("enabled", True))
    s.timezone = raw.get("timezone", s.timezone)
    try:
        ZoneInfo(s.timezone)
    except Exception:
        errors.append(f"timezone {s.timezone!r} is not a valid IANA zone (e.g. America/Chicago)")
    try:
        hh, mm = str(raw.get("send_time", "09:00")).split(":")
        s.send_time = time(int(hh), int(mm))
    except Exception:
        errors.append(f"send_time {raw.get('send_time')!r} must be HH:MM in 24-hour time")
    days = raw.get("days", DAYS)
    if days in ("daily", "*"):
        days = DAYS
    elif days == "weekdays":
        days = DAYS[:5]
    norm = [str(d)[:3].title() for d in days]
    bad = [d for d in norm if d not in DAYS]
    if bad or not norm:
        errors.append(f"days must be a list like ['Mon','Wed'] or 'daily'/'weekdays'; bad: {bad or days}")
    s.days = tuple(norm)
    s.min_match_score = float(raw.get("min_match_score", s.min_match_score))
    if not 0 <= s.min_match_score <= 100:
        errors.append("min_match_score must be between 0 and 100")
    s.max_listings = int(raw.get("max_listings", s.max_listings))
    s.send_when_empty = bool(raw.get("send_when_empty", True))
    s.early_minutes = int(raw.get("early_minutes", s.early_minutes))
    s.catch_up_minutes = int(raw.get("catch_up_minutes", s.catch_up_minutes))
    if errors:
        raise ValueError(f"{path.name}: " + "; ".join(errors))
    return s


def last_sent_date() -> str | None:
    state = workspace.path("data", "state.json")
    if state.exists() and state.read_text().strip():
        return json.loads(state.read_text(encoding="utf-8")).get("last_digest_date")
    return None


def is_due(s: Schedule, now: datetime, last_sent: str | None) -> tuple[bool, str]:
    """`now` must be timezone-aware. Returns (due, human-readable reason)."""
    local = now.astimezone(s.tz)
    if not s.enabled:
        return False, "schedule disabled"
    if DAYS[local.weekday()] not in s.days:
        return False, f"{DAYS[local.weekday()]} is not a send day"
    if last_sent == local.date().isoformat():
        return False, "already sent today"
    target = datetime.combine(local.date(), s.send_time, tzinfo=s.tz)
    start = target - timedelta(minutes=s.early_minutes)
    end = target + timedelta(minutes=s.catch_up_minutes)
    if start <= local <= end:
        return True, f"due: local {local:%a %H:%M} within {start:%H:%M}-{end:%H:%M}"
    return False, f"not due: local {local:%a %H:%M}, window {start:%H:%M}-{end:%H:%M}"


def main(argv: list[str]) -> int:
    s = load_schedule()
    due, why = is_due(s, datetime.now(s.tz), last_sent_date())
    print(why)
    if "--github" in argv and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"send={'true' if due else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
