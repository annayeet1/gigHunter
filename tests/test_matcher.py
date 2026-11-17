from gighunter.matcher import score_job
from gighunter.models import Job, Profile

W = {"skills": .40, "title": .20, "text_similarity": .15, "seniority": .10, "location": .10, "bonus": .05}
ALIASES = {"kubernetes": ["k8s"], "python": ["py"], "go": ["golang"]}


def prof(**kw):
    base = dict(name="T", target_titles=["Software Engineer"], years_experience=5, seniority="mid",
                work_modes=["remote"], locations=[], skills={"python": 3, "sql": 2, "kubernetes": 1},
                dealbreakers=["security clearance"], bonus_keywords=["healthcare"], min_salary_usd=0,
                body="Built Python data pipelines and SQL reporting for healthcare analytics.")
    base.update(kw)
    return Profile(**base)


def job(**kw):
    base = dict(id="x", title="Software Engineer", company="Co", url="u", location="Remote", remote=True,
                description="We need Python and SQL. K8s a plus. Healthcare analytics pipelines.")
    base.update(kw)
    return Job(**base)


def test_strong_match_scores_high():
    r = score_job(prof(), job(), W, ALIASES)
    assert r.score >= 75, r.breakdown
    assert set(r.matched_skills) == {"python", "sql", "kubernetes"}  # k8s alias counted


def test_dealbreaker_excludes():
    r = score_job(prof(), job(description="Active security clearance required. Python."), W, ALIASES)
    assert r.excluded_reason and r.score == 0


def test_missing_skill_lowers_score():
    a = score_job(prof(), job(), W, ALIASES).score
    b = score_job(prof(), job(description=job().description + " Golang required."), W, ALIASES)
    assert b.score < a and "go" in b.missing_skills


def test_onsite_elsewhere_scores_location_zero():
    r = score_job(prof(), job(location="Austin, TX", remote=False), W, ALIASES)
    assert r.breakdown["location"] == 0


def test_senior_title_penalised_for_junior():
    r = score_job(prof(seniority="junior"), job(title="Senior Software Engineer"), W, ALIASES)
    assert r.breakdown["seniority"] < 1


def test_seniority_range():
    rng = prof(seniority=["junior", "mid"])
    assert score_job(rng, job(title="Junior Data Engineer"), W, ALIASES).breakdown["seniority"] == 1.0
    assert score_job(rng, job(title="Data Engineer"), W, ALIASES).breakdown["seniority"] == 1.0   # unlabeled = mid
    assert score_job(rng, job(title="Senior Data Engineer"), W, ALIASES).breakdown["seniority"] == 0.6
    assert score_job(rng, job(title="Principal Data Engineer"), W, ALIASES).breakdown["seniority"] == 0.2


def test_single_level_string_still_works():
    r = score_job(prof(seniority="senior"), job(title="Senior Data Engineer"), W, ALIASES)
    assert r.breakdown["seniority"] == 1.0
