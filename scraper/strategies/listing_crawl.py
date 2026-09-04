"""Categorielijstpagina's crawlen: het werkpaard voor niet-Shopify-shops.

Per categorie worden pagina's 1..n opgehaald; producten komen uit de in de
pagina ingebedde JSON (JSON-LD / __NEXT_DATA__ / application/json). Dat kost
1 request per ±24-48 artikelen in plaats van 1 per artikel.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from .. import discover
from ..config import RetailerCfg
from ..http import Http
from ..jsonscan import flight_meta, products_from_html
from ..models import Product, ScrapeResult

PAGINATION_PATTERNS = ("?page={n}", "?p={n}", "?pagina={n}")


def category_urls(cfg: RetailerCfg, http: Http, res: ScrapeResult) -> list[str]:
    if cfg.seeds:
        return cfg.seeds[: cfg.max_categories]
    urls: list[str] = []
    for sm in discover.find_sitemaps(http, cfg.base):
        all_urls = discover.sitemap_urls(http, sm, cfg.url_filter)
        _, cats = discover.split_product_category_urls(all_urls)
        urls.extend(cats)
        if len(urls) >= cfg.max_categories:
            break
    if not urls:
        urls = discover.nav_categories(http, cfg.base, cfg.url_filter, cfg.max_categories)
        if urls:
            res.notes.append("categorieën uit navigatie (geen categorie-sitemap gevonden)")
    urls = list(dict.fromkeys(urls))   # dezelfde categorie niet twee keer crawlen
    if cfg.focus_categories and urls:
        rx = re.compile(cfg.focus_categories, re.I)
        focused = [u for u in urls if rx.search(u)]
        if focused:
            res.notes.append(f"focus: {len(focused)} van {len(urls)} categorieën gecrawld")
            urls = focused
        else:
            res.notes.append("focusfilter matchte geen categorie — alle categorieën "
                             "gecrawld; producten worden na de mapping gefilterd")
    return discover.spread_by_audience(urls, cfg.max_categories)


def scrape(cfg: RetailerCfg, http: Http, limit: int | None = None) -> ScrapeResult:
    res = ScrapeResult(retailer_id=cfg.id, strategy="listing")
    cats = category_urls(cfg, http, res)
    res.categories_found = len(cats)
    if not cats:
        res.error = "geen categorie-URLs gevonden (sitemap noch navigatie)"
        return res
    # Welke categorieën gecrawld worden bepaalt of de doelgroep herkenbaar is;
    # zichtbaar maken scheelt gokwerk bij het instellen van `seeds`.
    res.notes.append("gecrawlde categorieën: " + ", ".join(
        urlsplit(u).path for u in cats[:10]))

    seen: dict[str, Product] = {}
    for cat_url in cats:
        cat_path = urlsplit(cat_url).path.strip("/").replace("/", " > ")
        first = http.get(cat_url)
        if first is None:
            continue
        page_products = products_from_html(first.text, cat_url)
        _absorb(seen, page_products, cat_path)
        if not page_products:
            continue
        # De eigen teller van de bron (Next.js-flight: total/totalPages).
        # Daarmee weten we vooraf hoeveel pagina's er zijn én achteraf of de
        # oogst compleet was — zonder die teller is 'geen nieuwe sleutels
        # meer' het enige stopsignaal.
        teller = flight_meta(first.text)
        bekend_pages = teller.get("totalPages") or 0
        cat_keys = {p.key for p in page_products}

        # paginering: probeer patronen tot er één nieuwe producten oplevert.
        # 'Nieuw' is zonder teller: nog niet in de hele oogst gezien. Mét
        # teller: nog niet in déze categorie gezien — Zeeman's lingerie- en
        # ondergoedcategorieën overlappen, en 'alles al gezien bij de vorige
        # categorie' zou de rest van de pagina's onterecht overslaan (eerste
        # proef 04-09: 1.230 van 1.265 vermeldingen).
        pattern = None
        if bekend_pages != 1:
            for pat in PAGINATION_PATTERNS:
                candidate = cat_url + pat.format(n=2)
                resp = http.get(candidate)
                if resp is None:
                    continue
                prods2 = products_from_html(resp.text, candidate)
                nieuw = {p.key for p in prods2} - (cat_keys if bekend_pages else set(seen))
                if prods2 and nieuw:
                    pattern = pat
                    _absorb(seen, prods2, cat_path)
                    cat_keys.update(p.key for p in prods2)
                    break
        if pattern:
            for n in range(3, cfg.max_pages_per_category + 1):
                if bekend_pages and n > bekend_pages:
                    break
                resp = http.get(cat_url + pattern.format(n=n))
                if resp is None:
                    break
                prods_n = products_from_html(resp.text, cat_url)
                new_keys = {p.key for p in prods_n} - (cat_keys if bekend_pages else set(seen))
                _absorb(seen, prods_n, cat_path)
                cat_keys.update(p.key for p in prods_n)
                if not new_keys:
                    break
                if limit and len(seen) >= limit:
                    break
        if teller.get("total"):
            res.coverage[cat_path] = (len(cat_keys), int(teller["total"]))
        if (limit and len(seen) >= limit) or len(seen) >= cfg.max_products:
            break

    if res.coverage:
        geoogst = sum(h for h, _ in res.coverage.values())
        verwacht = sum(t for _, t in res.coverage.values())
        res.notes.append(
            f"tellercontrole: {geoogst} van {verwacht} vermeldingen die de bron zelf "
            f"telt over {len(res.coverage)} categorieën "
            f"({geoogst / verwacht:.0%})" if verwacht else "tellercontrole: bron telt 0")
    res.products = list(seen.values())[: limit or cfg.max_products]
    return res


def _absorb(seen: dict[str, Product], products: list[Product], cat_path: str) -> None:
    for p in products:
        # Het crawlpad draagt de doelgroep ("dames > lingerie"), de bron-categorie
        # vaak alleen het producttype ("Pyjama's"). Allebei bewaren, niet het een
        # door het ander laten verdringen — anders blijft de doelgroep 'onbekend'.
        p.category_raw = _voeg_samen(cat_path, p.category_raw)
        cur = seen.get(p.key)
        if cur is None:
            seen[p.key] = p
        elif cur.price is None and p.price is not None:
            p.category_raw = _voeg_samen(cur.category_raw, p.category_raw)
            seen[p.key] = p
        else:
            cur.category_raw = _voeg_samen(cur.category_raw, p.category_raw)


def _voeg_samen(*delen: str) -> str:
    """Categoriedelen samenvoegen zonder herhaling, gecapt op de kolombreedte."""
    uit: list[str] = []
    for deel in delen:
        deel = (deel or "").strip()
        if deel and deel.lower() not in (u.lower() for u in uit):
            uit.append(deel)
    return " > ".join(uit)[:500]
