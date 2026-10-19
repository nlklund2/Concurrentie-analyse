"""Strategieregister + automatische keuze (waterval van goedkoop naar duur)."""
from __future__ import annotations

import re

from ..config import RetailerCfg
from ..http import BlockedError, Http
from ..models import ScrapeResult
from . import firecrawl_api, listing_crawl, render_listing, shopify, sitemap_pages

def sleutel_uit_url(result: ScrapeResult, patroon: str) -> None:
    """Artikelsleutel uit de URL halen (cfg.key_from_url).

    Action wisselde t/m W40 elke week de id in zijn ingebedde JSON: 716
    sleutels voor ±220 artikelen, dus elke week ±40% schijn-instroom en
    -uitstroom. Het productnummer in de URL bleef gelijk. Artikelen zonder
    match houden hun sleutel; dubbele sleutels worden samengevoegd (eerste wint).
    """
    rx = re.compile(patroon)
    gezien: dict[str, object] = {}
    for p in result.products:
        m = rx.search(p.url or "")
        if m and m.group(1):
            p.key = m.group(1)
        gezien.setdefault(p.key, p)
    if len(gezien) < len(result.products):
        result.notes.append(f"sleutel uit URL: {len(result.products) - len(gezien)} "
                            "dubbele artikelen samengevoegd")
    result.products = list(gezien.values())


FIXED = {
    "shopify": shopify.scrape,
    "listing": listing_crawl.scrape,
    "sitemap_pages": sitemap_pages.scrape,
    "render": render_listing.scrape,     # fase-2: headless browser (Playwright)
    "firecrawl": firecrawl_api.scrape,   # fase-2b: externe dienst met proxies (betaald)
}


def run(cfg: RetailerCfg, limit: int | None = None) -> ScrapeResult:
    http = Http(min_delay=cfg.min_delay, respect_robots=cfg.respect_robots)
    result = ScrapeResult(retailer_id=cfg.id)
    try:
        if cfg.strategy in FIXED:
            result = FIXED[cfg.strategy](cfg, http, limit)
        else:
            result = _auto(cfg, http, limit)
    except BlockedError as e:
        result.error = str(e)
        result.notes.append("Bron blokkeert geautomatiseerde toegang; overweeg fase-2 "
                            "(headless browser) of accepteer uitval van deze bron.")
    except Exception as e:  # één bron mag nooit de hele weekrun breken
        result.error = f"{type(e).__name__}: {e}"
    result.retailer_id = cfg.id
    if cfg.key_from_url:
        sleutel_uit_url(result, cfg.key_from_url)
    if result.strategy == "firecrawl":
        # requests_done telt hierboven de Firecrawl-aanroepen; bewaar die als
        # creditverbruik vóór de teller hieronder de gewone-HTTP-stand krijgt.
        # (Week 33 rapporteerde hierdoor 'Wibra 0, HEMA 1 credit' — onwaar.)
        result.credits_used = result.requests_done
    result.requests_done = http.requests_done
    if http.robots_skipped:
        result.notes.append(f"{http.robots_skipped} URL(s) overgeslagen wegens robots.txt.")
    return result


def _auto(cfg: RetailerCfg, http: Http, limit: int | None) -> ScrapeResult:
    """1) Shopify-JSON, 2) categorielijstpagina's, 3) productpagina's (klein)."""
    if shopify.detect(cfg, http):
        return shopify.scrape(cfg, http, limit)

    res = listing_crawl.scrape(cfg, http, limit)
    if res.ok:
        return res

    res2 = sitemap_pages.scrape(cfg, http, limit)
    if res2.ok:
        res2.notes = res.notes + res2.notes
        return res2

    res2.notes = res.notes + res2.notes
    res2.error = res2.error or res.error or "geen strategie leverde producten op"
    return res2
