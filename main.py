"""Entry point: scrape LinkedIn and send digest, on a schedule or on demand."""
import argparse
import logging
import os
import sys
import time

import schedule
from dotenv import load_dotenv

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


def run_job() -> None:
    lookback = int(os.environ.get("LOOKBACK_HOURS", "12"))
    try:
        posts = scrape_posts(lookback_hours=lookback)
    except Exception as exc:
        logger.error("Scraper mislukt: %s", exc)
        return

    new_posts = [p for p in posts if tracker.is_new(p["urn"])]
    logger.info("%d posts na deduplicatie (tracker)", len(new_posts))

    try:
        send_digest(new_posts, lookback_hours=lookback)
    except Exception as exc:
        logger.error("E-mail versturen mislukt: %s", exc)
        return

    tracker.mark_seen([p["urn"] for p in new_posts])
    tracker.cleanup_old(days=30)
    logger.info("Klaar.")


def _schedule_times() -> list[str]:
    raw = os.environ.get("SCHEDULE_TIMES", "08:00,17:00")
    return [t.strip() for t in raw.split(",") if t.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn branding/webdesign alert scraper")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Voer direct één run uit (geen scheduler)",
    )
    args = parser.parse_args()

    if args.run_now:
        logger.info("Eenmalige run gestart.")
        run_job()
        return

    times = _schedule_times()
    for t in times:
        schedule.every().day.at(t).do(run_job)
        logger.info("Ingepland op %s", t)

    logger.info("Scheduler actief. Wachten op ingeplande tijden…")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
