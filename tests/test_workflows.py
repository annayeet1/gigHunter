"""Workflow instructions ship in the package; plugin skills are thin pointers to them."""
import contextlib
import io
import re
from pathlib import Path

from gighunter import cli, workspace

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted(p.parent.name for p in (ROOT / "plugin" / "skills").glob("*/SKILL.md"))


def _run(*argv) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main(list(argv))
    return buf.getvalue()


def test_every_plugin_skill_has_a_packaged_workflow():
    assert SKILLS == cli.workflow_names() == ["build-resume", "tailor", "tune-score"]


def test_plugin_skills_are_thin_pointers():
    for name in SKILLS:
        text = (ROOT / "plugin" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert re.search(rf"^name: {re.escape(name)}$", text, re.M)
        assert f"python -m gighunter workflow {name}" in text
        assert len(text) < 1500, f"{name} SKILL.md should point at the workflow, not duplicate it"


def test_workflow_command_prints_full_instructions():
    for name in SKILLS:
        out = _run("workflow", name)
        assert "Never invent" in out or "Don't change aboutme.md skills" in out, name
        assert "## 0. Preflight" in out
    assert "tailor" in _run("workflow")


def test_workflows_reference_siblings_both_ways():
    text = workspace.resource("workflows", "build-resume.md").read_text(encoding="utf-8")
    assert "python -m gighunter workflow tailor" in text


def test_template_claude_md_points_at_guidelines_and_workflows():
    text = workspace.resource("instance", "CLAUDE.md").read_text(encoding="utf-8")
    assert "python -m gighunter guidelines" in text
    for name in SKILLS:
        assert f"python -m gighunter workflow {name}" in text
