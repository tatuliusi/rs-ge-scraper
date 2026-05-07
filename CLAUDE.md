# RS.ge scraper architecture

## Purpose
Deep-crawling knowledge base layer for a Georgian tax RAG system.
Targets rs.ge (Revenue Service of Georgia) and infohub.rs.ge.

## Module map

```
app/
├── config.py              CrawlerConfig dataclass — all tunable parameters
├── main.py                FastAPI app with /crawl/start and /crawl/status endpoints
├── models/
│   └── document.py        CrawlResult dataclass (url, text, depth, parent_url, child_urls, …)
└── scraper/
    ├── crawler.py         BFS crawler with priority queue — main orchestrator
    ├── fetcher.py         Selenium (JS pages) + requests (PDFs/binaries)
    ├── parser.py          BS4: extract text + hyperlinks from HTML
    ├── link_extractor.py  Classify links: INTERNAL_HTML / INTERNAL_DOCUMENT / EXTERNAL / SKIP
    ├── pdf_handler.py     pdfplumber — extract text from PDF bytes
    ├── sitemap.py         Discover seed URLs from rs.ge sitemap + infohub search pages
    ├── storage.py         JSONL document store + crawl state for resume
    └── run.py             CLI entry point
```

## Crawl flow

1. `sitemap.py` discovers seed URLs from rs.ge/SiteMap and infohub paginated search.
2. Seeds pushed into a `PriorityQueue` — tax-relevant paths get higher priority score.
3. `crawler.py` pops entries, decides HTML vs document by URL extension or depth == -1.
4. HTML pages → Selenium fetch → BS4 parse → save text → extract links → enqueue children.
5. Document links (PDF/DOCX) → requests fetch → pdfplumber extract → save.
6. `storage.py` deduplicates by SHA-256 content hash, writes to `output/documents.jsonl`.
7. State saved every 50 pages for crash-resume support.

## Running

```bash
# CLI
python -m app.scraper.run
python -m app.scraper.run --depth 3 --pages 500 --no-sitemap

# API server
uvicorn app.main:app --reload
# POST /crawl/start  {"max_depth": 4, "max_pages": 3000, "use_sitemap": true}
# GET  /crawl/status
```

## Output files

| File | Contents |
|---|---|
| `output/documents.jsonl` | One CrawlResult JSON per line |
| `output/crawl_state.json` | Resume state (visited URLs, queue snapshot) |
| `output/failed_urls.txt` | URL + failure reason, tab-separated |
| `output/crawler.log` | Full timestamped log |
