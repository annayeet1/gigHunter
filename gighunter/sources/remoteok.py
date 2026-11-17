from datetime import datetime, timezone

from ..models import Job
from ..text import html_to_text
from ._http import get_json


def fetch(cfg: dict) -> list[Job]:
    data = get_json("https://remoteok.com/api")
    want = {t.lower() for t in cfg.get("tags") or []}
    out = []
    for j in data:
        if "id" not in j:          # first element is a legal notice
            continue
        tags = [t.lower() for t in j.get("tags") or []]
        if want and not want & set(tags):
            continue
        ep = j.get("epoch")
        out.append(Job(
            id=f"remoteok:{j['id']}", title=j.get("position", ""), company=j.get("company", ""),
            url=j.get("url", ""), description=html_to_text(j.get("description", "")),
            location=j.get("location") or "Remote", remote=True,
            posted=datetime.fromtimestamp(ep, tz=timezone.utc) if ep else None,
            source="RemoteOK", tags=tags,
            salary_min=j.get("salary_min") or None, salary_max=j.get("salary_max") or None,
        ))
    return out
