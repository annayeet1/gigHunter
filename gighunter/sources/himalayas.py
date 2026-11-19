"""Himalayas remote-jobs public API (https://himalayas.app/jobs/api). Searched per query."""
from datetime import datetime, timezone

from ..models import Job
from ..text import html_to_text
from ._http import get_json

API = "https://himalayas.app/jobs/api/search"


def fetch(cfg: dict) -> list[Job]:
    out, seen = [], set()
    for q in cfg.get("queries") or ["data engineer"]:
        data = get_json(API, q=q, limit=cfg.get("limit", 50))
        for j in data.get("jobs", []):
            guid = j.get("guid") or j.get("applicationLink")
            if not guid or guid in seen:
                continue
            seen.add(guid)
            regions = [str(r) for r in (j.get("locationRestrictions") or [])]
            ts = j.get("pubDate")
            out.append(Job(
                id=f"himalayas:{guid.rsplit('/', 1)[-1]}:{j.get('companySlug', '')}",
                title=j.get("title", ""), company=j.get("companyName", ""),
                url=j.get("applicationLink") or guid,
                description=html_to_text(j.get("description") or j.get("excerpt") or ""),
                location="Remote" + (f" ({', '.join(regions)})" if regions else ""), remote=True,
                remote_regions=regions,
                posted=datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else None,
                source="Himalayas",
                salary_min=_usd(j, "minSalary"), salary_max=_usd(j, "maxSalary"),
                tags=[str(c) for c in (j.get("categories") or [])],
            ))
    return out


def _usd(j: dict, key: str) -> int | None:
    """Only trust annual USD salaries for the salary filter."""
    v = j.get(key)
    if not v or (j.get("currency") or "USD").upper() != "USD":
        return None
    if (j.get("salaryPeriod") or "year").lower() not in ("year", "yearly", "annual"):
        return None
    return int(v)
