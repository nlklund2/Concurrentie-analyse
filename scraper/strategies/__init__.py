"""Strategieregister + automatische keuze (waterval van goedkoop naar duur)."""
from __future__ import annotations

from ..config import RetailerCfg
from ..http import BlockedError, Http
from ..models import ScrapeResult
from . import listing_crawl, shopify, sitemap_pages

FIXED = {
    "shopify": shopify.scrape,
    "listing": listing_crawl.scrape,
    "sitemap_pages": sitemap_pages.scrape,
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
