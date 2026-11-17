"""Every place that names the engine version must agree, so a workspace pinned to
@vX.Y.Z of the reusable workflow installs engine vX.Y.Z."""
import json
import re
import tomllib
from pathlib import Path

import gighunter

ROOT = Path(__file__).resolve().parent.parent


def versions() -> dict[str, str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / "plugin/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    digest = (ROOT / ".github/workflows/digest.yml").read_text(encoding="utf-8")
    caller = (ROOT / "gighunter/resources/instance/dot-github/workflows/daily-digest.yml").read_text(encoding="utf-8")
    return {
        "pyproject.toml": pyproject["project"]["version"],
        "gighunter.__version__": gighunter.__version__,
        "plugin.json": plugin["version"],
        "marketplace.json": market["plugins"][0]["version"],
        "digest.yml ENGINE_REF": re.search(r"ENGINE_REF:\s*v([\d.]+)", digest).group(1),
        "template caller @v": re.search(r"digest\.yml@v([\d.]+)", caller).group(1),
    }


def test_versions_agree():
    v = versions()
    assert len(set(v.values())) == 1, v
