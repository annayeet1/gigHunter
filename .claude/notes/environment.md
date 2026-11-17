# Environment gotchas
- Local pip is pointed at artifactory.epic.com; when it's unreachable, feedparser/pytest can't install.
  feedparser is imported lazily in sources/rss.py so everything else still runs. Actions uses public PyPI.
- GitHub Actions cron is UTC-only and can't read config, so the instance workflow runs hourly at :55 and
  `gighunter/schedule.py` (stdlib + tomllib only) decides whether a send is due. The gate installs the engine with
  `--no-deps`, so `workspace.py` and `schedule.py` must stay dependency-free.
  Hourly is about 720 Action minutes/month (2,000 free on private repos).
- Plugin: `claude plugin validate .` and `claude plugin validate ./plugin` both pass.
  One-step install on Claude Code 2.1.275+: `/plugin install gighunter --marketplace annayeet1/gigHunter`.
- FocusGTS blocks automated fetches (403 Vercel checkpoint); use the Wayback Machine copy.
- In this Claude Code Bash tool, heredocs containing apostrophes can fail to parse; write files with the Write tool.
