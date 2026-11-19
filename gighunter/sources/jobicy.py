"""Jobicy remote-jobs public API (https://jobicy.com/jobs-rss-feed). Jobicy asks to be credited
and for links to go to the original listing URL; the digest shows the source and links to `url`."""
from datetime import datetime

from ..models import Job
from ..text import html_to_text
from ._http import get_json

API = "https://jobicy.com/api/v2/remote-jobs"


def fetch(cfg: dict) -> list[Job]:
    out, seen = [], set()
    for tag in cfg.get("tags") or ["sql"]:
        params = {"count": cfg.get("count", 50), "tag": tag}
        if cfg.get("geo"):
            params["geo"] = cfg["geo"]
        for j in get_json(API, **params).get("jobs", []):
            if j["id"] in seen:
                continue
            seen.add(j["id"])
            geo = j.get("jobGeo") or ""
            regions = [g.strip() for g in geo.split(",") if g.strip() and g.strip().lower() != "anywhere"]
            pub = j.get("pubDate")
            out.append(Job(
                id=f"jobicy:{j['id']}", title=html_to_text(j.get("jobTitle", "")),
                company=j.get("companyName", ""), url=j.get("url", ""),
                description=html_to_text(j.get("jobDescription") or j.get("jobExcerpt") or ""),
                location="Remote" + (f" ({geo})" if geo else ""), remote=True, remote_regions=regions,
                posted=datetime.fromisoformat(pub) if pub else None, source="Jobicy",
                salary_min=_int(j.get("salaryMin")) if j.get("salaryCurrency", "USD") == "USD" else None,
                salary_max=_int(j.get("salaryMax")) if j.get("salaryCurrency", "USD") == "USD" else None,
            ))
    return out


def _int(v):
    try:
        return int(float(v)) if v not in (None, "", "None") else None
    except (TypeError, ValueError):
        return None
