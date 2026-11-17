import tempfile
from pathlib import Path

from gighunter.profile import load_profile

ABOUT = """---
name: T
years_experience: 4
current_seniority: mid
skills: {python: 3, TODO-x: 1}
target_titles: [Legacy Title]
---
Built Python things.
"""
PARAMS = """---
target_titles: [Data Engineer, "TODO: other"]
target_seniority: senior
work_modes: [remote]
dealbreakers: [Clearance Required]
min_salary_usd: 120000
---
# My Ideal Job
> instructions line
Mission-driven healthcare data team. TODO fill more
"""


def _write(d, name, text):
    p = Path(d) / name
    p.write_text(text, encoding="utf-8")
    return p


def test_jobparams_merged_and_overrides():
    with tempfile.TemporaryDirectory() as d:
        p = load_profile(_write(d, "a.md", ABOUT), _write(d, "j.md", PARAMS))
    assert p.target_titles == ["Data Engineer"]          # JobParams wins, TODO dropped
    assert p.seniority == ["senior"]                     # target level used for matching
    assert p.years_experience == 4 and p.skills == {"python": 3}
    assert p.dealbreakers == ["clearance required"] and p.min_salary_usd == 120000
    assert "TODO" not in p.ideal_job                   # placeholder lines ignored
    assert "instructions line" not in p.ideal_job and "Ideal Job" in p.ideal_job


def test_missing_jobparams_falls_back_to_aboutme():
    with tempfile.TemporaryDirectory() as d:
        p = load_profile(_write(d, "a.md", ABOUT), Path(d) / "nope.md")
    assert p.target_titles == ["Legacy Title"] and p.seniority == ["mid"]


BANNER_ABOUT = """---
# ---------------------------------------------------------------------------
# a banner comment full of dashes, like the real template
# ---------------------------------------------------------------------------
name: T
skills:
  sql: 3
  python: 2
---

# About Me
Body text --- with dashes inline.
"""


def test_front_matter_ignores_dashes_in_comments():
    with tempfile.TemporaryDirectory() as d:
        p = load_profile(_write(d, "a.md", BANNER_ABOUT), Path(d) / "none.md")
    assert p.skills == {"sql": 3, "python": 2}
    assert "Body text --- with dashes inline." in p.body


def test_real_template_parses():
    from gighunter.profile import read_front_matter
    from gighunter.workspace import resource
    for name in ("aboutme.md", "JobParams.md"):
        fm, body = read_front_matter(resource("instance", name))
        assert isinstance(fm, dict) and fm, name      # banner must not swallow the YAML
    assert "target_titles" in read_front_matter(resource("instance", "JobParams.md"))[0]
