# gigHunter

Scan job boards, score every listing against **your** profile, get a daily email with the best
new matches, and use Claude Code to build and tailor resumes and cover letters that **never invent
experience**.

This repo is the **engine** (Python package + Claude Code plugin). Your personal data lives in your own
**private workspace repo**, which you create with `gighunter init`.

```
annayeet1/gigHunter (public)        you/gigHunter-me (private)
├─ gighunter/   engine     ──pip──▶ ├─ aboutme.md      facts about you
├─ plugin/      Claude skills       ├─ JobParams.md    what you want
└─ templates for `init`             ├─ config/         sites, schedule, overrides
                                    ├─ resume/         generated resumes + cover letters
                                    └─ .github/        daily digest workflow
```

## Quick start
1. **Install the engine** (Python 3.11+):
   `pip install "gighunter @ git+https://github.com/annayeet1/gigHunter"`
2. **Create your workspace:** `python -m gighunter init ~/gigHunter-me`
3. **Install the Claude Code plugin:** in Claude Code run
   `/plugin install gighunter --marketplace annayeet1/gigHunter`
   (older versions: `/plugin marketplace add annayeet1/gigHunter`, then `/plugin install gighunter@gighunter`)
4. Open Claude Code **in your workspace folder** and run `/gighunter:build-resume`. It interviews you,
   reads any resumes you put in `source_resumes/`, and fills in `aboutme.md`.
5. Edit `JobParams.md` (titles, level, locations, salary, dealbreakers), `config/sites.yaml` (sources)
   and `config/schedule.toml` (send time + minimum match %).
6. **Daily email:** push the workspace to a **private** GitHub repo, then pick one:
   - **Resend (recommended, most secure):** sign up at [resend.com](https://resend.com), create an API key with
     **Sending access** only (it can send mail and nothing else), add it as the secret `RESEND_API_KEY`, and set
     `email.to` in `config/settings.yaml` to the address you signed up with. No domain needed.
   - **SMTP:** secrets `SMTP_USER` and `SMTP_PASSWORD`. A Gmail app password grants *full mailbox access*, so
     use a dedicated sending account if you go this way. Other providers: set `smtp_host`/`smtp_port`. Test with Actions → daily-digest → Run workflow → *force*.

## Claude Code skills
| Skill | What it does |
|---|---|
| `/gighunter:build-resume` | Interviews you role by role, grows `aboutme.md`, and writes `resume/master/` with a source for every bullet |
| `/gighunter:tailor <url or text>` | Fit report (score, requirements vs. evidence), questions, drafts, review rounds, then the resume + cover letter in `resume/<date-company-role>/` |
| `/gighunter:tune-score` | You rate real listings strong/maybe/no; it fits the score weights and suggests a threshold and alias fixes |

**No plugin? Same workflows:** where third-party plugins aren't allowed, ask Claude to follow
`python -m gighunter workflow build-resume` (or `tailor`, `tune-score`). The plugin skills load the same text.

## CLI
`python -m gighunter --help`: `init`, `scan`, `digest`, `score`, `fetch-jd`, `render`, `extract`,
`guidelines`, `workflow`, `config`, `label`, `tune`. `python -m gighunter.schedule` shows whether a digest is due.

## How the match score works
`score = 100 × sum(weight × component)`, with components skills (40%), title (20%), text similarity (15%),
seniority (10%), location (10%) and bonus keywords (5%). Dealbreakers and below-minimum salaries are dropped.
Details are in `gighunter/matcher.py`. Tune it with `/gighunter:tune-score` or `config/settings.yaml`.

## Job sources
Only public APIs and feeds: Greenhouse, Lever and Ashby company boards, RemoteOK, Himalayas, Jobicy, and any RSS feed.
Remote listings limited to other countries are filtered by `remote_regions` (JobParams.md; default: US).
Sites that forbid scraping (LinkedIn, Indeed, Glassdoor) are deliberately not supported.

## Resume guidelines
`python -m gighunter guidelines`. The rules are drawn from Harvard FAS Career Services and FocusGTS and
tagged per rule. PRs that add sources are welcome.

## Development
`pip install -e ".[dev]"` then `pytest`. The `GIGHUNTER_HOME` env var points the CLI at a workspace.
License: MIT.
