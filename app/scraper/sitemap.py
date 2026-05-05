import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE = "https://rs.ge"
_SITEMAP_URL = "https://rs.ge/SiteMap"

_SKIP_PREFIXES = (
    "tel:", "mailto:", "javascript:",
    "https://www.youtube.", "https://www.facebook.",
    "http://asycuda.", "http://newzone.", "http://www.revenue.",
)

_SKIP_PATHS = {
    "/", "/gallery", "/Vacancy", "/EmailUs", "/SiteMap",
    "/PublicInfo", "/Contact", "/VideoInstructions",
}

_RELEVANT_PATH_PREFIXES = (
    "/PersonsTaxes",
    "/PersonsPreferentialTax",
    "/PersonsTaxAdministration",
    "/PersonsAccountingDocuments",
    "/PersonsTaxFAQ",
    "/PersonsRights",
    "/LegalEntityTaxes",
    "/LegalEntityPreferentialTax",
    "/LegalEntityTaxAdministration",
    "/LegalEntityAccountingDocuments",
    "/LegalEntityTaxFAQ",
    "/LegalEntityRights",
    "/Legislation",
    "/TaxPayer",
    "/SituationalManuals",
    "/TaxPrivileges",
    "/PayerPermissions",
    "/UsefulInformation",
    "/PreliminaryDecision",
    "/Agreements",
    "/ApplicationForms",
    "/OrdersoftheHeadoftheRevenueService",
    "/MountainRegion",
    "/CompanyStatus",
    "/CharityOrganization",
)


def fetch_sitemap_urls() -> list[str]:
    response = requests.get(_SITEMAP_URL, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return [link["href"] for link in soup.find_all("a") if link.get("href")]


def clean_urls(urls: list[str]) -> list[str]:
    cleaned = set()
    for url in urls:
        if any(url.startswith(p) for p in _SKIP_PREFIXES):
            continue

        if url.startswith("/"):
            if url in _SKIP_PATHS:
                continue
            if not any(url.startswith(p) for p in _RELEVANT_PATH_PREFIXES):
                continue
            cleaned.add(_BASE + url)

        elif url.startswith(f"{_BASE}/"):
            path = url[len(_BASE):]
            if path in _SKIP_PATHS:
                continue
            if not any(path.startswith(p) for p in _RELEVANT_PATH_PREFIXES):
                continue
            cleaned.add(url)

        elif url.startswith("https://infohub.rs.ge"):
            cleaned.add(url)

    return sorted(cleaned)


def get_infohub_article_urls() -> list[str]:
    """Paginate through infohub search results and collect individual article URLs."""
    article_urls = set()
    search_bases = [
        "https://infohub.rs.ge/ka/search?types=57",
        "https://infohub.rs.ge/ka/search?types=64",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; rs-ge-scraper/1.0)"}

    for base in search_bases:
        page = 1
        consecutive_empty = 0
        while consecutive_empty < 2:
            url = f"{base}&page={page}"
            try:
                resp = requests.get(url, timeout=15, headers=headers)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                found = [
                    "https://infohub.rs.ge" + l["href"]
                    for l in soup.find_all("a", href=True)
                    if l["href"].startswith("/ka/article/")
                    or l["href"].startswith("/ka/news/")
                ]
                if not found:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0
                    article_urls.update(found)
                    logger.info(f"infohub page {page}: found {len(found)} articles")
                page += 1
            except Exception as e:
                logger.warning(f"Failed fetching infohub {url}: {e}")
                break

    return sorted(article_urls)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    urls = fetch_sitemap_urls()
    clean = clean_urls(urls)
    print(f"rs.ge relevant pages: {len(clean)}")
    for u in clean:
        print(" ", u)
    infohub = get_infohub_article_urls()
    print(f"\ninfohub articles: {len(infohub)}")
