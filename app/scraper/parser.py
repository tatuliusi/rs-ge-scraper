import hashlib
import logging
import re
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_MIN_TEXT_LENGTH = 300
_MIN_WORD_COUNT = 40
_NAV_LINE_RATIO_THRESHOLD = 0.75

_CONTENT_SELECTORS = [
    ("css", "article"),
    ("css", "main"),
    ("id", "main-content"),
    ("id", "content"),
    ("css", ".tab-content"),
    ("css", ".page-content"),
    ("css", ".content-wrapper"),
]

_GEORGIAN_RE = re.compile(r"[ა-ჿ]")


def _find_content(soup: BeautifulSoup) -> Tag | None:
    for kind, value in _CONTENT_SELECTORS:
        if kind == "css":
            el = soup.select_one(value)
        elif kind == "id":
            el = soup.find(id=value)
        else:
            el = soup.find(class_=value)
        if el:
            return el
    return None


def _is_navigation_noise(text: str) -> bool:
    """Return True if the text looks like mostly nav links rather than content."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return True
    short_lines = sum(1 for l in lines if len(l) < 40)
    ratio = short_lines / len(lines)
    return ratio > _NAV_LINE_RATIO_THRESHOLD


def _has_georgian(text: str) -> bool:
    return bool(_GEORGIAN_RE.search(text))


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_page(html: str) -> str:
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer",
                     "noscript", "iframe", "aside"]):
        tag.decompose()

    content = _find_content(soup)
    if not content:
        logger.debug("No content container found")
        return ""

    text = content.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = text.strip()

    if len(text) < _MIN_TEXT_LENGTH:
        logger.debug(f"Text too short ({len(text)} chars)")
        return ""

    words = text.split()
    if len(words) < _MIN_WORD_COUNT:
        logger.debug(f"Too few words ({len(words)})")
        return ""

    if _is_navigation_noise(text):
        logger.debug("Detected navigation noise, skipping")
        return ""

    if not _has_georgian(text):
        logger.debug("No Georgian characters found, skipping")
        return ""

    return text
