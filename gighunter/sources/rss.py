import hashlib
from datetime import datetime, timezone



from ..models import Job
from ..text import html_to_text
from ._http import get_text


def fetch(cfg: dict) -> list[Job]:
    import feedparser  # lazy: only needed when an rss source is enabled
    feed = feedparser.parse(get_text(cfg["url"]))
    out = []
    for e in feed.entries:
        title = e.get("title", "")
        company = cfg.get("company", "")
        if not company and ": " in title:      # WWR style "Company: Title"
            company, title = title.split(": ", 1)
        link = e.get("link", "")
        t = e.get("published_parsed") or e.get("updated_parsed")
        out.append(Job(
            id=f"rss:{hashlib.sha1(link.encode()).hexdigest()[:16]}", title=title,
            company=company, url=link,
            description=html_to_text(e.get("summary", "")),
            location=e.get("region", "") or cfg.get("location", ""),
            remote=cfg.get("remote"),
            posted=datetime(*t[:6], tzinfo=timezone.utc) if t else None,
            source=cfg.get("name", "rss"),
        ))
    return out
