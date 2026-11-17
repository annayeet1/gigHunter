from datetime import datetime, timezone

from ..models import Job
from ._http import get_json


def fetch(cfg: dict) -> list[Job]:
    company = cfg["company"]
    data = get_json(f"https://api.lever.co/v0/postings/{company}", mode="json")
    out = []
    for j in data:
        cats = j.get("categories") or {}
        ts = j.get("createdAt")
        out.append(Job(
            id=f"lever:{company}:{j['id']}", title=j.get("text", ""),
            company=cfg.get("name", company), url=j.get("hostedUrl", ""),
            description=j.get("descriptionPlain", "") + "\n" + "\n".join(
                f"{l.get('text','')}: {l.get('content','')}" for l in j.get("lists", [])),
            location=cats.get("location", ""),
            remote=(j.get("workplaceType") == "remote") if j.get("workplaceType") else None,
            posted=datetime.fromtimestamp(ts / 1000, tz=timezone.utc) if ts else None,
            source=cfg.get("name", "lever"),
        ))
    return out
