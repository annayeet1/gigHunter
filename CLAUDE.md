# gigHunter engine: notes for Claude sessions

This repo is the PUBLIC engine. **No personal data belongs here**: user data lives in private
workspaces created by `gighunter init` (the maintainer's is annayeet1/gigHunter-me).

## Layout
- `gighunter/`: package. `workspace.py` finds the user's workspace (GIGHUNTER_HOME or the nearest parent
  folder with aboutme.md / config/schedule.toml); everything user-specific is read through it.
- `gighunter/resources/defaults/`: default settings.yaml + skill_aliases.yaml (workspace files overlay these).
- `gighunter/resources/instance/`: templates copied by `init`; the `dot-` prefix becomes `.`.
- `gighunter/resources/resume_guidelines.md`: sourced rules, printed by `gighunter guidelines`.
- `plugin/`: Claude Code plugin (skills build-resume, tailor, tune-score); `.claude-plugin/marketplace.json` lists it.
- `.claude/notes/`: gotchas, one topic per file.

## Rules
- Resume skills must never invent experience; aboutme.md is the truth source, JobParams.md is preferences only.
- `workspace.py` and `schedule.py` must stay **stdlib-only**: the workflow gate runs them with `--no-deps`.
- Job sources: public APIs and feeds only.
- `.github/workflows/digest.yml` is a REUSABLE workflow that workspaces call at a version tag; workspace
  Dependabot opens PRs when a new tag appears. Its `ENGINE_REF` must equal the tag it ships in.

## Release checklist
1. Bump the version in: pyproject.toml, gighunter/__init__.py, plugin/.claude-plugin/plugin.json,
   .claude-plugin/marketplace.json, digest.yml `ENGINE_REF`, and the template caller
   (resources/instance/dot-github/workflows/daily-digest.yml `@vX.Y.Z`). `tests/test_release.py` checks they agree.
2. Commit, then `git tag vX.Y.Z && git push origin main vX.Y.Z`. CI rejects a tag that doesn't match.
3. Never move or delete a published tag; workspaces depend on it.
- Validate the plugin with `claude plugin validate .` and `claude plugin validate ./plugin`.
