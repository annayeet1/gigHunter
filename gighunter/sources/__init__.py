"""Source adapters. Each exposes fetch(cfg: dict) -> list[Job]."""
from __future__ import annotations

import logging

from ..models import Job
from . import ashby, greenhouse, lever, remoteok, rss

ADAPTERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "remoteok": remoteok.fetch,
    "rss": rss.fetch,
}
log = logging.getLogger(__name__)


def fetch_all(sources: list[dict]) -> list[Job]:
    jobs: list[Job] = []
    for cfg in sources:
        if not cfg.get("enabled", True):
            continue
        fn = ADAPTERS.get(cfg.get("type", ""))
        if not fn:
            log.warning("Unknown source type %r in %s", cfg.get("type"), cfg.get("name"))
            continue
        try:
            got = fn(cfg)
            log.info("%-40s %4d jobs", cfg.get("name"), len(got))
            jobs.extend(got)
        except Exception as e:  # one broken source must not kill the digest
            log.error("Source %s failed: %s", cfg.get("name"), e)
    return jobs
