"""Match-score formula (v2: weighted titles, gap vocabulary, fit tiers).

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
Fit tiers (fit_tier): 'out' listings are excluded like hard filters; 'reach' ones are labelled.
Skills can require context in aboutme.md: clarity: {weight: 3, requires_any: [epic, caboodle]}.
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

# Role words that appear in almost every tech title. They count, but far less than the
# distinctive word ("BI", "Data", "Database"), so "UI Developer" barely matches "BI Developer".
GENERIC_TITLE_WORDS = {
    "engineer", "engineering", "developer", "development", "administrator", "admin", "analyst",
    "specialist", "manager", "consultant", "technician", "programmer", "scientist", "officer",
    "coordinator", "associate", "representative", "expert", "professional",
}
GENERIC_WEIGHT = 0.25

# Fit tiers (override any key under `fit:` in config/settings.yaml).
DEFAULT_FIT = {
    "min_title": 0.5,              # below: not your role family -> out of scope
    "min_skill_coverage": 0.35,    # below: missing most recognisable required skills -> out of scope
    "reach_skill_coverage": 0.6,   # below (but above min): noticeable gaps -> reach
    "max_level_gap_up": 1,         # levels above your highest accepted level allowed as a reach
    "reach_years_over": 1,         # required years > yours + this -> reach
    "exclude_years_over": 4,       # required years > yours + this -> out of scope
}


def _skill_terms(skill: str, aliases: dict[str, list[str]]) -> list[str]:
    terms = [skill]
    for canon, alist in aliases.items():
        names = [canon.lower()] + [a.lower() for a in alist]
        if skill in names:
            terms = list(dict.fromkeys([skill] + names))
            break
    return terms


def _skill_present(skill: str, text_lower: str, aliases: dict, context: dict) -> bool:
    if not any(phrase_in(t, text_lower) for t in _skill_terms(skill, aliases)):
        return False
    need = context.get(skill)
    return not need or any(phrase_in(c.lower(), text_lower) for c in need)


def score_skills(profile: Profile, text_lower: str, aliases: dict,
                 vocab: list[str] | None = None) -> tuple[float, list[str], list[str], float | None]:
    """Returns (score, matched, missing, coverage). coverage is None when the listing names no
    skill we can recognise. `vocab` = extra skill names used only to detect gaps."""
    context = getattr(profile, "skill_context", {}) or {}
    matched, matched_w = [], 0
    for skill, w in profile.skills.items():
        if _skill_present(skill, text_lower, aliases, context):
            matched.append(skill)
            matched_w += w
    have = {t for s in profile.skills for t in _skill_terms(s, aliases)}
    candidates = {c.lower(): [c] + list(a) for c, a in aliases.items()}
    for term in vocab or []:
        candidates.setdefault(term.lower(), [term])
    missing = [canon for canon, terms in candidates.items()
               if canon not in have and not ({t.lower() for t in terms} & have)
               and any(phrase_in(t.lower(), text_lower) for t in terms)]
    denom = matched_w + UNKNOWN_SKILL_WEIGHT * len(missing)
    if denom == 0:
        return 0.0, matched, missing, None
    coverage = matched_w / denom
    confidence = min(1.0, matched_w / 6)       # ~2 core skills = full confidence
    return coverage * (0.5 + 0.5 * confidence), matched, missing, coverage


def _title_tokens(t: str) -> set[str]:
    return {x for x in tokens(t) if x not in _TITLE_NOISE}


def _w(tok: str) -> float:
    return GENERIC_WEIGHT if tok in GENERIC_TITLE_WORDS else 1.0


def score_title(profile: Profile, title: str) -> float:
    """Best weighted overlap with any target title. Generic role words weigh 0.25, so a match
    needs the distinctive word: 'UI Developer' vs 'BI Developer' = 0.2, 'Data Engineer II' = 1.0."""
    jt = _title_tokens(title)
    best = 0.0
    for target in profile.target_titles:
        tt = _title_tokens(target)
        if tt:
            best = max(best, sum(_w(t) for t in tt & jt) / sum(_w(t) for t in tt))
    return best


def job_level(job: Job) -> str | None:
    for w in tokens(job.title):
        if w in _LEVEL_WORDS:
            return _LEVEL_WORDS[w]
    return None


def _wanted_levels(profile: Profile) -> list[str]:
    wanted = profile.seniority if isinstance(profile.seniority, (list, tuple)) else [profile.seniority]
    return [w for w in wanted if w in LEVELS] or ["mid"]


def level_gap(profile: Profile, job: Job) -> int:
    """Signed distance from your accepted range: +1 = one level above your highest, -1 = below your lowest."""
    idx = LEVELS.index(job_level(job) or "mid")   # titles without a level word are usually mid-level
    wanted = [LEVELS.index(w) for w in _wanted_levels(profile)]
    if idx > max(wanted):
        return idx - max(wanted)
    if idx < min(wanted):
        return idx - min(wanted)
    return 0


def required_years(job: Job) -> int | None:
    years = [int(y) for y in _YEARS.findall(job.description)[:3]]
    return min(years) if years else None


def score_seniority(profile: Profile, job: Job) -> float:
    s = {0: 1.0, 1: 0.6}.get(abs(level_gap(profile, job)), 0.2)
    need = required_years(job)
    if need is not None and profile.years_experience and need > profile.years_experience + 1:
        s *= max(0.2, 1 - 0.15 * (need - profile.years_experience))
    return s


def fit_tier(profile: Profile, job: Job, title: float, coverage: float | None,
             fit: dict | None = None) -> tuple[str, list[str]]:
    """('fit' | 'reach' | 'out', reasons). 'out' listings are left out of the digest."""
    f = {**DEFAULT_FIT, **(fit or {})}
    out, reach = [], []
    if title < f["min_title"]:
        out.append("not your target role family")
    if coverage is not None and coverage < f["min_skill_coverage"]:
        out.append("missing most required skills")
    elif coverage is not None and coverage < f["reach_skill_coverage"]:
        reach.append("some required skills you don't list")
    gap = level_gap(profile, job)
    if gap > f["max_level_gap_up"]:
        out.append(f"{job_level(job)} level")
    elif gap > 0:
        reach.append(f"{job_level(job)} level")
    elif gap < 0:
        out.append(f"{job_level(job)} level (below your range)")
    need = required_years(job)
    if need is not None and profile.years_experience:
        over = need - profile.years_experience
        if over > f["exclude_years_over"]:
            out.append(f"asks for {need}+ years")
        elif over > f["reach_years_over"]:
            reach.append(f"asks for {need}+ years")
    if out:
        return "out", out
    return ("reach", reach) if reach else ("fit", [])


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


def score_job(profile: Profile, job: Job, weights: dict, aliases: dict,
              vocab: list[str] | None = None, fit: dict | None = None) -> MatchResult:
    text_lower = f"{job.title}\n{job.description}\n{' '.join(job.tags)}".lower()
    reason = hard_filter(profile, job, text_lower)
    skills, matched, missing, coverage = score_skills(profile, text_lower, aliases, vocab)
    title = score_title(profile, job.title)
    profile_text = " ".join([profile.body, profile.ideal_job, *profile.skills, *profile.target_titles])
    breakdown = {
        "skills": skills,
        "title": title,
        "text_similarity": min(1.0, cosine(profile_text, job.description) / 0.35),
        "seniority": score_seniority(profile, job),
        "location": score_location(profile, job),
        "bonus": score_bonus(profile, text_lower),
    }
    total = sum(weights.get(k, 0) * v for k, v in breakdown.items())
    tier, why = fit_tier(profile, job, title, coverage, fit)
    if not reason and tier == "out":
        reason = "out of scope: " + "; ".join(why)
    return MatchResult(job=job, score=0.0 if reason else round(100 * total, 1),
                       breakdown=breakdown, matched_skills=matched,
                       missing_skills=missing, excluded_reason=reason,
                       tier=tier, tier_reasons=why, raw_score=round(100 * total, 1))
