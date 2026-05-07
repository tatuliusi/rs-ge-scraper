"""
Seed URL discovery — two sources:
  1. rs.ge/SiteMap  (HTML sitemap listing all top-level pages)
  2. infohub.rs.ge  (paginated article search endpoints)
"""
import logging
from typing import List

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_SITEMAP_URL = "https://rs.ge/SiteMap"
_INFOHUB_SEARCH = "https://infohub.rs.ge/ka/search"
_INFOHUB_TYPES = [57, 64]

_SKIP = ["/gallery", "/Vacancy", "/vacancy", "/EmailUs", "/Contact",
         "/login", "/register", "/print"]
_SKIP_DOMAINS = ["youtube.com", "facebook.com", "twitter.com",
                 "asycuda.org", "google.com"]


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def get_all_seed_urls() -> List[str]:
    logger.info("Fetching sitemap…")
    sitemap = _fetch_sitemap()
    logger.info("  %d URLs from sitemap", len(sitemap))

    logger.info("Fetching infohub…")
    infohub = _fetch_infohub_all()
    logger.info("  %d URLs from infohub", len(infohub))

    combined = list(set(sitemap + infohub))
    logger.info("Total seed URLs: %d", len(combined))
    return combined


# ---------------------------------------------------------------------------
# Private
# ---------------------------------------------------------------------------

def _fetch_sitemap() -> List[str]:
    try:
        resp = requests.get(_SITEMAP_URL, timeout=15, headers={"User-Agent": _USER_AGENT})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        return [
            a["href"].strip()
            for a in soup.find_all("a", href=True)
            if _keep(a["href"].strip())
        ]
    except Exception as exc:
        logger.error("Sitemap fetch failed: %s", exc)
        return []


def _fetch_infohub_all() -> List[str]:
    urls: List[str] = []
    for t in _INFOHUB_TYPES:
        page = 1
        while page <= 200:          # hard safety cap
            batch = _fetch_infohub_page(t, page)
            if not batch:
                break
            urls.extend(batch)
            page += 1
    return list(set(urls))


def _fetch_infohub_page(article_type: int, page: int) -> List[str]:
    try:
        resp = requests.get(
            _INFOHUB_SEARCH,
            params={"types": article_type, "page": page},
            timeout=15,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        links = [
            a["href"].strip()
            for a in soup.find_all("a", href=True)
            if "/ka/" in a["href"] and "infohub.rs.ge" in a["href"]
        ]
        return links
    except Exception as exc:
        logger.warning("Infohub page %d type %d failed: %s", page, article_type, exc)
        return []


def _keep(url: str) -> bool:
    if not url.startswith("http"):
        return False
    if any(s in url for s in _SKIP):
        return False
    if any(d in url for d in _SKIP_DOMAINS):
        return False
    return True
