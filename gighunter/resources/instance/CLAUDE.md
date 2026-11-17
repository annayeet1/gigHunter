# gigHunter workspace

Private job-hunt workspace for the gigHunter engine (https://github.com/annayeet1/gigHunter).
CLI: `python -m gighunter --help` (run from this folder).

## Before writing or editing any resume or cover letter
Run `python -m gighunter guidelines` and follow it: the sourced resume and cover-letter rules.

## Workflows
To build a resume, tailor to a job, or tune the match score, print the instructions and follow them:
- `python -m gighunter workflow build-resume`: build or refresh the master resume
- `python -m gighunter workflow tailor`: tailor a resume and cover letter to one listing
- `python -m gighunter workflow tune-score`: calibrate the match score to your ratings

With the gighunter Claude Code plugin installed, `/gighunter:build-resume`, `/gighunter:tailor` and
`/gighunter:tune-score` load these same instructions. Without the plugin (for example where third-party
plugins need approval), use the commands above. Nothing extra gets installed either way.

## Rules
- aboutme.md = facts (the only truth source for resumes). JobParams.md = preferences, never evidence.
- Never invent experience, metrics, dates or credentials. Ask the user, then record new facts in aboutme.md.
- Generated output goes in resume/<YYYY-MM-DD-company-role>/ (master resume in resume/master/).
