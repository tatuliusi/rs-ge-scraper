"""
Parser module — two responsibilities:
  1. Extract clean text content from an HTML page.
  2. Extract all hyperlinks from an HTML page.
"""
import hashlib
import logging
import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_GEORGIAN_RE = re.compile(r"[ა-ჿ]")

_NOISE_TAGS = frozenset({
    "script", "style", "nav", "header", "footer",
    "noscript", "iframe", "aside", "form", "button",
})

_CONTENT_SELECTORS = [
    "article",
    "main",
    "div.tab-content",
    "div.page-content",
    "div#content",
    ".main-content",
    "#main-content",
    ".content-body",
    "div.article-body",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_page(
    html: str,
    min_length: int = 200,
    min_words: int = 30,
) -> Tuple[Optional[str], str]:
    """
    Extract the main text body from an HTML document.

    Returns:
        (text, sha256_hash)  — text is None if the page fails validation.
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    container = _find_content_container(soup)
    if not container:
        return None, ""

    text = _clean_text(container.get_text(separator="\n", strip=True))

    if len(text) < min_length or len(text.split()) < min_words:
        return None, ""

    return text, _sha256(text)


def extract_title(html: str) -> str:
    """Best-effort title extraction: og:title → <title> → first <h1>."""
    soup = BeautifulSoup(html, "lxml")

    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()

    if soup.title:
        return soup.title.get_text(strip=True)

    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)

    return ""


def extract_links(html: str, base_url: str) -> List[str]:
    """
    Return every unique absolute URL found in <a href> tags.
    Fragments, javascript: and mailto: links are discarded.
    """
    soup = BeautifulSoup(html, "lxml")
    seen: set = set()
    links: List[str] = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()

        if not href:
            continue
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        absolute = urljoin(base_url, href)

        # Strip fragment
        parsed = urlparse(absolute)
        normalized = parsed._replace(fragment="").geturl()

        if normalized not in seen:
            seen.add(normalized)
            links.append(normalized)

    return links


def has_georgian(text: str) -> bool:
    return bool(_GEORGIAN_RE.search(text))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_content_container(soup: BeautifulSoup) -> Optional[Tag]:
    for selector in _CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el:
            return el
    return soup.find("body")


def _clean_text(raw: str) -> str:
    lines = (line.strip() for line in raw.splitlines())
    return "\n".join(line for line in lines if line)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
