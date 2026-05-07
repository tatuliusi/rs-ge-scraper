"""
Crawl state and document persistence.

Documents are written to a JSONL file (one JSON object per line) so the
output can be streamed and resumed without loading everything into memory.
State (visited URLs, content hashes, queue snapshot) is persisted to a
JSON file every N pages so a crashed run can be resumed.
"""
import json
import logging
import os
from dataclasses import asdict
from typing import Any, Dict, List, Set

from app.models.document import CrawlResult

logger = logging.getLogger(__name__)


class CrawlStorage:
    def __init__(
        self,
        output_dir: str,
        documents_file: str,
        failed_urls_file: str,
        state_file: str,
    ) -> None:
        self._docs_path = documents_file
        self._failed_path = failed_urls_file
        self._state_path = state_file

        os.makedirs(output_dir, exist_ok=True)

        self._visited: Set[str] = set()
        self._hashes: Set[str] = set()
        self._doc_count = 0

        # Keep the JSONL file open for appending throughout the run
        self._doc_fh = open(documents_file, "a", encoding="utf-8")

    # ------------------------------------------------------------------
    # State persistence (resume support)
    # ------------------------------------------------------------------

    def load_state(self) -> Dict[str, Any]:
        """
        Load a previously saved state file.
        Returns the raw dict (callers can pull `queue_snapshot` from it).
        """
        if not os.path.exists(self._state_path):
            return {}
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                state = json.load(fh)
            self._visited = set(state.get("visited_urls", []))
            self._hashes = set(state.get("content_hashes", []))
            self._doc_count = state.get("doc_count", 0)
            logger.info(
                "Resumed: %d visited URLs, %d documents already saved",
                len(self._visited),
                self._doc_count,
            )
            return state
        except Exception as exc:
            logger.warning("Could not load state (%s) — starting fresh.", exc)
            return {}

    def save_state(self, queue_snapshot: list) -> None:
        state = {
            "visited_urls": list(self._visited),
            "content_hashes": list(self._hashes),
            "doc_count": self._doc_count,
            "queue_snapshot": queue_snapshot,
        }
        with open(self._state_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # URL tracking
    # ------------------------------------------------------------------

    def is_visited(self, url: str) -> bool:
        return url in self._visited

    def mark_visited(self, url: str) -> None:
        self._visited.add(url)

    # ------------------------------------------------------------------
    # Document storage
    # ------------------------------------------------------------------

    def is_duplicate_content(self, content_hash: str) -> bool:
        return content_hash in self._hashes

    def save_document(self, doc: CrawlResult) -> bool:
        """
        Persist a document.
        Returns False (and skips) if the content is a duplicate.
        """
        if self.is_duplicate_content(doc.content_hash):
            logger.debug("Duplicate content — skipping %s", doc.url)
            return False

        self._hashes.add(doc.content_hash)
        self._doc_count += 1

        self._doc_fh.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")
        self._doc_fh.flush()

        logger.info(
            "[%d] Saved %-60s  depth=%d  type=%s",
            self._doc_count,
            doc.url[:60],
            doc.depth,
            doc.doc_type,
        )
        return True

    def log_failed(self, url: str, reason: str = "") -> None:
        with open(self._failed_path, "a", encoding="utf-8") as fh:
            fh.write(f"{url}\t{reason}\n")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def doc_count(self) -> int:
        return self._doc_count

    @property
    def visited_count(self) -> int:
        return len(self._visited)

    def close(self) -> None:
        self._doc_fh.close()
