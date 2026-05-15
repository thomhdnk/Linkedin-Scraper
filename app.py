"""
Combined web dashboard + background scheduler.
Open in browser (or iPhone Safari) to control the app.
"""
import json
import logging
import os
import threading
import time
from datetime import datetime

import schedule
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template_string, url_for

import tracker
from notifier import send_digest
from scraper import scrape_posts

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

REQUIRED_VARS = [
    "SERPER_API_KEY",
    "TELEGRAM_TOKEN",
    "TELEGRAM_CHAT_ID",
]

# In-memory status
_status = {
    "running": False,
    "last_run": None,
    "last_count": None,
    "next_runs": [],
    "error": None,
}

# ── HTML template ─────────────────────────────────────────────────────────────

DASHBOARD = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>LinkedIn Alerts</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f3f2ef; min-height: 100vh; }
  header { background: #0a66c2; color: white; padding: 20px 16px; }
  header h1 { font-size: 20px; font-weight: 700; }
  header p  { font-size: 13px; opacity: 0.8; margin-top: 2px; }
  main { max-width: 600px; margin: 0 auto; padding: 16px; }

  .card { background: white; border-radius: 10px; padding: 20px;
          box-shadow: 0 1px 4px rgba(0,0,0,.10); margin-bottom: 14px; }
  .card h2 { font-size: 14px; text-transform: uppercase; letter-spacing: .05em;
              color: #666; margin-bottom: 12px; }

  .stat { display: flex; align-items: center; gap: 12px; padding: 8px 0;
          border-bottom: 1px solid #f0f0f0; }
  .stat:last-child { border-bottom: none; }
  .stat-label { font-size: 13px; color: #555; flex: 1; font-family: monospace; }
  .stat-label-plain { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
  .stat-value { font-size: 14px; font-weight: 600; color: #191919; }

  .badge { display: inline-block; padding: 3px 10px; border-radius: 12px;
           font-size: 12px; font-weight: 600; }
  .badge-green  { background: #d1fae5; color: #065f46; }
  .badge-blue   { background: #dbeafe; color: #1e40af; }
  .badge-red    { background: #fee2e2; color: #991b1b; }
  .badge-gray   { background: #f3f4f6; color: #374151; }

  .btn { display: block; width: 100%; padding: 14px;
         background: #0a66c2; color: white; border: none;
         border-radius: 8px; font-size: 16px; font-weight: 600;
         cursor: pointer; text-align: center; text-decoration: none;
         margin-top: 6px; }
  .btn:active { background: #094e9e; }
  .btn:disabled { background: #93c5fd; cursor: not-allowed; }

  .alert { padding: 12px 14px; border-radius: 6px; font-size: 13px;
           margin-bottom: 14px; line-height: 1.5; }
  .alert-red  { background: #fee2e2; border-left: 3px solid #ef4444; color: #7f1d1d; }
  .alert-yellow { background: #fef9c3; border-left: 3px solid #eab308; color: #713f12; }

  .history-item { padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
  .history-item:last-child { border-bottom: none; }
  .history-time { font-size: 12px; color: #888; }
  .history-count { font-size: 14px; font-weight: 600; }

  .running-spinner::after { content: ' ⏳'; }
</style>
</head>
<body>
<header>
  <h1>LinkedIn Job Alerts</h1>
  <p>Branding &amp; web design · NL + BE</p>
</header>
<main>

  {% if missing_vars %}
  <div class="alert alert-yellow">
    <strong>⚠️ Ontbrekende instellingen</strong><br>
    Ga in Railway naar <em>Variables</em> en voeg toe:<br><br>
    {% for v in missing_vars %}<code>{{ v }}</code><br>{% endfor %}
  </div>
  {% endif %}

  {% if status.error %}
  <div class="alert alert-red"><strong>Fout bij laatste run:</strong><br>{{ status.error }}</div>
  {% endif %}

  <div class="card">
    <h2>Status</h2>
    <div class="stat">
      <span class="stat-label stat-label-plain">Scheduler</span>
      <span class="stat-value"><span class="badge badge-green">Actief</span></span>
    </div>
    <div class="stat">
      <span class="stat-label stat-label-plain">Laatste run</span>
      <span class="stat-value">{{ status.last_run or '—' }}</span>
    </div>
    <div class="stat">
      <span class="stat-label stat-label-plain">Posts gevonden</span>
      <span class="stat-value">
        {% if status.last_count is not none %}
          <span class="badge badge-blue">{{ status.last_count }} nieuw</span>
        {% else %}—{% endif %}
      </span>
    </div>
    <div class="stat">
      <span class="stat-label stat-label-plain">Volgende runs</span>
      <span class="stat-value">{{ status.next_runs | join(', ') or '—' }}</span>
    </div>
  </div>

  <div class="card">
    <h2>Instellingen</h2>
    {% for var, ok in config_status %}
    <div class="stat">
      <span class="stat-label">{{ var }}</span>
      <span class="stat-value">
        {% if ok %}
          <span class="badge badge-green">✓ Ingesteld</span>
        {% else %}
          <span class="badge badge-red">✗ Ontbreekt</span>
        {% endif %}
      </span>
    </div>
    {% endfor %}
  </div>

  <div class="card">
    <h2>Handmatig uitvoeren</h2>
    <p style="font-size:13px;color:#555;margin-bottom:14px;">
      Voer direct een scrape uit en ontvang de e-mail op je iPhone.
    </p>
    {% if missing_vars %}
      <button class="btn" disabled>Stel eerst alle variabelen in</button>
    {% elif status.running %}
      <button class="btn running-spinner" disabled>Bezig met scrapen…</button>
    {% else %}
      <form method="POST" action="/run-now">
        <button class="btn" type="submit">▶ Nu uitvoeren</button>
      </form>
    {% endif %}
  </div>

  {% if history %}
  <div class="card">
    <h2>Geschiedenis (laatste 10)</h2>
    {% for h in history %}
    <div class="history-item">
      <div class="history-time">{{ h.ran_at }}</div>
      <div class="history-count">{{ h.posts_found }} posts verzonden</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

</main>
<script>
  {% if status.running %}
  setTimeout(() => location.reload(), 5000);
  {% endif %}
</script>
</body>
</html>"""

# ── Routes ────────────────────────────────────────────────────────────────────

def _config_status():
    return [(v, bool(os.environ.get(v))) for v in REQUIRED_VARS]

def _missing_vars():
    return [v for v in REQUIRED_VARS if not os.environ.get(v)]


@app.route("/")
def index():
    history = tracker.get_run_history(limit=10)
    return render_template_string(
        DASHBOARD,
        status=_status,
        history=history,
        config_status=_config_status(),
        missing_vars=_missing_vars(),
    )


@app.route("/run-now", methods=["POST"])
def run_now():
    if not _status["running"] and not _missing_vars():
        t = threading.Thread(target=_run_job, daemon=True)
        t.start()
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/setup-telegram")
def setup_telegram():
    """Fetch recent Telegram updates to find your chat ID."""
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        return "Stel eerst TELEGRAM_TOKEN in via Railway Variables.", 400
    try:
        import urllib.request as _req
        with _req.urlopen(
            f"https://api.telegram.org/bot{token}/getUpdates", timeout=10
        ) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        return f"Fout: {exc}", 500

    results = data.get("result", [])
    if not results:
        return (
            "Geen berichten gevonden. Stuur eerst een bericht naar je bot in Telegram "
            "en laad deze pagina daarna opnieuw."
        ), 200

    chat_id = results[-1]["message"]["chat"]["id"]
    name = results[-1]["message"]["chat"].get("first_name", "")
    return (
        f"<h2>Jouw chat ID: <code>{chat_id}</code></h2>"
        f"<p>Naam: {name}</p>"
        f"<p>Voeg toe in Railway Variables:<br>"
        f"<code>TELEGRAM_CHAT_ID = {chat_id}</code></p>"
    ), 200


@app.route("/diagnose")
def diagnose():
    """Test each external connection independently — open in Safari to debug."""
    import smtplib
    results = {}

    # Test 1: outbound HTTPS via Serper.dev
    try:
        import json as _json
        import urllib.request as _req
        payload = _json.dumps({"q": "test", "num": 1}).encode()
        r = _req.Request(
            "https://google.serper.dev/search",
            data=payload,
            headers={
                "X-API-KEY": os.environ.get("SERPER_API_KEY", ""),
                "Content-Type": "application/json",
            },
        )
        with _req.urlopen(r, timeout=10) as resp:
            results["serper_https"] = f"OK (HTTP {resp.status})"
    except Exception as exc:
        results["serper_https"] = f"FOUT: {exc}"

    # Test 2: outbound SMTP port 587
    try:
        smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
            s.ehlo()
            s.starttls()
        results["smtp_587"] = "OK (verbinding geslaagd)"
    except Exception as exc:
        results["smtp_587"] = f"FOUT: {exc}"

    return jsonify(results)


# ── Job logic ─────────────────────────────────────────────────────────────────

def _run_job():
    missing = _missing_vars()
    if missing:
        _status["error"] = f"Ontbrekende variabelen: {', '.join(missing)}"
        return

    _status["running"] = True
    _status["error"] = None
    lookback = int(os.environ.get("LOOKBACK_HOURS", "12"))

    try:
        posts = scrape_posts(lookback_hours=lookback)
    except Exception as exc:
        logger.error("Scraper mislukt: %s", exc)
        _status["error"] = f"Zoeken mislukt: {exc}"
        _status["running"] = False
        _status["last_run"] = datetime.now().strftime("%d %b %Y, %H:%M")
        _update_next_runs()
        return

    try:
        new_posts = [p for p in posts if tracker.is_new(p["urn"])]
        send_digest(new_posts, lookback_hours=lookback)
        tracker.mark_seen([p["urn"] for p in new_posts])
        tracker.log_run(posts_found=len(new_posts))
        tracker.cleanup_old(days=30)
        _status["last_count"] = len(new_posts)
    except Exception as exc:
        logger.error("E-mail versturen mislukt: %s", exc)
        _status["error"] = f"E-mail versturen mislukt: {exc}"
    finally:
        _status["running"] = False
        _status["last_run"] = datetime.now().strftime("%d %b %Y, %H:%M")
        _update_next_runs()


def _update_next_runs():
    upcoming = []
    for j in schedule.get_jobs():
        if j.next_run:
            upcoming.append(j.next_run.strftime("%H:%M"))
    _status["next_runs"] = upcoming


# ── Scheduler ─────────────────────────────────────────────────────────────────

def _start_scheduler():
    raw = os.environ.get("SCHEDULE_TIMES", "08:00,17:00")
    times = [t.strip() for t in raw.split(",") if t.strip()]
    for t in times:
        schedule.every().day.at(t).do(_run_job)
        logger.info("Ingepland op %s", t)
    _update_next_runs()

    def loop():
        while True:
            schedule.run_pending()
            time.sleep(30)

    threading.Thread(target=loop, daemon=True).start()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _start_scheduler()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
