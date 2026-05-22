"""Send LinkedIn alert digest via Resend email API (HTTPS, works from Railway)."""
import json
import logging
import os
import urllib.request
from datetime import datetime, timezone

from jinja2 import Template

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"

EMAIL_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LinkedIn Opdrachten</title>
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
  .post-title { font-weight: 600; font-size: 14px; color: #0a66c2; }
  .post-text { font-size: 14px; line-height: 1.55; margin: 8px 0; color: #333; }
  .post-link a { font-size: 13px; color: #0a66c2; text-decoration: none; font-weight: 500; }
  .empty { text-align: center; color: #666; padding: 32px 0; font-size: 14px; }
  .footer { text-align: center; font-size: 12px; color: #999; margin-top: 20px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>LinkedIn Opdrachten &mdash; {{ run_time }}</h1>
    <p>{{ count }} nieuwe {{ 'resultaat' if count == 1 else 'resultaten' }} &bull; branding &amp; web design &bull; NL + BE</p>
  </div>
  <div class="body">
    {% if posts %}
      {% for post in posts %}
      <div class="post">
        <div class="post-title">{{ post.author }}</div>
        <div class="post-text">{{ post.text }}</div>
        <div class="post-link"><a href="{{ post.url }}">Bekijk op LinkedIn &rarr;</a></div>
      </div>
      {% endfor %}
    {% else %}
      <div class="empty">
        Geen nieuwe posts gevonden in de afgelopen {{ lookback_hours }} uur.
      </div>
    {% endif %}
  </div>
  <div class="footer">{{ now }} &bull; LinkedIn Job Alerts</div>
</div>
</body>
</html>""")


def send_digest(posts: list[dict], lookback_hours: int = 12) -> None:
    api_key = os.environ["RESEND_API_KEY"]
    email_to = os.environ["EMAIL_TO"]
    email_from = os.environ.get("EMAIL_FROM", "LinkedIn Alerts <alerts@resend.dev>")

    now = datetime.now()
    html = EMAIL_TEMPLATE.render(
        posts=posts,
        count=len(posts),
        run_time=now.strftime("%d %b %Y, %H:%M"),
        lookback_hours=lookback_hours,
        now=now.strftime("%d-%m-%Y %H:%M"),
    )

    payload = json.dumps({
        "from": email_from,
        "to": [email_to],
        "subject": f"LinkedIn Opdrachten: {len(posts)} nieuwe posts ({now.strftime('%d %b, %H:%M')})",
        "html": html,
    }).encode()

    req = urllib.request.Request(
        RESEND_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.load(resp)

    if "id" not in result:
        raise RuntimeError(f"Resend API fout: {result}")

    logger.info("E-mail verstuurd via Resend (id=%s).", result["id"])
