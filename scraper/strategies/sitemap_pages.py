"""Laatste redmiddel: productpagina's stuk voor stuk (alleen kleine assortimenten).

1 request per artikel is duur; boven cfg.sitemap_page_cap wordt deze strategie
geweigerd zodat een run nooit uren op één bron blijft hangen.
"""
from __future__ import annotations

import re

from .. import discover
from ..config import RetailerCfg
from ..http import Http
from ..jsonscan import extract_jsonld, products_from_jsonld
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
    if len(product_urls) > cfg.sitemap_page_cap and not limit:
        res.error = (f"{len(product_urls)} productpagina's is te veel voor deze strategie "
                     f"(cap {cfg.sitemap_page_cap}); gebruik listing of verhoog de cap bewust")
        return res

    cap = limit or cfg.sitemap_page_cap
    for url in product_urls[:cap]:
        resp = http.get(url)
        if resp is None:
            continue
        objs = extract_jsonld(resp.text)
        found = products_from_jsonld(objs, url)
        if found:
            p = found[0]
            if not p.category_raw:
                p.category_raw = _breadcrumb(objs)
            if not p.url:
                p.url = url
            res.products.append(p)
    return res


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
