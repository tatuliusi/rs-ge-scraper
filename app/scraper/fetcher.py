import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_CONTENT_SIGNALS = ["article", "main", "div.tab-content", "div.page-content"]


def make_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={_USER_AGENT}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(3)
    return driver


def _wait_for_content(driver: webdriver.Chrome, timeout: int = 12) -> bool:
    """Wait until any known content signal appears. Returns True if found."""
    for selector in _CONTENT_SIGNALS:
        try:
            if " " in selector or "." in selector:
                # CSS selector
                WebDriverWait(driver, timeout // len(_CONTENT_SIGNALS)).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
            else:
                WebDriverWait(driver, timeout // len(_CONTENT_SIGNALS)).until(
                    EC.presence_of_element_located((By.TAG_NAME, selector))
                )
            return True
        except (TimeoutException, StaleElementReferenceException):
            continue
    return False


def fetch_page(url: str, driver: webdriver.Chrome, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            driver.get(url)
            found = _wait_for_content(driver)
            if not found:
                time.sleep(3)
            return driver.page_source

        except WebDriverException as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(4 * (attempt + 1))  # back off: 4s, 8s
            else:
                logger.error(f"All retries exhausted for {url}")
    return ""
