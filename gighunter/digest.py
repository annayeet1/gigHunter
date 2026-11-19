from __future__ import annotations

import html
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .models import MatchResult


def _color(score: float) -> str:
    return "#1a7f37" if score >= 80 else "#9a6700" if score >= 65 else "#57606a"


def render_html(results: list[MatchResult], day: str, threshold: float = 0) -> str:
    rows = []
    for r in results:
        j, b = r.job, r.breakdown
        why = ", ".join(r.matched_skills[:8]) or "-"
        gaps = ", ".join(r.missing_skills[:6]) or "-"
        parts = " · ".join(f"{k.replace('_', ' ')} {v:.0%}" for k, v in b.items())
        badge = ("" if r.tier != "reach" else
                 f'<span style="background:#fff8c5;border:1px solid #d4a72c;border-radius:4px;padding:0 4px;'
                 f'font-size:11px">REACH: {html.escape("; ".join(r.tier_reasons))}</span><br>')
        rows.append(f"""
<tr><td style="padding:10px;border-bottom:1px solid #eee;vertical-align:top">
  <div style="font-size:22px;font-weight:bold;color:{_color(r.score)}">{r.score:.0f}%</div></td>
<td style="padding:10px;border-bottom:1px solid #eee">
  <a href="{html.escape(j.url)}" style="font-size:16px;font-weight:bold">{html.escape(j.title)}</a><br>
  {badge}{html.escape(j.company)} · {html.escape(j.location or 'n/a')} · <span style="color:#888">{html.escape(j.source)}</span><br>
  <span style="font-size:12px">✅ {html.escape(why)}<br>⚠️ gaps: {html.escape(gaps)}</span><br>
  <span style="font-size:11px;color:#888">{parts}</span>
</td></tr>""")
    body = "".join(rows) or "<tr><td>No new listings above your threshold today.</td></tr>"
    return f"""<html><body style="font-family:Segoe UI,Arial,sans-serif;max-width:760px">
<h2>gigHunter: {len(results)} new match{'es' if len(results) != 1 else ''} for {day}</h2>
<p style="color:#57606a;font-size:12px">Showing new listings scoring at least {threshold:g}% (set in config/schedule.toml).</p>
<table style="border-collapse:collapse;width:100%">{body}</table>
<p style="font-size:11px;color:#888">To tailor a resume: open the repo in Claude Code and run
<code>python -m gighunter workflow tailor</code> (or /gighunter:tailor) with the job link.
Listings marked REACH are one step beyond your profile; out-of-scope listings are left out.</p></body></html>"""


def render_text(results: list[MatchResult]) -> str:
    return "\n\n".join(f"{r.score:.0f}%  {'[REACH] ' if r.tier == 'reach' else ''}{r.job.title} @ {r.job.company}\n{r.job.url}"
                       for r in results) \
        or "No new listings above your threshold today."


# New names first; GMAIL_* are accepted for workspaces created before v0.3.0.
_ENV = {
    "user": ("SMTP_USER", "GMAIL_USER"),
    "password": ("SMTP_PASSWORD", "GMAIL_APP_PASSWORD"),
    "to": ("SMTP_TO", "GMAIL_TO"),
}


def smtp_env(key: str) -> str | None:
    for name in _ENV[key]:
        if os.environ.get(name):
            return os.environ[name]
    return None


def credentials() -> tuple[str, str]:
    user, pw = smtp_env("user"), smtp_env("password")
    if not user or not pw:
        raise SystemExit("Email credentials missing: set secrets SMTP_USER and SMTP_PASSWORD "
                         "(older names GMAIL_USER / GMAIL_APP_PASSWORD also work).")
    return user, pw


RESEND_URL = "https://api.resend.com/emails"
RESEND_TEST_SENDER = "onboarding@resend.dev"   # works without a domain; delivers only to your Resend account email


def provider(email_cfg: dict) -> str:
    """'resend' or 'smtp'. 'auto' (default) picks Resend when RESEND_API_KEY is set."""
    p = (email_cfg.get("provider") or "auto").lower()
    if p == "auto":
        return "resend" if os.environ.get("RESEND_API_KEY") else "smtp"
    if p not in ("resend", "smtp"):
        raise SystemExit(f"email.provider must be auto, resend or smtp (got {p!r})")
    return p


def recipient(email_cfg: dict, fallback: str | None = None) -> str | None:
    return email_cfg.get("to") or os.environ.get("EMAIL_TO") or smtp_env("to") or fallback


def send(subject: str, html_body: str, text_body: str, email_cfg: dict) -> None:
    if provider(email_cfg) == "resend":
        send_resend(subject, html_body, text_body, email_cfg)
    else:
        send_smtp(subject, html_body, text_body, email_cfg)


def send_resend(subject: str, html_body: str, text_body: str, email_cfg: dict) -> None:
    """Send through Resend's HTTP API. Use a 'Sending access' key: it can send mail and nothing else."""
    import requests
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        raise SystemExit("RESEND_API_KEY is not set (create a 'Sending access' key at resend.com).")
    to = recipient(email_cfg)
    if not to:
        raise SystemExit("No recipient: set email.to in config/settings.yaml (or the EMAIL_TO secret) to the "
                         "address you signed up to Resend with.")
    sender = email_cfg.get("resend_from") or RESEND_TEST_SENDER
    r = requests.post(RESEND_URL, timeout=30,
                      headers={"Authorization": f"Bearer {key}", "User-Agent": "gigHunter"},
                      json={"from": f"{email_cfg.get('from_name', 'gigHunter')} <{sender}>", "to": [to],
                            "subject": subject, "html": html_body, "text": text_body})
    if r.status_code >= 300:
        try:
            detail = r.json().get("message", r.text)
        except ValueError:
            detail = r.text
        hint = (" With the onboarding@resend.dev sender, email.to must be your Resend account email."
                if r.status_code == 403 else "")
        raise SystemExit(f"Resend rejected the email ({r.status_code}): {detail}.{hint}")


def send_smtp(subject: str, html_body: str, text_body: str, email_cfg: dict) -> None:
    user, pw = credentials()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{email_cfg.get('from_name', 'gigHunter')} <{user}>"
    to = recipient(email_cfg, fallback=user)
    msg["To"] = to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL(email_cfg["smtp_host"], email_cfg["smtp_port"],
                          context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
