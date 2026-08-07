"""Fase-2b-strategie: Firecrawl — externe scrape-dienst met residentiële proxies.

Voor bronnen die het datacenter-IP van GitHub Actions categorisch weren (bv.
Wibra, HEMA): een eigen headless browser helpt daar niet, want het probleem is
het herkenbare server-IP, niet de browser. Firecrawl draait de scrape vanaf
roterende residentiële IP's en geeft gerenderde HTML terug, waarna we dezelfde
JSON-/DOM-extractie toepassen als altijd.

BEWUSTE AFWEGING (zie PLAN.md §8):
- Kost geld: gratis start (~500 pagina's eenmalig), daarna ±€16/mnd hobby-tier.
- Stuurt de te scrapen product-URL's naar een derde partij.
- Alleen actief met FIRECRAWL_API_KEY; zonder key blijft de bron eerlijk rood.
Daarom is dit een aparte, expliciet te kiezen strategie (`strategy: firecrawl`),
geen automatische stap in de waterval.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import requests

from .. import discover
from ..config import RetailerCfg
from ..http import Http
from ..jsonscan import products_from_html
from ..models import Product, ScrapeResult

FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"


def scrape(cfg: RetailerCfg, http: Http, limit: int | None = None) -> ScrapeResult:
    res = ScrapeResult(retailer_id=cfg.id, strategy="firecrawl")
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        res.error = ("FIRECRAWL_API_KEY niet gezet — deze bron blijft ongescrapet. "
                     "Zet de sleutel als GitHub-secret om Firecrawl te activeren "
                     "(betaalde dienst, zie PLAN.md §8).")
        return res

    cats = _category_urls(cfg, http, res)
    if not cats:
        res.error = "geen categorie-URLs gevonden om via Firecrawl op te halen"
        return res
    cats = cats[: cfg.max_categories]
    res.categories_found = len(cats)

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"})
    seen: dict[str, Product] = {}
    credits = 0
    for cat_url in cats:
        cat_path = urlsplit(cat_url).path.strip("/").replace("/", " > ")
        html = _firecrawl_html(session, cat_url, res)
        credits += 1
        if html is None:
            continue
        for p in products_from_html(html, cat_url):
            if not p.category_raw:
                p.category_raw = cat_path
            seen.setdefault(p.key, p)
        if (limit and len(seen) >= limit) or len(seen) >= cfg.max_products:
            break
    res.requests_done = credits
    res.notes.append(f"{credits} Firecrawl-credits gebruikt (± {credits} pagina's)")
    res.products = list(seen.values())[: limit or cfg.max_products]
    if not res.products and not res.error:
        res.error = "Firecrawl leverde HTML maar geen producten — extractie nalopen"
    return res


def _category_urls(cfg: RetailerCfg, http: Http, res: ScrapeResult) -> list[str]:
    """Categorieën uit seeds of sitemap. De sitemap zelf kan ook geblokkeerd
    zijn voor het datacenter-IP; dan zijn expliciete `seeds` nodig."""
    if cfg.seeds:
        return list(cfg.seeds)
    cats: list[str] = []
    try:
        for sm in discover.find_sitemaps(http, cfg.base):
            urls = discover.sitemap_urls(http, sm, cfg.url_filter)
            _, sm_cats = discover.split_product_category_urls(urls)
            cats.extend(sm_cats)
            if len(cats) >= cfg.max_categories * 3:
                break
    except Exception:
        pass
    if cats and cfg.focus_categories:
        import re
        rx = re.compile(cfg.focus_categories, re.I)
        focused = [u for u in cats if rx.search(u)]
        if focused:
            cats = focused
    if not cats:
        res.notes.append("geen categorie-sitemap bereikbaar — voeg `seeds` toe in "
                         "retailers.yml (categorie-URLs) om Firecrawl te sturen")
    return cats


def _firecrawl_html(session: requests.Session, url: str, res: ScrapeResult) -> str | None:
    payload = {
        "url": url,
        "formats": ["html"],
        "onlyMainContent": False,
        "waitFor": 2500,
        "timeout": 30000,
        "location": {"country": "NL", "languages": ["nl-NL"]},
    }
    try:
        r = session.post(FIRECRAWL_ENDPOINT, json=payload, timeout=60)
    except requests.RequestException as e:
        res.notes.append(f"Firecrawl-netwerkfout: {str(e)[:120]}")
        return None
    if r.status_code == 402:
        res.error = "Firecrawl-credits op (HTTP 402) — tegoed bijvullen of tier verhogen"
        return None
    if r.status_code == 401:
        res.error = "Firecrawl-sleutel ongeldig (HTTP 401)"
        return None
    if r.status_code >= 400:
        res.notes.append(f"Firecrawl HTTP {r.status_code} op {url[:60]}")
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    return (data.get("data") or {}).get("html")
