from gighunter.digest import render_html, render_text
from gighunter.models import Job, MatchResult


def _r(title, score, tier, reasons=()):
    j = Job(id=title, title=title, company="Co <b>", url="https://x/?a=1&b=2", location="Remote (USA)", source="Jobicy")
    return MatchResult(job=j, score=score, breakdown={"skills": .8, "title": 1.0, "bonus": 0.0},
                       matched_skills=["sql"], missing_skills=["kafka"], tier=tier, tier_reasons=list(reasons))


def test_sections_tiles_chips_and_escaping():
    out = render_html([_r("BI Developer", 81, "fit"), _r("SQL Developer", 70, "reach", ["asks for 5+ years"])],
                      "Wed Nov 18", 60, scanned=418)
    assert "Strong fits" in out and "Reaches" in out and "418" in out
    assert "&#10003; Fit" in out and "&#9650; Reach" in out          # icon + word, not color alone
    assert "Why it&rsquo;s a reach: asks for 5+ years" in out
    assert "Co &lt;b&gt;" in out and "a=1&amp;b=2" in out           # untrusted listing text is escaped
    assert "<script" not in out and "<svg" not in out                # email-safe
    assert "bonus" not in out.split("Strong fits")[1].split("Reaches")[0]   # zero bonus hidden


def test_empty_state_and_text_version():
    out = render_html([], "Wed", 60, scanned=12)
    assert "No new listings at or above 60%" in out and "Strong fits" not in out
    assert "[REACH]" in render_text([_r("SQL Developer", 70, "reach")])
