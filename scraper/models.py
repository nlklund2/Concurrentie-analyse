"""Gedeelde datastructuren."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Product:
    key: str
    title: str
    url: str = ""
    brand: str = ""
    category_raw: str = ""
    color: str = ""
    sizes: str = ""      # aangeboden maten (kommagescheiden), géén voorraadinfo
    price: float | None = None
    was_price: float | None = None
    # Alleen gevuld als de bron het expliciet meldt (schema.org availability);
    # None betekent "onbekend", niet "op voorraad".
    in_stock: bool | None = None


@dataclass
class ScrapeResult:
    retailer_id: str
    strategy: str = ""
    products: list[Product] = field(default_factory=list)
    categories_found: int = 0
    requests_done: int = 0
    # Alleen Firecrawl kost geld; requests_done wordt aan het eind van run()
    # overschreven met de gewone-HTTP-teller en is dus géén creditmeter.
    credits_used: int = 0
    notes: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and len(self.products) > 0
