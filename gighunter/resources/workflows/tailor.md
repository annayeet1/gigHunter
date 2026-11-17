<!-- gigHunter workflow 'tailor'. Shipped with the engine; print it with
     `python -m gighunter workflow tailor`. The Claude Code plugin skill
     /gighunter:tailor loads this same text. -->

# Tailor resume + cover letter to a listing (interactive)

## Hard rules
- **Never invent or inflate** anything: employers, titles, dates, metrics, tools, degrees, certifications.
  Only use `aboutme.md`, `source_resumes/`, `resume/master/`, and facts the user states in this session.
- New facts from the user go into **`aboutme.md` first** (show the change, get an OK).
- `JobParams.md` is preferences: use it for motivation and fit in the cover letter, never as evidence.
- Mirror the listing's keywords **only where the experience is real**. If a must-have has no evidence, say so.
- Follow `python -m gighunter guidelines` (read it before drafting).

## 0. Preflight
Run `python -m gighunter --version` (`python3` on macOS/Linux). If it's missing, install with
`pip install "gighunter @ git+https://github.com/annayeet1/gigHunter"`. Then run
`python -m gighunter config` to confirm the workspace. If aboutme.md is mostly TODOs, suggest
the `build-resume` workflow (`/gighunter:build-resume` or `python -m gighunter workflow build-resume`) first.

## 1. Capture the listing
Slug: `YYYY-MM-DD-<company>-<role>` (lowercase, hyphens).
- URL: `python -m gighunter fetch-jd <url> --out resume/<slug>/job_description.md`. If it warns about
  little text (JavaScript pages such as Workday), ask the user to paste the description and save it there.
- Pasted text: save it to that path yourself, with a `Source:` line.

## 2. Score + fit report (show the user)
`python -m gighunter score --file resume/<slug>/job_description.md --title "<title>" --company "<company>"`
Then present a short **fit report**:
- the score and its components
- a requirements table: each must-have and nice-to-have, with its evidence (source) or **no evidence**
- an honest take: strong fit, stretch, or long shot, and why

Ask with AskUserQuestion: **resume + cover letter / resume only / skip this one**.

## 3. Clarify (one round, at most 4 questions)
Only ask what would materially change the result: missing metrics for the most relevant work, which
project best shows a must-have, adjacent experience you can't see in the files, how to frame a gap,
the hiring manager's name, and why this company (for the cover letter). Update aboutme.md with new facts.

## 4. Draft
- `resume/<slug>/resume.md`: start from `resume/master/resume.md` if it exists, otherwise from the sources.
  Reorder sections and bullets by relevance, put the listing's must-have skills first in Technical Skills,
  trim what's irrelevant, and keep it to the guideline length.
- `resume/<slug>/cover_letter.md`: one page, same header. Opening (role + where found), 1-2 evidence
  paragraphs tied to the listing's top requirements, "why this company" from JobParams.md and the user's
  answers, and a thank-you close.

## 5. Review rounds
Show a compact summary: what you emphasized, keywords covered, and keywords **not claimed** (no evidence).
Ask: **approve / revise (say what) / show full text**. Repeat until approved.

## 6. Finish
- `resume/<slug>/notes.md`: score breakdown, the requirements-to-evidence table, the Q&A from this session,
  and the source of each bullet.
- `python -m gighunter render resume/<slug>/resume.md` and the same for `cover_letter.md`.
- Self-check: every bullet traces to a source, no pronouns, consistent dates, length fits the guideline.
- Give the file paths and offer to commit `resume/<slug>/` (plus aboutme.md if it changed).
