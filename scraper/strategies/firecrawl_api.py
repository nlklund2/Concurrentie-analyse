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
import re
from urllib.parse import urlsplit

import requests

from .. import discover
from ..config import RetailerCfg
from ..http import Http
from ..jsonscan import products_from_html
from ..models import Product, ScrapeResult
from .listing_crawl import _voeg_samen

FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"


def scrape(cfg: RetailerCfg, http: Http, limit: int | None = None) -> ScrapeResult:
    res = ScrapeResult(retailer_id=cfg.id, strategy="firecrawl")
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        res.error = ("FIRECRAWL_API_KEY niet gezet — deze bron blijft ongescrapet. "
                     "Zet de sleutel als GitHub-secret om Firecrawl te activeren "
                     "(betaalde dienst, zie PLAN.md §8).")
        return res

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"})

    cats = _category_urls(cfg, http, res)
    if not cats:
        # De sitemap is bij deze bronnen vaak net zo geblokkeerd als de rest;
        # haal dan de startpagina óók via Firecrawl en lees de navigatie.
        cats = _nav_via_firecrawl(session, cfg, res)
    if not cats:
        # een al gezette fout (401/402) is de échte oorzaak — niet overschrijven
        res.error = res.error or (
            "geen categorie-URLs gevonden (sitemap én startpagina) — "
            "voeg `seeds` toe in retailers.yml om Firecrawl te sturen")
        return res
    cats = discover.spread_by_audience(cats, cfg.max_categories)
    res.categories_found = len(cats)
    res.notes.append("gecrawlde categorieën: " + ", ".join(
        urlsplit(u).path for u in cats[:10]))
    seen: dict[str, Product] = {}
    credits = res.requests_done   # navigatie-opvraag telt mee
    for cat_url in cats:
        cat_path = urlsplit(cat_url).path.strip("/").replace("/", " > ")
        html = _firecrawl_html(session, cat_url, res)
        credits += 1
        if html is None:
            if res.error:      # sleutel ongeldig of credits op: stoppen
                break
            continue
        for p in products_from_html(html, cat_url):
            # crawlpad (doelgroep) én bron-categorie (producttype) allebei bewaren
            p.category_raw = _voeg_samen(cat_path, p.category_raw)
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
        rx = re.compile(cfg.focus_categories, re.I)
        focused = [u for u in cats if rx.search(u)]
        if focused:
            cats = focused
    return cats


def _nav_via_firecrawl(session: requests.Session, cfg: RetailerCfg,
                       res: ScrapeResult) -> list[str]:
    """Categorieën uit de door Firecrawl gerenderde startpagina (1 credit)."""
    html = _firecrawl_html(session, cfg.base, res)
    res.requests_done += 1
    if not html:
        return []
    cats = discover.categories_from_html(html, cfg.base, cfg.url_filter,
                                         cfg.max_categories)
    if cfg.focus_categories and cats:
        rx = re.compile(cfg.focus_categories, re.I)
        focused = [u for u in cats if rx.search(u)]
        if focused:
            cats = focused
    if cats:
        res.notes.append("categorieën via de Firecrawl-gerenderde startpagina "
                         "(sitemap onbereikbaar voor het datacenter-IP)")
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
