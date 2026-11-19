"""gigHunter command line. Run inside your workspace (or set GIGHUNTER_HOME).

  init FOLDER                      create a new private workspace from the templates
  scan [--top N] [--save]          fetch + score; --save writes data/last_scan.json (for labeling)
  digest [--force] [--dry-run]     email new matches per config/schedule.toml
  score (--url U | --file F)       explain one listing's score
  fetch-jd URL --out PATH          save a job page as plain text
  render PATH.md                   resume/cover-letter Markdown -> ATS-friendly .docx
  extract FILE                     print the text of a .docx/.md/.txt resume
  guidelines                       print the resume/cover-letter rules
  workflow [NAME]                  print a Claude workflow (build-resume, tailor, tune-score)
  config                           print merged settings, schedule and profile summary
  label JOB_ID strong|maybe|no     record your rating of a scanned listing
  tune [--apply]                   fit score weights to your ratings
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__, workspace

log = logging.getLogger("gighunter")


# ---------------------------------------------------------------- helpers
def _ctx():
    from .profile import load_aliases, load_profile, load_settings, load_vocab
    settings = load_settings()
    settings["_vocab"] = load_vocab()      # gap-detection skill list, passed to score_job
    return settings, load_aliases(), load_profile()


def _score(profile, job, settings, aliases):
    from .matcher import score_job
    return score_job(profile, job, settings["weights"], aliases,
                     vocab=settings.get("_vocab"), fit=settings.get("fit"))


def _ranked(settings, aliases, profile, include_out=False):
    from .profile import load_sites
    from .sources import fetch_all
    jobs = fetch_all(load_sites())
    max_age = settings.get("max_listing_age_days")
    if max_age:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age)
        jobs = [j for j in jobs if not j.posted or _aware(j.posted) >= cutoff]
    uniq = {j.id: j for j in jobs}
    results = [_score(profile, j, settings, aliases) for j in uniq.values()]
    if include_out:
        return sorted(results, key=lambda r: -r.raw_score)
    return sorted((r for r in results if not r.excluded_reason), key=lambda r: -r.score)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- commands
def cmd_init(a):
    src = workspace.resource("instance")
    dest = Path(a.folder).expanduser().resolve()
    created, skipped = [], []
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = Path(*[part.replace("dot-", ".", 1) if part.startswith("dot-") else part
                     for part in f.relative_to(src).parts])
        out = dest / rel
        if out.exists():
            skipped.append(rel)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        created.append(rel)
    print(f"Workspace: {dest}\n  created {len(created)} files, kept {len(skipped)} existing")
    print("""
Next:
  1. Fill in aboutme.md (facts) and JobParams.md (what you want); put old resumes in source_resumes/.
  2. Add job sources to config/sites.yaml; set time + threshold in config/schedule.toml.
  3. git init, commit, push to a PRIVATE GitHub repo; add secrets SMTP_USER and SMTP_PASSWORD.
  4. In Claude Code: /gighunter:build-resume, /gighunter:tailor, /gighunter:tune-score (plugin), or without
     the plugin ask Claude to follow `python -m gighunter workflow build-resume` (or tailor, tune-score).""")


def cmd_scan(a):
    settings, aliases, profile = _ctx()
    results = _ranked(settings, aliases, profile, include_out=a.show_out)[: a.top]
    if a.save:
        from .tune import save_scan
        save_scan(results)
    if a.json:
        print(json.dumps([{"id": r.job.id, "score": r.score, "title": r.job.title, "company": r.job.company,
                           "location": r.job.location, "url": r.job.url,
                           "breakdown": {k: round(v, 2) for k, v in r.breakdown.items()},
                           "matched": r.matched_skills, "missing": r.missing_skills,
                           "tier": r.tier, "tier_reasons": r.tier_reasons,
                           "excluded_reason": r.excluded_reason, "raw_score": r.raw_score} for r in results], indent=1))
        return
    for r in results:
        tag = {"fit": "FIT  ", "reach": "REACH", "out": "OUT  "}[r.tier] if not r.excluded_reason or r.tier == "out" else "DROP "
        print(f"{r.raw_score:5.1f} {tag} {r.job.title[:46]:46}  {r.job.company[:20]:20}  {r.job.url}")
        if a.show_out and r.excluded_reason:
            print(f"            {r.excluded_reason}")


def cmd_digest(a):
    from . import digest, store
    from .schedule import is_due, load_schedule
    settings, aliases, profile = _ctx()
    sched = load_schedule()
    now = datetime.now(sched.tz)
    if not a.force and not a.dry_run:
        due, why = is_due(sched, now, store.last_digest_date())
        log.info("Schedule: %s", why)
        if not due:
            return
    seen = store.seen_ids()
    fresh = [r for r in _ranked(settings, aliases, profile)
             if r.job.id not in seen and r.score >= sched.min_match_score][: sched.max_listings]
    day = now.strftime("%a %b %d")
    html_body = digest.render_html(fresh, day, sched.min_match_score)
    if a.dry_run:
        out = workspace.path("digest_preview.html")
        out.write_text(html_body, encoding="utf-8")
        print(f"Wrote {out} with {len(fresh)} listings >= {sched.min_match_score:g}% (nothing sent).")
        return
    if fresh or sched.send_when_empty:
        digest.send(f"gigHunter: {len(fresh)} new matches ({day})", html_body,
                    digest.render_text(fresh), settings["email"])
        log.info("Sent digest with %d listings.", len(fresh))
    else:
        log.info("No listings >= %g%% and send_when_empty=false; no email.", sched.min_match_score)
    store.mark_seen([r.job.id for r in fresh], now.date())
    store.set_last_digest_date(now.date())   # mark today done either way so hourly runs stop


def cmd_score(a):
    from .models import Job
    from .sources._http import get_text
    from .text import html_to_text
    settings, aliases, profile = _ctx()
    text = html_to_text(get_text(a.url)) if a.url else Path(a.file).read_text(encoding="utf-8")
    job = Job(id="adhoc", title=a.title or text.strip().splitlines()[0][:120], company=a.company or "",
              url=a.url or a.file or "", description=text, location=a.location or "")
    r = _score(profile, job, settings, aliases)
    print(f"Match score: {r.raw_score:.1f}%   tier: {r.tier.upper()}"
          + (f"  ({'; '.join(r.tier_reasons)})" if r.tier_reasons else "")
          + (f"\n  EXCLUDED from digest: {r.excluded_reason}" if r.excluded_reason else ""))
    for k, v in r.breakdown.items():
        w = settings["weights"].get(k, 0)
        print(f"  {k:16} {v:5.0%}  x {w:.2f} = {100 * w * v:5.1f}")
    print("  matched skills:", ", ".join(r.matched_skills) or "-")
    print("  gaps:          ", ", ".join(r.missing_skills) or "-")


def cmd_fetch_jd(a):
    from .sources._http import get_text
    from .text import html_to_text
    text = html_to_text(get_text(a.url))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"Source: {a.url}\nFetched: {datetime.now():%Y-%m-%d}\n\n{text}\n", encoding="utf-8")
    print(f"Saved {len(text):,} chars to {out}")
    if len(text) < 800:
        print("WARNING: very little text; the page may need JavaScript. Paste the description instead.")


def cmd_render(a):
    from .render import md_to_docx
    print("Wrote", md_to_docx(Path(a.path)))


def cmd_extract(a):
    p = Path(a.file)
    if p.suffix.lower() == ".docx":
        from docx import Document
        d = Document(p)
        lines = [par.text for par in d.paragraphs]
        for t in d.tables:                      # some resume templates put content in tables
            for row in t.rows:
                lines.append(" | ".join(c.text for c in row.cells))
        print("\n".join(l for l in lines if l.strip()))
    elif p.suffix.lower() in (".md", ".txt"):
        print(p.read_text(encoding="utf-8"))
    else:
        sys.exit(f"{p.suffix} not supported here; for PDFs use Claude's Read tool.")


def cmd_guidelines(a):
    print(workspace.resource("resume_guidelines.md").read_text(encoding="utf-8"))


def workflow_names() -> list[str]:
    return sorted(p.stem for p in workspace.resource("workflows").glob("*.md"))


def cmd_workflow(a):
    names = workflow_names()
    if not a.name:
        print("Workflows (print one with: python -m gighunter workflow NAME):")
        for n in names:
            print("  " + n)
        return
    if a.name not in names:
        sys.exit(f"Unknown workflow {a.name!r}. Available: {', '.join(names)}")
    print(workspace.resource("workflows", f"{a.name}.md").read_text(encoding="utf-8"))


def cmd_config(a):
    from .schedule import load_schedule
    settings, aliases, profile = _ctx()
    s = load_schedule()
    print(f"workspace: {workspace.home()}")
    print(f"schedule:  {'ON' if s.enabled else 'PAUSED'} {s.send_time:%H:%M} {s.timezone} {','.join(s.days)}; "
          f"min score {s.min_match_score:g}%, max {s.max_listings}")
    print(f"weights:   {settings['weights']}")
    print(f"profile:   {len(profile.skills)} skills, {len(profile.target_titles)} target titles, "
          f"{len(profile.dealbreakers)} dealbreakers, {len(aliases)} alias groups")


def cmd_label(a):
    from .tune import add_label
    print(add_label(a.job_id, a.rating, a.note or ""))


def cmd_tune(a):
    from .tune import apply_weights, fit
    settings, aliases, profile = _ctx()
    res = fit(profile, settings, aliases)
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"{res['labels']} labels, {res['pairs']} ordered pairs")
        print(f"ranking accuracy: {res['accuracy_before']:.0%} -> {res['accuracy_after']:.0%}")
        for k in res["current"]:
            print(f"  {k:16} {res['current'][k]:.2f} -> {res['suggested'][k]:.2f}")
        if res["suggested_min_match_score"] is not None:
            print(f"suggested min_match_score (schedule.toml): {res['suggested_min_match_score']}")
        for rt, title, co, old, new in res["per_listing"]:
            print(f"  [{rt:6}] {old:5.1f} -> {new:5.1f}  {title[:45]} @ {co[:20]}")
    if a.apply:
        apply_weights(res["suggested"])
        print("Saved suggested weights to config/settings.yaml")


# ---------------------------------------------------------------- entry
def main(argv=None):
    for stream in (sys.stdout, sys.stderr):        # Windows consoles (cp1252) choke on emoji in titles
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="gighunter", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"gighunter {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("init"); c.add_argument("folder"); c.set_defaults(fn=cmd_init)
    c = sub.add_parser("scan"); c.add_argument("--top", type=int, default=30)
    c.add_argument("--save", action="store_true"); c.add_argument("--json", action="store_true")
    c.add_argument("--show-out", action="store_true", help="also list out-of-scope/dropped listings with the reason")
    c.set_defaults(fn=cmd_scan)
    c = sub.add_parser("digest"); c.add_argument("--force", action="store_true")
    c.add_argument("--dry-run", action="store_true"); c.set_defaults(fn=cmd_digest)
    c = sub.add_parser("score"); g = c.add_mutually_exclusive_group(required=True)
    g.add_argument("--url"); g.add_argument("--file")
    for f in ("--title", "--company", "--location"):
        c.add_argument(f)
    c.set_defaults(fn=cmd_score)
    c = sub.add_parser("fetch-jd"); c.add_argument("url"); c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_fetch_jd)
    c = sub.add_parser("render"); c.add_argument("path"); c.set_defaults(fn=cmd_render)
    c = sub.add_parser("extract"); c.add_argument("file"); c.set_defaults(fn=cmd_extract)
    sub.add_parser("guidelines").set_defaults(fn=cmd_guidelines)
    sub.add_parser("config").set_defaults(fn=cmd_config)
    c = sub.add_parser("workflow"); c.add_argument("name", nargs="?"); c.set_defaults(fn=cmd_workflow)
    c = sub.add_parser("label"); c.add_argument("job_id"); c.add_argument("rating", choices=["strong", "maybe", "no"])
    c.add_argument("--note"); c.set_defaults(fn=cmd_label)
    c = sub.add_parser("tune"); c.add_argument("--apply", action="store_true")
    c.add_argument("--json", action="store_true"); c.set_defaults(fn=cmd_tune)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
