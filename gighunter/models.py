from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Job:
    id: str                      # stable unique id: "<source>:<native id>"
    title: str
    company: str
    url: str
    description: str = ""        # plain text
    location: str = ""
    remote: bool | None = None
    posted: datetime | None = None
    source: str = ""
    salary_min: int | None = None
    salary_max: int | None = None
    tags: list[str] = field(default_factory=list)
    remote_regions: list[str] = field(default_factory=list)   # countries/regions a remote job is limited to; [] = unrestricted/unknown


@dataclass
class Profile:
    name: str
    target_titles: list[str]
    years_experience: float
    seniority: list[str] | str      # accepted level(s), e.g. ["junior", "mid"]
    work_modes: list[str]
    locations: list[str]
    skills: dict[str, int]       # skill -> weight 1..3
    dealbreakers: list[str]
    bonus_keywords: list[str]
    min_salary_usd: int
    body: str                    # aboutme.md free-form markdown (facts)
    ideal_job: str = ""          # JobParams.md free-form markdown (preferences)
    raw: dict = field(default_factory=dict)
    skill_context: dict[str, list[str]] = field(default_factory=dict)
    remote_regions: list[str] = field(default_factory=lambda: ["united states", "usa", "us", "north america", "americas", "worldwide", "anywhere", "global"])   # skill -> words, one of which must also appear


@dataclass
class MatchResult:
    job: Job
    score: float                         # 0-100
    breakdown: dict[str, float]          # component -> 0..1
    matched_skills: list[str]
    missing_skills: list[str]
    excluded_reason: str | None = None
    tier: str = "fit"                      # fit | reach | out
    tier_reasons: list[str] = field(default_factory=list)
    raw_score: float = 0.0                 # score before exclusion (for explaining 'out' listings)
