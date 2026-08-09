"""Laatste redmiddel: productpagina's stuk voor stuk (alleen kleine assortimenten).

1 request per artikel is duur; boven cfg.sitemap_page_cap wordt deze strategie
geweigerd zodat een run nooit uren op één bron blijft hangen.
"""
from __future__ import annotations

import re

from .. import discover
from ..config import RetailerCfg
from ..http import Http
from ..jsonscan import extract_jsonld, products_from_html, products_from_jsonld
from ..models import Product, ScrapeResult


def scrape(cfg: RetailerCfg, http: Http, limit: int | None = None) -> ScrapeResult:
    res = ScrapeResult(retailer_id=cfg.id, strategy="sitemap_pages")
    product_urls: list[str] = []
    for sm in discover.find_sitemaps(http, cfg.base):
        urls = discover.sitemap_urls(http, sm, cfg.url_filter)
        prods, _ = discover.split_product_category_urls(urls)
        product_urls.extend(prods)
    product_urls = list(dict.fromkeys(product_urls))
    if cfg.focus_categories and product_urls:
        rx = re.compile(cfg.focus_categories, re.I)
        focused = [u for u in product_urls if rx.search(u)]
        if focused:
            res.notes.append(f"focus: {len(focused)} van {len(product_urls)} product-URLs")
            product_urls = focused
    if not product_urls:
        res.error = "geen product-URLs in sitemap gevonden"
        return res

    # Boven de cap: vaste (gesorteerde) steekproef i.p.v. weigeren — een stabiele
    # deelwaarneming geeft bruikbare week-op-week-trends; tellingen zijn dan wel
    # een ondergrens, geen totaal (zichtbaar via de notitie in het rapport).
    cap = limit or cfg.sitemap_page_cap
    if len(product_urls) > cap:
        product_urls.sort()
        res.notes.append(f"{len(product_urls)} product-URLs binnen focus; vaste "
                         f"steekproef van {cap} pagina's — tellingen zijn een "
                         "deelwaarneming, trends blijven vergelijkbaar")
    gemist = 0
    for url in product_urls[:cap]:
        resp = http.get(url)
        if resp is None:
            continue
        objs = extract_jsonld(resp.text)
        found = products_from_jsonld(objs, url)
        if not found:
            # Lang niet elke shop zet JSON-LD op de productpagina (Zeeman bv. niet);
            # val terug op de volledige scan: __NEXT_DATA__ en andere ingebedde JSON.
            found = products_from_html(resp.text, url)
        if not found:
            gemist += 1
            continue
        p = max(found, key=lambda x: (x.price is not None, len(x.title or "")))
        # Het URL-pad draagt bij vrijwel elke shop de doelgroep ("/dames/ondergoed/");
        # samen met de breadcrumb geeft dat de mapping het sterkste signaal.
        p.category_raw = " ".join(x for x in (
            _breadcrumb(objs), p.category_raw, _pad(url)) if x)[:500]
        if not p.url:
            p.url = url
        res.products.append(p)
    if gemist:
        res.notes.append(f"{gemist} productpagina's zonder leesbare productdata")
    return res


def _pad(url: str) -> str:
    """Het URL-pad als categoriesignaal, bv. 'dames ondergoed slips'."""
    from urllib.parse import urlsplit
    segs = [s for s in urlsplit(url).path.split("/") if s]
    return " ".join(s.replace("-", " ") for s in segs[:-1])


def _breadcrumb(objs: list) -> str:
    for o in objs:
        if isinstance(o, dict) and o.get("@type") == "BreadcrumbList":
            items = o.get("itemListElement") or []
            names = []
            for it in items:
                if isinstance(it, dict):
                    name = it.get("name") or (it.get("item") or {}).get("name") \
                        if isinstance(it.get("item"), dict) else it.get("name")
                    if name:
                        names.append(str(name))
            if names:
                return " > ".join(names)
    return ""
