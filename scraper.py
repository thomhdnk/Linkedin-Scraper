"""LinkedIn post scraper using the unofficial linkedin-api library."""
import logging
import os
import time
from datetime import datetime, timezone

from linkedin_api import Linkedin

logger = logging.getLogger(__name__)

# LinkedIn geo URNs
GEO_URNS = {
    "nederland": "urn:li:geo:102890719",
    "belgie": "urn:li:geo:105015875",
}

# Zoekwoorden in NL en EN gericht op freelance branding/webdesign opdrachten
SEARCH_QUERIES = [
    "freelance designer gezocht",
    "grafisch ontwerper gezocht",
    "branding opdracht freelance",
    "web design opdracht freelance",
    "logo ontwerp gezocht",
    "huisstijl ontwerp freelance",
    "freelance web designer",
    "looking for freelance designer",
    "need brand designer",
    "branding freelance",
    "web design freelance Belgium",
    "webdesigner freelance",
]


def _ms_to_dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _build_post_url(urn: str) -> str:
    """Convert activity URN to a shareable LinkedIn post URL."""
    activity_id = urn.split(":")[-1]
    return f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"


def _extract_post(raw: dict) -> dict | None:
    """Parse a raw search result item into a clean post dict."""
    try:
        urn = raw.get("targetUrn") or raw.get("entityUrn", "")
        if not urn:
            return None

        # Navigate to the actual post content
        update = raw.get("value", {}).get("com.linkedin.voyager.feed.render.UpdateV2", {})
        if not update:
            # Try alternate path
            update = raw.get("value", {})

        # Get post text
        commentary = (
            update.get("commentary", {})
            .get("text", {})
            .get("text", "")
        )
        if not commentary:
            commentary = raw.get("summary", {}).get("text", {}).get("text", "")

        # Get author
        actor = update.get("actor", {})
        name = (
            actor.get("name", {}).get("text", "Onbekend")
            if isinstance(actor.get("name"), dict)
            else str(actor.get("name", "Onbekend"))
        )

        # Get timestamp
        posted_at_ms = update.get("publishedAt") or raw.get("timePeriod", {}).get("startDate")
        posted_at = _ms_to_dt(posted_at_ms) if isinstance(posted_at_ms, int) else None

        url = _build_post_url(urn)

        return {
            "urn": urn,
            "author": name,
            "text": commentary[:500] + ("…" if len(commentary) > 500 else ""),
            "url": url,
            "posted_at": posted_at,
        }
    except Exception as exc:
        logger.debug("Could not parse post: %s", exc)
        return None


def scrape_posts(lookback_hours: int = 12) -> list[dict]:
    """
    Search LinkedIn for recent branding/webdesign posts in NL + BE.
    Returns a list of post dicts, deduplicated by URN.
    """
    li_at = os.environ.get("LINKEDIN_LI_AT")
    jsessionid = os.environ.get("LINKEDIN_JSESSIONID", "")
    if li_at:
        logger.info("Inloggen bij LinkedIn via cookie…")
        api = Linkedin("", "", cookies={"li_at": li_at, "JSESSIONID": jsessionid})
    else:
        email = os.environ.get("LINKEDIN_EMAIL", "")
        password = os.environ.get("LINKEDIN_PASSWORD", "")
        if not email or not password:
            raise RuntimeError(
                "Stel LINKEDIN_LI_AT (aanbevolen) of LINKEDIN_EMAIL + LINKEDIN_PASSWORD in."
            )
        logger.info("Inloggen bij LinkedIn via e-mail/wachtwoord…")
        api = Linkedin(email, password)

    cutoff = datetime.now(tz=timezone.utc).timestamp() - lookback_hours * 3600
    seen_urns: set[str] = set()
    posts: list[dict] = []

    for query in SEARCH_QUERIES:
        logger.info("Zoeken naar: '%s'", query)
        try:
            results = api.search(
                params={
                    "keywords": query,
                    "origin": "GLOBAL_SEARCH_HEADER",
                    "resultType": "CONTENT",
                },
                limit=20,
            )
        except Exception as exc:
            logger.warning("Zoekopdracht mislukt voor '%s': %s", query, exc)
            time.sleep(2)
            continue

        for raw in results:
            post = _extract_post(raw)
            if not post:
                continue
            if post["urn"] in seen_urns:
                continue
            seen_urns.add(post["urn"])

            # Filter op tijdstip
            if post["posted_at"] and post["posted_at"].timestamp() < cutoff:
                continue

            posts.append(post)

        # Beleefd scrapen: kleine pauze tussen queries
        time.sleep(1.5)

    # Sorteer: nieuwste eerst
    posts.sort(
        key=lambda p: p["posted_at"].timestamp() if p["posted_at"] else 0,
        reverse=True,
    )

    logger.info("Gevonden: %d nieuwe posts", len(posts))
    return posts
