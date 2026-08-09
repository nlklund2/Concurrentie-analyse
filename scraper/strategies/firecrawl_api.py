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
from urllib.parse import urljoin, urlsplit

import requests

from .. import discover
from ..config import RetailerCfg
from ..http import Http
from ..jsonscan import products_from_html
from ..models import Product, ScrapeResult
from .listing_crawl import _voeg_samen
from .render_listing import cards_from_html, lees_ankers

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
        # De sitemap is bij deze bronnen net zo geblokkeerd als de rest — maar
        # Firecrawl kan hem wél lezen. Dat is de betrouwbaarste bron: de
        # navigatie bleek bij Wibra alleen productteasers te bevatten.
        cats = _sitemap_via_firecrawl(session, cfg, res)
    if not cats:
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
    uit_kaarten = 0
    for cat_url in cats:
        cat_path = urlsplit(cat_url).path.strip("/").replace("/", " > ")
        html = _firecrawl_html(session, cat_url, res)
        credits += 1
        if html is None:
            if res.error:      # sleutel ongeldig of credits op: stoppen
                break
            continue
        found = products_from_html(html, cat_url)
        if not found:
            # HEMA rendert de lijst wél maar sluit geen JSON in — dan is de
            # kaartweergave zelf de enige bron (zelfde vangnet als de DOM-scan).
            found = cards_from_html(html, cat_url)
            uit_kaarten += len(found)
        for p in found:
            # crawlpad (doelgroep) én bron-categorie (producttype) allebei bewaren
            p.category_raw = _voeg_samen(cat_path, p.category_raw)
            seen.setdefault(p.key, p)
        if (limit and len(seen) >= limit) or len(seen) >= cfg.max_products:
            break
    res.requests_done = credits
    if uit_kaarten:
        res.notes.append(f"kaart-vangnet: {uit_kaarten} artikelen uit de "
                         "gerenderde HTML (geen ingebedde JSON)")
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


def _focus_smal(cats: list[str], cfg: RetailerCfg) -> list[str]:
    """Versmal tot focus-categorieën, maar alleen als er dan iets overblijft."""
    if cats and cfg.focus_categories:
        rx = re.compile(cfg.focus_categories, re.I)
        focused = [u for u in cats if rx.search(u)]
        if focused:
            return focused
    return cats


def _sitemap_via_firecrawl(session: requests.Session, cfg: RetailerCfg,
                           res: ScrapeResult) -> list[str]:
    """Categorieën uit de sitemap, opgehaald via Firecrawl (rawHtml — geen
    rendering nodig, dus goedkoop en betrouwbaar). Max ±5 credits."""
    root = discover.origin(cfg.base)
    for pad in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        xml = _firecrawl_html(session, root + pad, res, raw=True)
        res.requests_done += 1
        if not xml or "<loc" not in xml:
            if res.error:
                return []
            continue
        locs = discover.sitemap_locs(xml)
        if re.search(r"<sitemap[\s>]", xml, re.I):
            # index: alleen de meest belovende sub-sitemaps ophalen
            subs = sorted(locs, key=lambda u: 0 if re.search(
                r"categor|collection|listing", u, re.I) else 1)[:3]
            locs = []
            for sm in subs:
                sub = _firecrawl_html(session, sm, res, raw=True)
                res.requests_done += 1
                if sub:
                    locs.extend(discover.sitemap_locs(sub))
        if cfg.url_filter:
            locs = [u for u in locs if cfg.url_filter in u]
        locs = _zonder_productnamespace(locs)
        _, cats = discover.split_product_category_urls(locs)
        cats = _focus_smal(list(dict.fromkeys(cats)), cfg)
        if cats:
            res.notes.append("categorieën uit de sitemap via Firecrawl")
            return cats
    return []


def _zonder_productnamespace(locs: list[str]) -> list[str]:
    """Padsegmenten waar vrijwel álle sitemap-URLs onder hangen zijn het
    productnamespace (Wibra: duizenden /assortiment/<artikel>/). Die URLs
    zien er voor de padheuristiek uit als categorie ('baby-pyjama-…') maar
    zijn productpagina's; de échte lijstpagina's staan in de rest."""
    from collections import Counter

    def eerste_seg(u: str) -> str:
        segs = [s for s in urlsplit(u).path.split("/") if s]
        return segs[0].lower() if segs else ""

    telling = Counter(eerste_seg(u) for u in locs)
    totaal = len(locs) or 1
    massa = {s for s, n in telling.items() if n > 100 and n / totaal > 0.5}
    return [u for u in locs if eerste_seg(u) not in massa] if massa else locs


def _nav_via_firecrawl(session: requests.Session, cfg: RetailerCfg,
                       res: ScrapeResult) -> list[str]:
    """Categorieën uit de door Firecrawl gerenderde startpagina (1 credit)."""
    html = _firecrawl_html(session, cfg.base, res)
    res.requests_done += 1
    if not html:
        return []
    cats = discover.categories_from_html(html, cfg.base, cfg.url_filter,
                                         cfg.max_categories)
    # Een 'navigatielink' mét prijs in de kaart eromheen is een productteaser,
    # geen categorie — bij Wibra wonnen pyjama-teasers het zo van de echte
    # afdelingen (de prijs staat er búiten het anker, dus kijk naar de kaart).
    met_prijs = set()
    for a in lees_ankers(html):
        if a["href"] and "€" in a["kaart"]:
            p = urlsplit(urljoin(cfg.base, a["href"]))
            met_prijs.add(f"{p.scheme}://{p.netloc}{p.path}")
    cats = [c for c in cats if c not in met_prijs]
    if cfg.focus_categories and cats:
        # focus vooraan sorteren maar niets wegfilteren: bij Wibra droeg geen
        # enkele echte afdeling een focuswoord, en een lege lijst is erger
        # dan een paar credits aan bredere categorieën
        rx = re.compile(cfg.focus_categories, re.I)
        cats.sort(key=lambda u: 0 if rx.search(u) else 1)
    if cats:
        res.notes.append("categorieën via de Firecrawl-gerenderde startpagina "
                         "(sitemap onbereikbaar voor het datacenter-IP)")
    return cats


def _firecrawl_html(session: requests.Session, url: str, res: ScrapeResult,
                    raw: bool = False) -> str | None:
    """raw=True haalt de onbewerkte bron op (sitemap-XML) zonder rendering."""
    payload = {
        "url": url,
        "formats": ["rawHtml"] if raw else ["html"],
        "onlyMainContent": False,
        # HEMA's raster rendert traag; bij 2500 ms was de lijst nog leeg
        "waitFor": 0 if raw else 5000,
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
    d = data.get("data") or {}
    return d.get("rawHtml") or d.get("html")
