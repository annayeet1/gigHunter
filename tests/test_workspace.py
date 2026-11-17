import json
import os
import tempfile
from pathlib import Path

from gighunter import cli, workspace


class _Home:
    """Create a fresh workspace with `init` and point GIGHUNTER_HOME at it."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "ws"
        cli.main(["init", str(self.path)])
        self.old = os.environ.get("GIGHUNTER_HOME")
        os.environ["GIGHUNTER_HOME"] = str(self.path)
        return self.path

    def __exit__(self, *exc):
        if self.old is None:
            os.environ.pop("GIGHUNTER_HOME", None)
        else:
            os.environ["GIGHUNTER_HOME"] = self.old
        self.tmp.cleanup()


def test_init_creates_instance_with_dotfiles():
    with _Home() as ws:
        for rel in ["aboutme.md", "JobParams.md", "config/schedule.toml", "config/sites.yaml",
                    ".gitignore", ".gitattributes", ".github/workflows/daily-digest.yml", ".github/dependabot.yml",
                    "resume/.gitkeep", "data/seen_jobs.json", "CLAUDE.md"]:
            assert (ws / rel).exists(), rel
        assert not list(ws.rglob("dot-*"))
        assert workspace.home() == ws.resolve()


def test_init_never_overwrites():
    with _Home() as ws:
        (ws / "aboutme.md").write_text("---\nname: Mine\n---\nkeep me", encoding="utf-8")
        cli.main(["init", str(ws)])
        assert "keep me" in (ws / "aboutme.md").read_text(encoding="utf-8")


def test_layered_settings_and_aliases():
    from gighunter.profile import load_aliases, load_settings
    with _Home() as ws:
        (ws / "config" / "settings.yaml").write_text(
            "weights: {skills: 0.5, title: 0.1, text_similarity: 0.15, seniority: 0.1, location: 0.1, bonus: 0.05}\n",
            encoding="utf-8")
        (ws / "config" / "skill_aliases.yaml").write_text("python: [python3]\nepic: [epic systems]\n", encoding="utf-8")
        s = load_settings()
        assert s["weights"]["skills"] == 0.5 and s["email"]["smtp_host"] == "smtp.gmail.com"  # default kept
        a = load_aliases()
        assert "py" in a["python"] and "python3" in a["python"] and a["epic"] == ["epic systems"]


def test_tune_learns_from_labels():
    from gighunter import tune
    from gighunter.profile import load_aliases, load_profile, load_settings
    with _Home() as ws:
        (ws / "aboutme.md").write_text(
            "---\nname: T\nyears_experience: 5\nskills: {python: 3, sql: 3}\n---\nPython SQL data pipelines.\n",
            encoding="utf-8")
        (ws / "JobParams.md").write_text(
            "---\ntarget_titles: [Data Engineer]\nwork_modes: [remote]\n---\n", encoding="utf-8")

        def job(i, title, desc):
            return {"id": f"t:{i}", "title": title, "company": "C", "url": "u", "description": desc,
                    "location": "Remote", "remote": True, "posted": None, "source": "t",
                    "salary_min": None, "salary_max": None, "tags": []}
        # The user cares about skills, not titles: title-matching jobs without the skills are "no".
        rows = [
            {"rating": "strong", "job": job(1, "Analytics Developer", "Python and SQL pipelines daily.")},
            {"rating": "strong", "job": job(2, "Platform Developer", "Heavy SQL, Python tooling.")},
            {"rating": "no", "job": job(3, "Data Engineer", "Java, Scala, Spark, Kafka only.")},
            {"rating": "no", "job": job(4, "Senior Data Engineer", "Golang and Rust services.")},
        ]
        (ws / "data" / "labels.jsonl").write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        res = tune.fit(load_profile(), load_settings(), load_aliases())
        assert res["accuracy_after"] >= res["accuracy_before"]
        assert res["accuracy_after"] == 1.0
        assert res["suggested"]["title"] <= res["current"]["title"]
        assert abs(sum(res["suggested"].values()) - 1.0) < 1e-6
        tune.apply_weights(res["suggested"])
        assert load_settings()["weights"] == {k: round(v, 2) for k, v in res["suggested"].items()}
