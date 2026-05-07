from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DocType(str, Enum):
    HTML = "html"
    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    UNKNOWN = "unknown"


@dataclass
class CrawlResult:
    url: str
    text: str
    source: str           # "rs.ge" | "infohub.rs.ge"
    language: str         # "ka"    | "en"
    depth: int = 0        # hop count from the nearest seed URL
    parent_url: Optional[str] = None
    child_urls: List[str] = field(default_factory=list)   # links found inside this page
    doc_type: DocType = DocType.HTML
    content_hash: str = ""
    title: str = ""
    status: str = "active"
    scraped_at: str = ""
