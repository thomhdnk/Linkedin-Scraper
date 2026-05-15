"""
LinkedIn post scraper via Serper.dev (Google Search API).

Searches Google for LinkedIn posts — no LinkedIn auth needed,
works reliably from any cloud server. Free tier: 2500 queries/month.
"""
import json
import logging
import os
import time
import urllib.request

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"

SEARCH_QUERIES = [
    'site:linkedin.com/posts "freelance designer gezocht"',
    'site:linkedin.com/posts "grafisch ontwerper gezocht"',
    'site:linkedin.com/posts "webdesigner gezocht"',
    'site:linkedin.com/posts "huisstijl" "freelance"',
    'site:linkedin.com/posts "branding" "freelance" Nederland',
    'site:linkedin.com/posts "branding" "freelance" België',
    'site:linkedin.com/posts "logo" "freelance" gezocht',
    'site:linkedin.com/posts "web design" "freelance" Netherlands',
    'site:linkedin.com/posts "brand designer" freelance Netherlands OR Belgium',
]


def scrape_posts(lookback_hours: int = 12) -> list[dict]:
    """Search Google for recent LinkedIn posts about branding/webdesign freelance work."""
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "SERPER_API_KEY is niet ingesteld. "
            "Maak gratis een account aan op serper.dev en voeg de sleutel toe aan Railway."
        )

    # "qdr:d" = past 24 hours; suits a twice-daily run schedule
    tbs = "qdr:d" if lookback_hours <= 24 else "qdr:w"

    seen_urls: set[str] = set()
    posts: list[dict] = []

    for query in SEARCH_QUERIES:
        logger.info("Zoeken: %s", query)
        try:
            payload = json.dumps({"q": query, "tbs": tbs, "num": 10}).encode()
            req = urllib.request.Request(
                SERPER_URL,
                data=payload,
                headers={
                    "X-API-KEY": api_key,
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
        except Exception as exc:
            logger.warning("Zoekopdracht mislukt ('%s'): %s", query, exc)
            time.sleep(3)
            continue

        for item in data.get("organic", []):
            url = item.get("link", "")
            if not url or url in seen_urls or "linkedin.com" not in url:
                continue
            seen_urls.add(url)
            posts.append(
                {
                    "urn": url,
                    "author": item.get("title", "LinkedIn"),
                    "text": item.get("snippet", ""),
                    "url": url,
                    "posted_at": None,
                }
            )

        time.sleep(1)

    logger.info("Gevonden: %d resultaten", len(posts))
    return posts
