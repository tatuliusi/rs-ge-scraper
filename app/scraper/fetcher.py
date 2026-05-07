"""
Fetcher module — two strategies:
  1. Selenium (undetected-chromedriver) for JS-rendered HTML pages.
  2. requests for static resources (PDFs, binary files).
"""
import logging
import time
from typing import Optional

import requests
import undetected_chromedriver as uc
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

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

_PAGE_LOAD_TIMEOUT = 20
_CONTENT_WAIT_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Selenium driver
# ---------------------------------------------------------------------------

def make_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={_USER_AGENT}")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")

    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(_PAGE_LOAD_TIMEOUT)
    return driver


def fetch_page(
    driver: uc.Chrome,
    url: str,
    retries: int = 3,
    delay: float = 4.0,
) -> Optional[str]:
    """Fetch a URL with Selenium. Returns raw HTML or None on failure."""
    for attempt in range(retries):
        try:
            driver.get(url)
            _wait_for_content(driver)
            return driver.page_source
        except TimeoutException:
            logger.warning("Timeout on %s (attempt %d/%d)", url, attempt + 1, retries)
        except (WebDriverException, StaleElementReferenceException) as exc:
            logger.warning("WebDriver error on %s: %s (attempt %d/%d)", url, exc, attempt + 1, retries)

        if attempt < retries - 1:
            time.sleep(delay * (attempt + 1))

    return None


def _wait_for_content(driver: uc.Chrome) -> None:
    wait = WebDriverWait(driver, _CONTENT_WAIT_TIMEOUT)
    for selector in _CONTENT_SELECTORS:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return
        except TimeoutException:
            continue


# ---------------------------------------------------------------------------
# Binary / PDF fetcher (plain requests — no JS needed)
# ---------------------------------------------------------------------------

def fetch_binary(url: str, timeout: int = 30) -> Optional[bytes]:
    """Download binary content (PDF, DOCX, …). Returns bytes or None."""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
            stream=True,
        )
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as exc:
        logger.warning("Failed to fetch binary %s: %s", url, exc)
        return None
