"""Send LinkedIn alert digest via Telegram Bot API (HTTPS, not SMTP)."""
import json
import logging
import os
import urllib.request
from datetime import datetime

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
MAX_MSG_LEN = 4000  # Telegram limit is 4096; leave headroom


def _post(token: str, method: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        TELEGRAM_API.format(token=token, method=method),
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def _build_message(posts: list[dict], lookback_hours: int) -> str:
    now = datetime.now().strftime("%d %b %Y, %H:%M")
    if not posts:
        return (
            f"🔍 <b>LinkedIn Alerts — {now}</b>\n\n"
            f"Geen nieuwe posts gevonden in de afgelopen {lookback_hours} uur."
        )

    lines = [f"🔍 <b>LinkedIn Alerts — {now}</b>", f"{len(posts)} nieuwe posts:\n"]
    for i, p in enumerate(posts, 1):
        author = p.get("author") or "LinkedIn"
        text = (p.get("text") or "")[:200]
        url = p.get("url", "")
        lines.append(f"<b>{i}. {author}</b>")
        if text:
            lines.append(f"{text}…")
        lines.append(f'<a href="{url}">Bekijk op LinkedIn →</a>\n')

    return "\n".join(lines)


def send_digest(posts: list[dict], lookback_hours: int = 12) -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    message = _build_message(posts, lookback_hours)

    # Split if message exceeds Telegram's limit
    chunks = [message[i:i + MAX_MSG_LEN] for i in range(0, len(message), MAX_MSG_LEN)]
    for chunk in chunks:
        result = _post(token, "sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API fout: {result}")

    logger.info("Telegram bericht verstuurd (%d posts).", len(posts))
