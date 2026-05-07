from dataclasses import dataclass, field
from typing import List


@dataclass
class CrawlerConfig:
    # --- Seeds ---
    seed_urls: List[str] = field(default_factory=lambda: [
        "https://rs.ge/ka/PersonsTaxes",
        "https://rs.ge/ka/LegalEntityTaxes",
        "https://rs.ge/ka/Legislation",
        "https://infohub.rs.ge/ka/search?types=57",
        "https://infohub.rs.ge/ka/search?types=64",
    ])

    # --- Crawl limits ---
    max_depth: int = 4          # how many link-hops from seed
    max_pages: int = 3000       # stop after this many saved documents
    rate_limit_seconds: float = 1.5
    max_retries: int = 3
    retry_delay: float = 4.0    # base delay; multiplied by attempt number

    # --- Domain scope ---
    allowed_domains: List[str] = field(default_factory=lambda: [
        "rs.ge",
        "infohub.rs.ge",
    ])

    # --- Output ---
    output_dir: str = "output"
    documents_file: str = "output/documents.jsonl"
    failed_urls_file: str = "output/failed_urls.txt"
    state_file: str = "output/crawl_state.json"

    # --- Content validation ---
    min_content_length: int = 200
    min_word_count: int = 30
    require_georgian: bool = False  # set True to skip non-Georgian pages

    # --- URL scoring: paths with these keywords get higher crawl priority ---
    relevant_path_keywords: List[str] = field(default_factory=lambda: [
        "PersonsTaxes", "LegalEntityTaxes", "Legislation", "Tax",
        "CustomsDeclaration", "Declaration", "VATTax", "IncomeTax",
        "PropertyTax", "article", "news", "document", "info",
        "gadasaxadi", "saxelmcifo",   # Georgian: tax, state
        "freelancer", "individual", "income",
    ])

    # --- URL segments that should never be crawled ---
    skip_path_segments: List[str] = field(default_factory=lambda: [
        "/gallery", "/vacancy", "/emailus", "/contact",
        "/login", "/register", "/print", "/sitemap", "/rss", "/feed",
        "/en/",     # focus on Georgian-language pages
    ])

    # --- External domains to ignore ---
    skip_domains: List[str] = field(default_factory=lambda: [
        "youtube.com", "facebook.com", "twitter.com", "instagram.com",
        "asycuda.org", "google.com", "linkedin.com",
    ])

    # --- Extensions treated as downloadable documents ---
    document_extensions: List[str] = field(default_factory=lambda: [
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ])


config = CrawlerConfig()
