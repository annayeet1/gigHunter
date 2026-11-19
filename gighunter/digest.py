from __future__ import annotations

import html
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .models import MatchResult


# ---- Email design tokens (dataviz reference palette; light values inline, dark via <style>) ----
# Email clients strip JS and SVG and many ignore <style>, so everything is inline-styled tables.
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"        # primary / secondary / muted text
PAGE, SURFACE, HAIRLINE = "#f9f9f7", "#fcfcfb", "#e1e0d9"  # page plane / card surface / hairline
ACCENT, TRACK = "#2a78d6", "#cde2fb"                       # meter fill (blue 450) / track (blue 100, same ramp)
LINK = "#1c5cab"                                           # blue 550: link text, >= 4.5:1 on the surface
GOOD, WARNING = "#0ca30c", "#fab219"                       # reserved status colors; always icon + label
FONT = "'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

_DARK_CSS = f"""
<style>
  :root {{ color-scheme: light dark; supported-color-schemes: light dark; }}
  @media (prefers-color-scheme: dark) {{
    .gh-page {{ background:#0d0d0d !important; }}
    .gh-card {{ background:#1a1a19 !important; border-color:#2c2c2a !important; }}
    .gh-ink {{ color:#f0efec !important; }}
    .gh-ink2 {{ color:#c3c2b7 !important; }}
    .gh-link {{ color:#86b6ef !important; }}
    .gh-track {{ background:#184f95 !important; }}
    .gh-fill {{ background:#3987e5 !important; }}
  }}
</style>"""


def _e(s) -> str:
    return html.escape(str(s or ""))


def _tier_chip(tier: str) -> str:
    """Status chip: color + icon + word, never color alone. Text inside warning is near-black."""
    if tier == "reach":
        bg, fg, label = WARNING, INK, "&#9650; Reach"      # ▲
    else:
        bg, fg, label = GOOD, "#ffffff", "&#10003; Fit"    # ✓
    return (f'<span style="display:inline-block;background:{bg};color:{fg};border-radius:999px;'
            f'padding:2px 9px;font:600 11px {FONT};letter-spacing:.2px">{label}</span>')


def _meter(score: float) -> str:
    """Thin meter: blue fill on a lighter step of the same ramp, rounded ends, no text inside."""
    pct = max(2, min(100, round(score)))
    rest = 100 - pct
    filled = (f'<td class="gh-fill" width="{pct}%" style="background:{ACCENT};height:6px;font-size:0;line-height:0;'
              f'border-radius:{"999px" if rest == 0 else "999px 0 0 999px"}">&nbsp;</td>')
    empty = (f'<td width="{rest}%" style="height:6px;font-size:0;line-height:0">&nbsp;</td>' if rest else "")
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="gh-track" '
            f'style="background:{TRACK};border-radius:999px;border-collapse:separate"><tr>{filled}{empty}</tr></table>')


def _stat(label: str, value) -> str:
    """Stat tile: sentence-case label, semibold value, both in text ink (never series color)."""
    return (f'<td class="gh-card" style="background:{SURFACE};border:1px solid {HAIRLINE};border-radius:10px;'
            f'padding:12px 14px;width:25%">'
            f'<div class="gh-ink2" style="font:400 12px {FONT};color:{INK_2}">{_e(label)}</div>'
            f'<div class="gh-ink" style="font:600 24px {FONT};color:{INK};margin-top:2px">{_e(value)}</div></td>')


def _card(r: MatchResult) -> str:
    j = r.job
    meta = " &middot; ".join(_e(x) for x in [j.company, j.location or "Location n/a", j.source] if x)
    matched = ", ".join(r.matched_skills[:8])
    gaps = ", ".join(r.missing_skills[:6])
    why = ""
    if r.tier == "reach" and r.tier_reasons:
        why = (f'<div class="gh-ink2" style="font:400 12px {FONT};color:{INK_2};margin-top:6px">'
               f'Why it&rsquo;s a reach: {_e("; ".join(r.tier_reasons))}</div>')
    skills = ""
    if matched:
        skills += (f'<div class="gh-ink2" style="font:400 12px {FONT};color:{INK_2};margin-top:8px">'
                   f'<b class="gh-ink" style="color:{INK};font-weight:600">You have:</b> {_e(matched)}</div>')
    if gaps:
        skills += (f'<div class="gh-ink2" style="font:400 12px {FONT};color:{INK_2};margin-top:2px">'
                   f'<b class="gh-ink" style="color:{INK};font-weight:600">Gaps:</b> {_e(gaps)}</div>')
    parts = " &middot; ".join(f"{k.replace('_', ' ')} {v:.0%}" for k, v in r.breakdown.items() if k != "bonus" or v)
    return f"""
<tr><td style="padding:0 0 12px 0">
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="gh-card"
        style="background:{SURFACE};border:1px solid {HAIRLINE};border-radius:12px;border-collapse:separate">
  <tr><td style="padding:16px 18px">
   <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="vertical-align:top">
     <a class="gh-link" href="{_e(j.url)}" style="font:600 16px {FONT};color:{LINK};text-decoration:none">{_e(j.title)}</a>
     <div class="gh-ink2" style="font:400 13px {FONT};color:{INK_2};margin-top:3px">{meta}</div>
    </td>
    <td style="vertical-align:top;text-align:right;white-space:nowrap;padding-left:12px">{_tier_chip(r.tier)}</td>
   </tr></table>
   <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px"><tr>
    <td style="vertical-align:middle">{_meter(r.score)}</td>
    <td class="gh-ink" style="vertical-align:middle;width:52px;text-align:right;font:600 15px {FONT};color:{INK}">{r.score:.0f}%</td>
   </tr></table>
   {why}{skills}
   <div style="font:400 11px {FONT};color:{MUTED};margin-top:8px">{parts}</div>
  </td></tr>
 </table>
</td></tr>"""


def _section(title: str, results: list[MatchResult]) -> str:
    if not results:
        return ""
    head = (f'<tr><td class="gh-ink" style="padding:18px 0 8px 0;font:600 14px {FONT};color:{INK}">'
            f'{_e(title)} <span class="gh-ink2" style="color:{INK_2};font-weight:400">({len(results)})</span></td></tr>')
    return head + "".join(_card(r) for r in results)


def render_html(results: list[MatchResult], day: str, threshold: float = 0, scanned: int | None = None) -> str:
    fits = [r for r in results if r.tier != "reach"]
    reaches = [r for r in results if r.tier == "reach"]
    n = len(results)
    preheader = (f"{len(fits)} fit, {len(reaches)} reach" if n else "No new matches today")
    tiles = "".join([
        _stat("New matches", n), '<td style="width:8px"></td>',
        _stat("Fit", len(fits)), '<td style="width:8px"></td>',
        _stat("Reach", len(reaches)), '<td style="width:8px"></td>',
        _stat("Listings scanned", f"{scanned:,}" if scanned is not None else "n/a"),
    ])
    if n:
        body = _section("Strong fits", fits) + _section("Reaches: one step beyond your profile", reaches)
    else:
        body = (f'<tr><td class="gh-card gh-ink2" style="background:{SURFACE};border:1px solid {HAIRLINE};'
                f'border-radius:12px;padding:24px;text-align:center;font:400 14px {FONT};color:{INK_2}">'
                f'No new listings at or above {threshold:g}% today. Tomorrow&rsquo;s scan runs automatically.</td></tr>')
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">
<title>gigHunter digest</title>{_DARK_CSS}</head>
<body class="gh-page" style="margin:0;padding:0;background:{PAGE}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{_e(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" class="gh-page" style="background:{PAGE}">
 <tr><td align="center" style="padding:24px 12px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px">
   <tr><td style="padding:0 0 4px 0">
    <div class="gh-ink" style="font:700 22px {FONT};color:{INK}">gigHunter</div>
    <div class="gh-ink2" style="font:400 13px {FONT};color:{INK_2};margin-top:2px">Your job matches for {_e(day)}</div>
   </td></tr>
   <tr><td style="padding:14px 0 4px 0">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate"><tr>{tiles}</tr></table>
   </td></tr>
   {body}
   <tr><td style="padding:16px 2px 0 2px;font:400 11px {FONT};color:{MUTED};line-height:1.5">
    Showing new listings scoring at least {threshold:g}% (config/schedule.toml). &#10003; Fit = matches your
    profile; &#9650; Reach = one step beyond it (reason shown). Out-of-scope listings are left out.<br>
    To tailor a resume and cover letter, ask Claude to follow <code>python -m gighunter workflow tailor</code>
    (or /gighunter:tailor) with the job link.
   </td></tr>
  </table>
 </td></tr>
</table></body></html>"""


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
