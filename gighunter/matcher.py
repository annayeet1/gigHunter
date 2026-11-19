"""Match-score formula (v1).

score = 100 * sum(weight_i * component_i), each component in 0..1.
Weights live in config/settings.yaml. Hard filters run first and drop the job.

Components
----------
skills           Weighted coverage of the skills the listing asks for (that we can recognise),
                 scaled down when only a little evidence was found.
title            Best token overlap between the listing title and any target title.
text_similarity  Cosine similarity of aboutme.md body + JobParams.md "ideal job" text vs the listing (rescaled).
seniority        Listing level vs. your accepted level(s): inside the range = 1.0, one level
                 outside = 0.6, further = 0.2. Unlabeled titles count as mid. Penalized when
                 required years exceed yours by more than one.
location         Remote/hybrid/onsite fit with your work_modes and locations.
bonus            Hits on bonus_keywords (2 hits = full credit).

Hard filters: dealbreaker phrase present; known salary max below min_salary_usd.
"""
from __future__ import annotations

import re

from .models import Job, MatchResult, Profile
from .text import cosine, phrase_in, tokens

LEVELS = ["intern", "junior", "mid", "senior", "staff", "principal"]
_LEVEL_WORDS = {
    "intern": "intern", "internship": "intern",
    "junior": "junior", "jr": "junior", "entry": "junior", "associate": "junior", "graduate": "junior",
    "senior": "senior", "sr": "senior", "lead": "senior",
    "staff": "staff", "principal": "principal", "distinguished": "principal", "architect": "staff",
}
_TITLE_NOISE = set(_LEVEL_WORDS) | {"i", "ii", "iii", "iv", "remote", "hybrid", "us", "usa"}
_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years|yrs)", re.I)
UNKNOWN_SKILL_WEIGHT = 2  # weight given to a recognised skill you don't have


def _skill_terms(skill: str, aliases: dict[str, list[str]]) -> list[str]:
    terms = [skill]
    for canon, alist in aliases.items():
        names = [canon.lower()] + [a.lower() for a in alist]
        if skill in names:
            terms = list(dict.fromkeys([skill] + names))
            break
    return terms


def score_skills(profile: Profile, text_lower: str, aliases: dict) -> tuple[float, list[str], list[str]]:
    matched, matched_w = [], 0
    for skill, w in profile.skills.items():
        if any(phrase_in(t, text_lower) for t in _skill_terms(skill, aliases)):
            matched.append(skill)
            matched_w += w
    have = {t for s in profile.skills for t in _skill_terms(s, aliases)}
    missing = [canon for canon, alist in aliases.items()
               if canon.lower() not in have
               and any(phrase_in(t, text_lower) for t in [canon] + list(alist))]
    denom = matched_w + UNKNOWN_SKILL_WEIGHT * len(missing)
    if denom == 0:
        return 0.0, matched, missing
    coverage = matched_w / denom
    confidence = min(1.0, matched_w / 6)       # ~2 core skills = full confidence
    return coverage * (0.5 + 0.5 * confidence), matched, missing


def _title_tokens(t: str) -> set[str]:
    return {x for x in tokens(t) if x not in _TITLE_NOISE}


def score_title(profile: Profile, title: str) -> float:
    jt = _title_tokens(title)
    best = 0.0
    for target in profile.target_titles:
        tt = _title_tokens(target)
        if tt:
            best = max(best, len(tt & jt) / len(tt))
    return best


def job_level(job: Job) -> str | None:
    for w in tokens(job.title):
        if w in _LEVEL_WORDS:
            return _LEVEL_WORDS[w]
    return None


def score_seniority(profile: Profile, job: Job) -> float:
    wanted = profile.seniority if isinstance(profile.seniority, (list, tuple)) else [profile.seniority]
    wanted = [w for w in wanted if w in LEVELS] or ["mid"]
    lvl = job_level(job) or "mid"          # titles without a level word are usually mid-level roles
    gap = min(abs(LEVELS.index(lvl) - LEVELS.index(w)) for w in wanted)
    s = {0: 1.0, 1: 0.6}.get(gap, 0.2)
    years = [int(y) for y in _YEARS.findall(job.description)[:3]]
    if years and profile.years_experience:
        need = min(years)
        if need > profile.years_experience + 1:
            s *= max(0.2, 1 - 0.15 * (need - profile.years_experience))
    return s


US_STATES = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california",
    "CO": "colorado", "CT": "connecticut", "DE": "delaware", "DC": "district of columbia",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho", "IL": "illinois",
    "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana",
    "ME": "maine", "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
    "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new hampshire", "NJ": "new jersey", "NM": "new mexico", "NY": "new york",
    "NC": "north carolina", "ND": "north dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon",
    "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina", "SD": "south dakota",
    "TN": "tennessee", "TX": "texas", "UT": "utah", "VT": "vermont", "VA": "virginia",
    "WA": "washington", "WV": "west virginia", "WI": "wisconsin", "WY": "wyoming",
}
_NAME_TO_ABBR = {v: k for k, v in US_STATES.items()}
_ABBR_WORD = re.compile(r"\b([A-Z]{2})\b")


def _states_in(location: str) -> set[str]:
    """US states named in a listing location, as abbreviations. Abbreviations must be
    uppercase ('IN', 'OR'), so ordinary words like 'in' or 'or' don't count."""
    found = {a for a in _ABBR_WORD.findall(location) if a in US_STATES}
    low = location.lower()
    found |= {abbr for name, abbr in _NAME_TO_ABBR.items() if phrase_in(name, low)}
    return found


def _state_abbr(text: str) -> str | None:
    t = text.strip()
    return t.upper() if t.upper() in US_STATES else _NAME_TO_ABBR.get(t.lower())


def location_matches(want: str, location: str) -> bool:
    """'Verona, WI' = that city in that state (state checked whenever the listing names one).
    'WI' or 'Wisconsin' = anywhere in the state. 'Boston' = any place called Boston.
    Anything after the first comma that isn't a US state (e.g. 'Toronto, Canada') must also appear."""
    parts = [p.strip() for p in want.split(",") if p.strip()]
    if not parts:
        return False
    low = location.lower()
    listed = _states_in(location)
    if len(parts) == 1:
        st = _state_abbr(parts[0])
        return st in listed if st else phrase_in(parts[0].lower(), low)
    city, rest = parts[0], parts[1:]
    if not phrase_in(city.lower(), low):
        return False
    for r in rest:
        st = _state_abbr(r)
        if st:
            if listed and st not in listed:
                return False
        elif not phrase_in(r.lower(), low):
            return False
    return True


def score_location(profile: Profile, job: Job) -> float:
    raw = job.location or ""
    loc = raw.lower()
    remote = job.remote if job.remote is not None else ("remote" in loc or "anywhere" in loc)
    if remote and "remote" in profile.work_modes:
        return 1.0
    if not loc:
        return 0.5
    if {"hybrid", "onsite"} & set(profile.work_modes):
        for want in profile.locations:
            if location_matches(want, raw):
                return 1.0
    return 0.0


def score_bonus(profile: Profile, text_lower: str) -> float:
    if not profile.bonus_keywords:
        return 0.0
    hits = sum(phrase_in(b, text_lower) for b in profile.bonus_keywords)
    return min(1.0, hits / 2)


def hard_filter(profile: Profile, job: Job, text_lower: str) -> str | None:
    for d in profile.dealbreakers:
        if phrase_in(d, text_lower):
            return f"dealbreaker: {d}"
    if profile.min_salary_usd and job.salary_max and job.salary_max < profile.min_salary_usd:
        return f"salary max {job.salary_max} < {profile.min_salary_usd}"
    return None


def score_job(profile: Profile, job: Job, weights: dict, aliases: dict) -> MatchResult:
    text_lower = f"{job.title}\n{job.description}\n{' '.join(job.tags)}".lower()
    reason = hard_filter(profile, job, text_lower)
    skills, matched, missing = score_skills(profile, text_lower, aliases)
    profile_text = " ".join([profile.body, profile.ideal_job, *profile.skills, *profile.target_titles])
    breakdown = {
        "skills": skills,
        "title": score_title(profile, job.title),
        "text_similarity": min(1.0, cosine(profile_text, job.description) / 0.35),
        "seniority": score_seniority(profile, job),
        "location": score_location(profile, job),
        "bonus": score_bonus(profile, text_lower),
    }
    total = sum(weights.get(k, 0) * v for k, v in breakdown.items())
    return MatchResult(job=job, score=0.0 if reason else round(100 * total, 1),
                       breakdown=breakdown, matched_skills=matched,
                       missing_skills=missing, excluded_reason=reason)
