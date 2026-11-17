"""Locate the user's gigHunter workspace (their private instance) and the engine's bundled resources.

STANDARD LIBRARY ONLY: imported by the schedule gate, which runs before dependencies are installed.

Workspace = GIGHUNTER_HOME if set, else the nearest folder at or above the current directory that
contains aboutme.md or config/schedule.toml.
"""
from __future__ import annotations

import os
from pathlib import Path

PKG = Path(__file__).resolve().parent
RESOURCES = PKG / "resources"
MARKERS = ("aboutme.md", "config/schedule.toml")


class NoWorkspace(SystemExit):
    pass


def home() -> Path:
    env = os.environ.get("GIGHUNTER_HOME")
    if env:
        return Path(env).expanduser().resolve()
    cur = Path.cwd().resolve()
    for d in (cur, *cur.parents):
        if any((d / m).exists() for m in MARKERS):
            return d
    raise NoWorkspace(
        "No gigHunter workspace found here or in any parent folder.\n"
        "Create one with:  python -m gighunter init <folder>   (or set GIGHUNTER_HOME)")


def path(*parts: str) -> Path:
    return home().joinpath(*parts)


def resource(*parts: str) -> Path:
    return RESOURCES.joinpath(*parts)
