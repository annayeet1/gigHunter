"""Source adapters parse API payloads (no network), and remote-region eligibility works."""
from gighunter.matcher import remote_eligible, score_job
from gighunter.models import Job, Profile
from gighunter.sources import himalayas, jobicy

HIM = {"jobs": [
    {"title": "Data Engineer", "companyName": "Acme", "companySlug": "acme",
     "guid": "https://himalayas.app/companies/acme/jobs/data-engineer",
     "applicationLink": "https://himalayas.app/companies/acme/jobs/data-engineer?ut",
     "description": "<p>SQL and Python.</p>", "locationRestrictions": ["Poland"],
     "pubDate": 1792126270, "minSalary": 90000, "maxSalary": 120000, "currency": "USD",
     "salaryPeriod": "year", "categories": ["Data"]},
    {"title": "BI Developer", "companyName": "Beta", "companySlug": "beta",
     "guid": "https://himalayas.app/companies/beta/jobs/bi-developer",
     "description": "SQL Server, SSAS.", "locationRestrictions": ["United States"],
     "pubDate": 1792126270, "minSalary": 40, "maxSalary": 60, "currency": "USD", "salaryPeriod": "hour"},
]}
JOBICY = {"jobs": [{"id": 7, "url": "https://jobicy.com/jobs/7-dba", "jobTitle": "Database Administrator",
                    "companyName": "Gamma", "jobDescription": "<b>SQL Server</b> DBA", "jobGeo": "USA",
                    "pubDate": "2026-11-18T15:49:14+00:00", "salaryMin": 80000, "salaryMax": 100000}]}


def test_himalayas_parses_and_dedupes(monkeypatch):
    calls = []
    monkeypatch.setattr(himalayas, "get_json", lambda url, **p: calls.append(p) or HIM)
    jobs = himalayas.fetch({"queries": ["data engineer", "bi developer"]})
    assert len(calls) == 2 and len(jobs) == 2                       # same jobs from 2 queries kept once
    de, bi = jobs
    assert de.remote_regions == ["Poland"] and de.location == "Remote (Poland)" and de.salary_max == 120000
    assert bi.salary_max is None                                    # hourly pay isn't used for the salary filter
    assert de.description == "SQL and Python."


def test_jobicy_parses(monkeypatch):
    monkeypatch.setattr(jobicy, "get_json", lambda url, **p: JOBICY)
    (j,) = jobicy.fetch({"tags": ["sql"], "geo": "usa"})
    assert j.title == "Database Administrator" and j.remote_regions == ["USA"] and j.salary_max == 100000
    assert j.url == "https://jobicy.com/jobs/7-dba" and j.source == "Jobicy"


def _p():
    return Profile(name="T", target_titles=["Data Engineer"], years_experience=3, seniority=["mid"],
                   work_modes=["remote"], locations=[], skills={"sql": 3, "python": 2}, dealbreakers=[],
                   bonus_keywords=[], min_salary_usd=0, body="SQL Python")


def test_remote_region_eligibility():
    p = _p()
    mk = lambda regions: Job(id="x", title="Data Engineer", company="c", url="u", description="SQL, Python",
                             remote=True, remote_regions=regions)
    assert remote_eligible(p, mk([])) and remote_eligible(p, mk(["USA"])) and remote_eligible(p, mk(["United States"]))
    assert remote_eligible(p, mk(["US", "Canada"])) and remote_eligible(p, mk(["Worldwide"]))
    assert not remote_eligible(p, mk(["Poland"])) and not remote_eligible(p, mk(["Australia"]))
    W = {"skills": .4, "title": .2, "text_similarity": .15, "seniority": .1, "location": .1, "bonus": .05}
    r = score_job(p, mk(["Poland"]), W, {})
    assert r.tier == "out" and "remote only in Poland" in r.excluded_reason
    assert score_job(p, mk(["USA"]), W, {}).tier == "fit"
