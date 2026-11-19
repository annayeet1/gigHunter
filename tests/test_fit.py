"""Title weighting, gap detection, skill context, and fit tiers (fit / reach / out)."""
from gighunter.matcher import score_job, score_title
from gighunter.models import Job, Profile

W = {"skills": .40, "title": .20, "text_similarity": .15, "seniority": .10, "location": .10, "bonus": .05}
ALIASES = {"python": ["py"], "sql": ["t-sql", "postgresql"]}
VOCAB = ["kafka", "apache spark", "terraform", "golang", "reactjs", "figma"]


def prof(**kw):
    base = dict(name="T", target_titles=["BI Developer", "Data Engineer", "Database Administrator"],
                years_experience=2.5, seniority=["junior", "mid"], work_modes=["remote"], locations=[],
                skills={"sql": 3, "python": 2, "powershell": 2, "clarity": 3, "mumps": 2},
                dealbreakers=[], bonus_keywords=[], min_salary_usd=0, body="SQL reporting and PowerShell.",
                skill_context={"clarity": ["epic", "caboodle", "sql"], "mumps": ["epic", "intersystems", "cache"]})
    base.update(kw)
    return Profile(**base)


def job(title="Data Engineer", desc="SQL and Python pipelines, PowerShell automation.", **kw):
    return Job(id="x", title=title, company="C", url="u", description=desc, location="Remote", remote=True, **kw)


def run(p, j, fit=None):
    return score_job(p, j, W, ALIASES, vocab=VOCAB, fit=fit)


def test_generic_title_words_barely_count():
    p = prof()
    assert score_title(p, "UI Developer") < 0.25          # only 'developer' shared with 'BI Developer'
    assert score_title(p, "Software Engineer") < 0.25
    assert score_title(p, "Data Engineer II") == 1.0
    assert score_title(p, "Business Data Engineer") == 1.0


def test_good_listing_is_fit():
    r = run(prof(), job())
    assert r.tier == "fit" and not r.excluded_reason and r.score > 0


def test_wrong_role_family_is_out():
    r = run(prof(), job(title="Telehealth Endocrinologist", desc="Clinical care. Clarity of communication."))
    assert r.tier == "out" and r.score == 0 and "role family" in r.excluded_reason


def test_listing_full_of_skills_you_lack_is_out():
    r = run(prof(), job(desc="Kafka, Apache Spark, Terraform and Golang required. Some SQL."))
    assert r.tier == "out" and "missing most required skills" in r.excluded_reason
    assert {"kafka", "apache spark", "terraform", "golang"} <= set(r.missing_skills)


def test_one_minor_gap_is_still_fit_but_several_are_reach():
    assert run(prof(), job(desc="SQL, Python and PowerShell. Kafka a plus.")).tier == "fit"   # 7/(7+2) = 78%
    r = run(prof(), job(desc="SQL, Python and PowerShell, plus Kafka, Terraform and Golang."))  # 7/(7+6) = 54%
    assert r.tier == "reach" and not r.excluded_reason


def test_senior_is_reach_by_default_and_out_when_configured():
    assert run(prof(), job(title="Senior Data Engineer")).tier == "reach"
    r = run(prof(), job(title="Senior Data Engineer"), fit={"max_level_gap_up": 0})
    assert r.tier == "out" and r.score == 0
    assert run(prof(), job(title="Principal Data Engineer")).tier == "out"
    assert run(prof(), job(title="Data Engineering Intern")).tier == "out"


def test_years_required():
    assert run(prof(), job(desc="SQL, Python, PowerShell. 5+ years of experience.")).tier == "reach"
    assert run(prof(), job(desc="SQL, Python, PowerShell. 8+ years of experience.")).tier == "out"


def test_skill_context_blocks_ordinary_words():
    r = run(prof(), job(desc="Write with clarity. MMR vaccine (measles, mumps, rubella) required. Python."))
    assert "clarity" not in r.matched_skills and "mumps" not in r.matched_skills
    r = run(prof(), job(desc="Build Epic Clarity reports in SQL; MUMPS on InterSystems Cache."))
    assert {"clarity", "mumps", "sql"} <= set(r.matched_skills)


def test_vocab_never_adds_to_score_for_skills_you_have():
    # a vocab term you list as a skill counts as matched, not missing
    p = prof(skills={**prof().skills, "kafka": 2})
    r = run(p, job(desc="SQL, Python and Kafka."))
    assert "kafka" in r.matched_skills and "kafka" not in r.missing_skills
