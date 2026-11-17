from datetime import datetime

from ..models import Job
from ..text import html_to_text
from ._http import get_json


def fetch(cfg: dict) -> list[Job]:
    board = cfg["board"]
    data = get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", content="true")
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        posted = j.get("updated_at") or j.get("first_published")
        out.append(Job(
            id=f"greenhouse:{board}:{j['id']}", title=j.get("title", ""),
            company=cfg.get("name", board), url=j.get("absolute_url", ""),
            description=html_to_text(_unescape(j.get("content", ""))), location=loc,
            posted=datetime.fromisoformat(posted) if posted else None, source=cfg.get("name", "greenhouse"),
        ))
    return out


def _unescape(s: str) -> str:
    import html
    return html.unescape(s or "")
