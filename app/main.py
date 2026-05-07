import logging
import threading

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="RS.ge Scraper API")

_crawl_thread: threading.Thread | None = None


class CrawlRequest(BaseModel):
    max_depth: int = 4
    max_pages: int = 3000
    use_sitemap: bool = True


@app.get("/")
def root():
    return {"status": "ok", "service": "rs.ge scraper"}


@app.post("/crawl/start")
def start_crawl(req: CrawlRequest, background_tasks: BackgroundTasks):
    """
    Kick off a background crawl.
    Only one crawl can run at a time.
    """
    global _crawl_thread

    if _crawl_thread and _crawl_thread.is_alive():
        raise HTTPException(status_code=409, detail="A crawl is already running.")

    def _run():
        from app.config import config
        from app.scraper.crawler import Crawler
        from app.scraper.sitemap import get_all_seed_urls

        config.max_depth = req.max_depth
        config.max_pages = req.max_pages

        seeds = get_all_seed_urls() if req.use_sitemap else None
        Crawler(config).run(seeds)

    _crawl_thread = threading.Thread(target=_run, daemon=True, name="crawler")
    _crawl_thread.start()

    return {"status": "started", "config": req.model_dump()}


@app.get("/crawl/status")
def crawl_status():
    running = _crawl_thread is not None and _crawl_thread.is_alive()
    return {"running": running}
