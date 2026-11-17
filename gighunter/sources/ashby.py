from datetime import datetime

from ..models import Job
from ..text import html_to_text
from ._http import get_json


def fetch(cfg: dict) -> list[Job]:
    company = cfg["company"]
    data = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{company}", includeCompensation="true")
    out = []
    for j in data.get("jobs", []):
        if not j.get("isListed", True):
            continue
        posted = j.get("publishedAt")
        out.append(Job(
            id=f"ashby:{company}:{j['id']}", title=j.get("title", ""),
            company=cfg.get("name", company), url=j.get("jobUrl", ""),
            description=j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", "")),
            location=j.get("location", ""), remote=j.get("isRemote"),
            posted=datetime.fromisoformat(posted.replace("Z", "+00:00")) if posted else None,
            source=cfg.get("name", "ashby"),
        ))
    return out
