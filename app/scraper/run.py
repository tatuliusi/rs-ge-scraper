"""
Entry point — run from the project root:

    python -m app.scraper.run
    # or
    venv/Scripts/python.exe app/scraper/run.py

Flags (all optional, override config defaults):
    --depth N       max crawl depth  (default: 4)
    --pages N       max documents    (default: 3000)
    --no-sitemap    skip sitemap discovery, use only config seed_urls
    --resume        force resume even if state file exists (default: auto)
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("output/crawler.log", encoding="utf-8", mode="a"),
    ],
)

from app.config import config
from app.scraper.crawler import Crawler
from app.scraper.sitemap import get_all_seed_urls


def main() -> None:
    parser = argparse.ArgumentParser(description="RS.ge deep crawler")
    parser.add_argument("--depth", type=int, default=None)
    parser.add_argument("--pages", type=int, default=None)
    parser.add_argument("--no-sitemap", action="store_true")
    args = parser.parse_args()

    if args.depth is not None:
        config.max_depth = args.depth
    if args.pages is not None:
        config.max_pages = args.pages

    seed_urls = None
    if not args.no_sitemap:
        seed_urls = get_all_seed_urls()

    Crawler(config).run(seed_urls)


if __name__ == "__main__":
    main()
