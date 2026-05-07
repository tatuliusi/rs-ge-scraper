"""
Main crawler — BFS with a priority queue.

Priority queue entry:  (-priority, depth, url, parent_url)
Using negative priority because Python's heapq / PriorityQueue is a min-heap,
so a higher relevance score → more negative number → popped first.

Special depth value:
  depth == -1  →  URL is a downloadable document (PDF etc.), not an HTML page.
                  It bypasses the max_depth check and is fetched with requests
                  instead of Selenium.
"""
import logging
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath
from queue import PriorityQueue
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import undetected_chromedriver as uc

from app.config import CrawlerConfig, config as _default_cfg
from app.models.document import CrawlResult, DocType
from app.scraper.fetcher import fetch_binary, fetch_page, make_driver
from app.scraper.link_extractor import LinkExtractor
from app.scraper.parser import extract_links, extract_title, has_georgian, parse_page
from app.scraper.pdf_handler import extract_text as extract_pdf_text
from app.scraper.storage import CrawlStorage

logger = logging.getLogger(__name__)

_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".doc", ".docx", ".xls", ".xlsx"})
_STATE_SAVE_EVERY = 50   # pages between automatic state saves

# Type alias for a frontier entry
_Entry = Tuple[int, int, str, Optional[str]]   # (-priority, depth, url, parent_url)


class Crawler:
    """
    Depth-aware BFS crawler for rs.ge / infohub.rs.ge.

    Usage::

        from app.scraper.crawler import Crawler
        from app.scraper.sitemap import get_all_seed_urls

        seeds = get_all_seed_urls()
        Crawler().run(seeds)
    """

    def __init__(self, cfg: CrawlerConfig = _default_cfg) -> None:
        self.cfg = cfg
        self.storage = CrawlStorage(
            output_dir=cfg.output_dir,
            documents_file=cfg.documents_file,
            failed_urls_file=cfg.failed_urls_file,
            state_file=cfg.state_file,
        )
        self.extractor = LinkExtractor(
            allowed_domains=cfg.allowed_domains,
            skip_path_segments=cfg.skip_path_segments,
            skip_domains=cfg.skip_domains,
            relevant_keywords=cfg.relevant_path_keywords,
        )
        self._frontier: PriorityQueue[_Entry] = PriorityQueue()
        self._driver: Optional[uc.Chrome] = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, seed_urls: Optional[List[str]] = None) -> None:
        """
        Start (or resume) a crawl.

        If *seed_urls* is None the seeds from ``cfg.seed_urls`` are used.
        """
        logger.info("=== Crawler starting ===")

        state = self.storage.load_state()

        if state.get("queue_snapshot"):
            logger.info("Restoring frontier from saved state…")
            for entry in state["queue_snapshot"]:
                self._frontier.put(tuple(entry))
        else:
            seeds = seed_urls or self.cfg.seed_urls
            logger.info("Seeding frontier with %d URLs", len(seeds))
            for url in seeds:
                self._enqueue_html(url, depth=0, parent_url=None, priority=10)

        self._driver = make_driver()
        try:
            self._loop()
        finally:
            self._driver.quit()
            self.storage.close()
            logger.info(
                "=== Crawl finished — %d documents saved, %d URLs visited ===",
                self.storage.doc_count,
                self.storage.visited_count,
            )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        pages_since_save = 0

        while (
            not self._frontier.empty()
            and self.storage.doc_count < self.cfg.max_pages
        ):
            neg_pri, depth, url, parent_url = self._frontier.get()

            if self.storage.is_visited(url):
                continue
            self.storage.mark_visited(url)

            # ---- Route by type ----------------------------------------
            is_document = (depth == -1) or self._is_document_url(url)

            if is_document:
                self._handle_document(url, parent_url)
            else:
                self._handle_html(url, depth, parent_url)

            # ---- Housekeeping -----------------------------------------
            time.sleep(self.cfg.rate_limit_seconds)

            pages_since_save += 1
            if pages_since_save >= _STATE_SAVE_EVERY:
                self._save_state()
                pages_since_save = 0

        # Final state save
        self._save_state()

    # ------------------------------------------------------------------
    # HTML page handler
    # ------------------------------------------------------------------

    def _handle_html(self, url: str, depth: int, parent_url: Optional[str]) -> None:
        logger.info("HTML  [depth=%d] %s", depth, url)

        html = fetch_page(
            self._driver,
            url,
            retries=self.cfg.max_retries,
            delay=self.cfg.retry_delay,
        )
        if html is None:
            self.storage.log_failed(url, "fetch_failed")
            return

        text, content_hash = parse_page(
            html,
            min_length=self.cfg.min_content_length,
            min_words=self.cfg.min_word_count,
        )

        if not text:
            self.storage.log_failed(url, "no_content")
            return

        if self.cfg.require_georgian and not has_georgian(text):
            logger.debug("No Georgian text — skipping %s", url)
            return

        # Extract all outbound links
        raw_links = extract_links(html, url)
        crawlable = self.extractor.crawlable(raw_links)
        doc_links = self.extractor.documents(raw_links)

        child_urls = [c.url for c in crawlable] + [c.url for c in doc_links]

        doc = CrawlResult(
            url=url,
            text=text,
            source=self._source(url),
            language=self._language(url),
            depth=depth,
            parent_url=parent_url,
            child_urls=child_urls,
            doc_type=DocType.HTML,
            content_hash=content_hash,
            title=extract_title(html),
            scraped_at=_now(),
        )
        self.storage.save_document(doc)

        # Enqueue child HTML pages (respect max depth)
        if depth < self.cfg.max_depth:
            for cl in crawlable:
                if not self.storage.is_visited(cl.url):
                    self._enqueue_html(cl.url, depth + 1, url, cl.priority)

        # Enqueue document links regardless of HTML depth
        for dl in doc_links:
            if not self.storage.is_visited(dl.url):
                self._enqueue_doc(dl.url, parent_url=url)

    # ------------------------------------------------------------------
    # Document (PDF/DOCX/…) handler
    # ------------------------------------------------------------------

    def _handle_document(self, url: str, parent_url: Optional[str]) -> None:
        logger.info("DOC   %s", url)

        content = fetch_binary(url)
        if content is None:
            self.storage.log_failed(url, "binary_fetch_failed")
            return

        ext = PurePosixPath(urlparse(url).path).suffix.lower()
        doc_type = _ext_to_doc_type(ext)

        text: Optional[str] = None
        if doc_type == DocType.PDF:
            text = extract_pdf_text(content)

        if not text:
            # We still record that the document exists, even without text
            text = f"[binary document — text extraction not available for {ext}]"

        from app.scraper.parser import _sha256  # local import to avoid circular
        doc = CrawlResult(
            url=url,
            text=text,
            source=self._source(url),
            language=self._language(url),
            depth=-1,
            parent_url=parent_url,
            child_urls=[],
            doc_type=doc_type,
            content_hash=_sha256(text),
            title="",
            scraped_at=_now(),
        )
        self.storage.save_document(doc)

    # ------------------------------------------------------------------
    # Queue helpers
    # ------------------------------------------------------------------

    def _enqueue_html(
        self,
        url: str,
        depth: int,
        parent_url: Optional[str],
        priority: int = 0,
    ) -> None:
        self._frontier.put((-priority, depth, url, parent_url))

    def _enqueue_doc(self, url: str, parent_url: Optional[str]) -> None:
        # depth = -1 signals "download as document"
        self._frontier.put((-8, -1, url, parent_url))

    def _save_state(self) -> None:
        snapshot = list(self._frontier.queue)
        self.storage.save_state(snapshot)
        logger.info("State saved — %d entries in frontier", len(snapshot))

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _is_document_url(url: str) -> bool:
        ext = PurePosixPath(urlparse(url).path).suffix.lower()
        return ext in _DOCUMENT_EXTENSIONS

    @staticmethod
    def _source(url: str) -> str:
        return "infohub.rs.ge" if "infohub" in url else "rs.ge"

    @staticmethod
    def _language(url: str) -> str:
        path = urlparse(url).path
        return "en" if "/en/" in path or path.endswith("/en") else "ka"


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ext_to_doc_type(ext: str) -> DocType:
    mapping = {
        ".pdf": DocType.PDF,
        ".doc": DocType.WORD,
        ".docx": DocType.WORD,
        ".xls": DocType.EXCEL,
        ".xlsx": DocType.EXCEL,
    }
    return mapping.get(ext, DocType.UNKNOWN)
