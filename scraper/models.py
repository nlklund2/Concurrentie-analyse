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
    # Ruwe promotekst van de kaart/tegel ('2 voor € 7,50', '1+1 gratis',
    # '-30%'), zoals gevangen door promo.promo_fragmenten — stap A van het
    # promotievormen-onderzoek: vangen en meten, nog niet interpreteren.
    promo_text: str = ""
    # Verpakkingsgrootte zoals de kaart hem verraadt via de stukprijs
    # ("€ 4,95 € 2,48/st" → 2; KiK "(2,50 € / Stuk)"), voor bronnen die de
    # pack-grootte niet in de artikelnaam zetten. 0 = geen aanwijzing;
    # normalize.to_staging_rows laat de artikelnaam voorgaan.
    pack_hint: int = 0


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
    # Tellercontrole: per gecrawlde categorie (geoogste sleutels, aantal
    # volgens de teller van de bron zelf). Alleen gevuld als de bron die
    # teller meestuurt (Next.js-flight: "total"). De kwaliteitspoort keurt
    # een week af als de oogst meer dan 5% onder de eigen telling blijft —
    # groencriterium 3 uit docs/validaties/2026-08-19-zeeman-paginering.md.
    coverage: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.error and len(self.products) > 0
