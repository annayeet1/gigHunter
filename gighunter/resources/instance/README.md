# My gigHunter workspace

**Keep this repository PRIVATE.** It holds your profile and resumes.
Engine and docs: https://github.com/annayeet1/gigHunter

| File | Purpose |
|---|---|
| `aboutme.md` | Facts about you: skills, years, experience. The only source resumes may draw on. |
| `JobParams.md` | What you want: titles, level, locations, salary, dealbreakers, ideal job |
| `config/sites.yaml` | Job sources to scan |
| `config/schedule.toml` | Email time, days, timezone, **minimum match %** |
| `config/settings.yaml` | Optional overrides (score weights, email recipient) |
| `source_resumes/` | Drop existing resumes here (docx, pdf, md) |
| `resume/` | Generated resumes and cover letters |
| `data/` | Digest state (managed by the workflow) |

In Claude Code, from this folder: `/gighunter:build-resume`, `/gighunter:tailor <job url>`, `/gighunter:tune-score`.
Run `git pull` before editing; the daily workflow commits `data/` back.
