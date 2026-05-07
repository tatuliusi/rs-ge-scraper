"""
Link classifier — decides what to do with every URL found on a page:
  INTERNAL_HTML     → add to crawl frontier
  INTERNAL_DOCUMENT → download as a file (PDF, DOCX, …)
  EXTERNAL          → record but do not crawl
  SKIP              → discard entirely
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"})
_HTML_EXTENSIONS = frozenset({".html", ".htm", ".php", ".aspx", ""})


class LinkType(str, Enum):
    INTERNAL_HTML = "internal_html"
    INTERNAL_DOCUMENT = "internal_document"
    EXTERNAL = "external"
    SKIP = "skip"


@dataclass
class ClassifiedLink:
    url: str
    link_type: LinkType
    priority: int = 0   # higher = crawled sooner (min-heap so stored as negative)


class LinkExtractor:
    def __init__(
        self,
        allowed_domains: List[str],
        skip_path_segments: List[str],
        skip_domains: List[str],
        relevant_keywords: List[str],
    ) -> None:
        self._allowed = allowed_domains
        self._skip_segs = [s.lower() for s in skip_path_segments]
        self._skip_doms = skip_domains
        self._keywords = [k.lower() for k in relevant_keywords]

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def classify(self, url: str) -> ClassifiedLink:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace("www.", "")
        path_lower = parsed.path.lower()

        if any(domain.endswith(d) for d in self._skip_doms):
            return ClassifiedLink(url, LinkType.SKIP)

        is_internal = any(
            domain == d or domain.endswith("." + d)
            for d in self._allowed
        )
        if not is_internal:
            return ClassifiedLink(url, LinkType.EXTERNAL)

        if any(seg in path_lower for seg in self._skip_segs):
            return ClassifiedLink(url, LinkType.SKIP)

        ext = PurePosixPath(parsed.path).suffix.lower()

        if ext in _DOCUMENT_EXTENSIONS:
            return ClassifiedLink(url, LinkType.INTERNAL_DOCUMENT, priority=8)

        # Non-HTML, non-document extension (image, css, js, …) → skip
        if ext and ext not in _HTML_EXTENSIONS:
            return ClassifiedLink(url, LinkType.SKIP)

        priority = self._score(path_lower)
        return ClassifiedLink(url, LinkType.INTERNAL_HTML, priority=priority)

    def crawlable(self, links: List[str]) -> List[ClassifiedLink]:
        """Return only links we should add to the HTML crawl frontier."""
        return [c for c in map(self.classify, links) if c.link_type == LinkType.INTERNAL_HTML]

    def documents(self, links: List[str]) -> List[ClassifiedLink]:
        """Return links that should be downloaded as files."""
        return [c for c in map(self.classify, links) if c.link_type == LinkType.INTERNAL_DOCUMENT]

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _score(self, path: str) -> int:
        return sum(2 for kw in self._keywords if kw in path)
