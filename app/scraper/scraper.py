import json
import logging
import time
from pathlib import Path

from .sitemap import fetch_sitemap_urls, clean_urls, get_infohub_article_urls
from .fetcher import make_driver, fetch_page
from .parser import parse_page, text_hash
from ..models.document import Document

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

_RATE_LIMIT_SECONDS = 1.5
_OUTPUT_PATH = Path("output.json")
_FAILED_PATH = Path("failed_urls.txt")
_PROGRESS_PATH = Path("output.jsonl")


def _detect_language(url: str) -> str:
    if "/en/" in url or url.endswith("/en"):
        return "en"
    return "ka"


def _detect_source(url: str) -> str:
    if "infohub.rs.ge" in url:
        return "infohub.rs.ge"
    return "rs.ge"


def _load_already_scraped() -> set[str]:
    """Read progress file to resume from where we left off."""
    seen = set()
    if _PROGRESS_PATH.exists():
        for line in _PROGRESS_PATH.read_text(encoding="utf-8").splitlines():
            try:
                doc = json.loads(line)
                seen.add(doc["url"])
            except Exception:
                continue
    return seen


def scrape_all() -> list[Document]:
    raw_urls = fetch_sitemap_urls()
    rs_urls = clean_urls(raw_urls)
    infohub_urls = get_infohub_article_urls()
    all_urls = rs_urls + infohub_urls

    logger.info(
        f"Total URLs: {len(all_urls)} "
        f"({len(rs_urls)} rs.ge + {len(infohub_urls)} infohub)"
    )

    already_scraped = _load_already_scraped()
    if already_scraped:
        logger.info(f"Resuming — {len(already_scraped)} URLs already done")

    pending = [u for u in all_urls if u not in already_scraped]
    logger.info(f"Pending: {len(pending)} URLs")

    documents: list[Document] = []
    failed_urls: list[str] = []
    seen_hashes: set[str] = set()

    progress_file = _PROGRESS_PATH.open("a", encoding="utf-8")
    driver = make_driver()

    try:
        for i, url in enumerate(pending, 1):
            logger.info(f"[{i}/{len(pending)}] {url}")
            html = fetch_page(url, driver)
            text = parse_page(html)

            if not text:
                logger.warning(f"  Skipped (no valid content)")
                failed_urls.append(url)
                time.sleep(_RATE_LIMIT_SECONDS)
                continue

            h = text_hash(text)
            if h in seen_hashes:
                logger.info(f"  Duplicate content, skipping")
                time.sleep(_RATE_LIMIT_SECONDS)
                continue
            seen_hashes.add(h)

            doc = Document(
                url=url,
                text=text,
                source=_detect_source(url),
                language=_detect_language(url),
            )
            documents.append(doc)

            progress_file.write(json.dumps(vars(doc), ensure_ascii=False) + "\n")
            progress_file.flush()

            time.sleep(_RATE_LIMIT_SECONDS)

    finally:
        driver.quit()
        progress_file.close()

    if failed_urls:
        _FAILED_PATH.write_text("\n".join(failed_urls), encoding="utf-8")
        logger.warning(f"  {len(failed_urls)} failed URLs saved to {_FAILED_PATH}")

    logger.info(f"Done. {len(documents)} unique documents from {len(pending)} URLs")
    return documents


def save_to_json(documents: list[Document], path: Path = _OUTPUT_PATH) -> None:
    data = [vars(doc) for doc in documents]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Saved {len(data)} documents → {path}")


if __name__ == "__main__":
    docs = scrape_all()
    save_to_json(docs)
