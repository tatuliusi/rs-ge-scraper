from dataclasses import dataclass


@dataclass
class Document:
    url: str
    text: str
    source: str
    language: str
    status: str = "active"
