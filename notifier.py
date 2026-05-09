"""Send HTML digest email with new LinkedIn posts."""
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Template

logger = logging.getLogger(__name__)

EMAIL_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LinkedIn Opdrachten Digest</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f3f2ef; margin: 0; padding: 20px; color: #191919; }
  .container { max-width: 640px; margin: 0 auto; }
  .header { background: #0a66c2; color: white; padding: 24px 28px; border-radius: 8px 8px 0 0; }
  .header h1 { margin: 0; font-size: 20px; }
  .header p { margin: 4px 0 0; font-size: 13px; opacity: 0.85; }
  .body { background: white; padding: 24px 28px; border-radius: 0 0 8px 8px;
          box-shadow: 0 1px 4px rgba(0,0,0,.12); }
  .post { border-left: 3px solid #0a66c2; padding: 12px 16px; margin-bottom: 20px;
          background: #f8f9fa; border-radius: 0 6px 6px 0; }
  .post-author { font-weight: 600; font-size: 14px; color: #0a66c2; }
  .post-time { font-size: 12px; color: #666; margin-left: 8px; }
  .post-text { font-size: 14px; line-height: 1.55; margin: 8px 0; color: #333; }
  .post-link a { font-size: 13px; color: #0a66c2; text-decoration: none; font-weight: 500; }
  .post-link a:hover { text-decoration: underline; }
  .empty { text-align: center; color: #666; padding: 32px 0; font-size: 14px; }
  .footer { text-align: center; font-size: 12px; color: #999; margin-top: 20px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>LinkedIn Opdrachten &mdash; {{ run_time }}</h1>
    <p>{{ count }} nieuwe {{ 'post' if count == 1 else 'posts' }} gevonden &bull; branding &amp; web design &bull; NL + BE</p>
  </div>
  <div class="body">
    {% if posts %}
      {% for post in posts %}
      <div class="post">
        <div>
          <span class="post-author">{{ post.author }}</span>
          {% if post.posted_at %}
          <span class="post-time">{{ post.posted_at_fmt }}</span>
          {% endif %}
        </div>
        <div class="post-text">{{ post.text }}</div>
        <div class="post-link"><a href="{{ post.url }}" target="_blank">Bekijk post op LinkedIn &rarr;</a></div>
      </div>
      {% endfor %}
    {% else %}
      <div class="empty">Geen nieuwe posts gevonden in de afgelopen {{ lookback_hours }} uur.<br>Probeer het later nog eens.</div>
    {% endif %}
  </div>
  <div class="footer">Verstuurd op {{ now }} &bull; LinkedIn Job Alerts</div>
</div>
</body>
</html>"""
)


def _fmt_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    local = dt.astimezone()
    now = datetime.now(tz=timezone.utc).astimezone()
    diff_h = int((now - local).total_seconds() / 3600)
    if diff_h == 0:
        return "zojuist"
    if diff_h == 1:
        return "1 uur geleden"
    return f"{diff_h} uur geleden"


def send_digest(posts: list[dict], lookback_hours: int = 12) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]
    email_from = os.environ.get("EMAIL_FROM", smtp_user)

    now = datetime.now()
    run_time = now.strftime("%d %b %Y, %H:%M")

    enriched = []
    for p in posts:
        enriched.append({**p, "posted_at_fmt": _fmt_time(p.get("posted_at"))})

    html = EMAIL_TEMPLATE.render(
        posts=enriched,
        count=len(posts),
        run_time=run_time,
        lookback_hours=lookback_hours,
        now=now.strftime("%d-%m-%Y %H:%M"),
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"LinkedIn Opdrachten: {len(posts)} nieuwe posts ({run_time})"
    msg["From"] = email_from
    msg["To"] = email_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    logger.info("E-mail versturen naar %s via %s:%s…", email_to, smtp_host, smtp_port)
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [email_to], msg.as_bytes())

    logger.info("E-mail verstuurd.")
