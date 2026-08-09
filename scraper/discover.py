"""Sitemaps en categorie-URLs vinden zonder per-site maatwerk."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit

from .http import Http

_LOC_RE = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S | re.I)
_SITEMAP_TAG_RE = re.compile(r"<sitemap>", re.I)
_HREF_RE = re.compile(r'href\s*=\s*["\']([^"\'#]+)["\']', re.I)

# padwoorden die op een categorie-/overzichtspagina duiden
CATEGORY_WORDS = re.compile(
    r"dames|heren|vrouwen|mannen|jongens|meisjes|meiden|baby|kind|kids|"
    r"ondergoed|lingerie|nacht|pyjama|"
    r"sokken|panty|schoen|sneaker|laarzen|sport|jassen|truien|broeken|jeans|shirts|"
    r"jurken|rokken|badmode|zwem|accessoires|huishoud|wonen|textiel|sale|aanbieding", re.I)

# doelgroepwoorden in een categoriepad — nodig om bij het afkappen niet één
# doelgroep te bevoordelen
AUDIENCE_WORDS = re.compile(
    r"dames|vrouwen|women|ladies|heren|mannen|\bmen\b|jongens|\bboys?\b|"
    r"meisjes|meiden|\bgirls?\b|baby|kinder|\bkids\b|junior", re.I)

# padwoorden die juist géén categorie zijn
NOISE_WORDS = re.compile(
    r"klantenservice|service|contact|vacature|retour|verzend|voorwaarden|privacy|cookie|"
    r"winkels|store-?locator|blog|nieuws|account|login|wishlist|cart|winkelwagen|"
    r"giftcard|cadeaukaart|folder|\.pdf$|\.jpg$|\.png$|"
    # kleur-/maatfilters van een categorie die we toch al crawlen (KiK: /c_wit)
    r"/c_[a-z]{3,}|"
    # redactionele pagina's die assortimentswoorden bevatten maar geen artikelen
    # tonen (Zeeman: /inspiratie/ons-damesondergoed, /over-zeeman/onze-producten)
    r"/inspiratie/|/over-[a-z]+/|/magazine|/lookbook|/verhalen|/advies", re.I)


def origin(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def find_sitemaps(http: Http, base: str) -> list[str]:
    """Sitemap-URLs uit robots.txt, met gangbare fallbacks."""
    root = origin(base)
    sitemaps: list[str] = []
    resp = http.get(f"{root}/robots.txt")
    if resp is not None:
        for line in resp.text.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemaps.append(line.split(":", 1)[1].strip())
    if not sitemaps:
        for cand in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
            probe = http.get(root + cand)
            if probe is not None and "<" in probe.text[:200]:
                sitemaps.append(root + cand)
                break
    return sitemaps


def sitemap_urls(http: Http, sitemap_url: str, url_filter: str = "",
                 max_files: int = 40, _depth: int = 0) -> list[str]:
    """Alle <loc>-URLs, sitemap-indexen één niveau diep volgend."""
    if _depth > 2:
        return []
    resp = http.get(sitemap_url)
    if resp is None:
        return []
    text = resp.text
    locs = _LOC_RE.findall(text)
    if _SITEMAP_TAG_RE.search(text):  # index van sitemaps
        urls: list[str] = []
        # eerst sub-sitemaps die op producten lijken, dan de rest
        ranked = sorted(locs, key=lambda u: 0 if re.search(r"product|prod", u, re.I) else 1)
        for sm in ranked[:max_files]:
            urls.extend(sitemap_urls(http, sm, url_filter, max_files, _depth + 1))
            if len(urls) > 100000:
                break
        return urls
    if url_filter:
        locs = [u for u in locs if url_filter in u]
    return locs


def split_product_category_urls(urls: list[str]) -> tuple[list[str], list[str]]:
    """Heuristiek: product-URLs hebben lange slugs of /p/-patronen; categorie-
    URLs zijn kort en bevatten assortimentswoorden."""
    products, categories = [], []
    for u in urls:
        path = urlsplit(u).path
        if NOISE_WORDS.search(u):
            continue
        segs = [s for s in path.split("/") if s]
        last = segs[-1] if segs else ""
        if re.search(r"/p/|/product/|/products/|/artikel/", path) or \
           re.search(r"\d{4,}", last) or len(last) > 45:
            products.append(u)
        elif CATEGORY_WORDS.search(path) and len(segs) <= 4:
            categories.append(u)
    return products, categories


def spread_by_audience(urls: list[str], cap: int) -> list[str]:
    """Categorielijst afkappen zonder één doelgroep te bevoordelen.

    Een op diepte en lengte gesorteerde lijst is alfabetisch geclusterd. Bij
    KiK leverden de eerste 20 van 500 categorieën daardoor uitsluitend 'dames'
    op, waarna de bron in week 32 als damesspeciaalzaak in de cijfers stond —
    203 artikelen, nul heren. Ronde voor ronde één categorie per doelgroep
    houdt de volgorde bínnen een doelgroep intact en de dekking evenwichtig.
    """
    if cap <= 0:
        return []
    if len(urls) <= cap:
        return urls
    groepen: dict[str, list[str]] = {}
    for u in urls:
        m = AUDIENCE_WORDS.search(urlsplit(u).path)
        groepen.setdefault(m.group(0).lower() if m else "", []).append(u)
    uit: list[str] = []
    while len(uit) < cap:
        ronde = [g for g in groepen.values() if g]
        if not ronde:
            break
        for groep in ronde:
            uit.append(groep.pop(0))
            if len(uit) >= cap:
                break
    return uit


def nav_categories(http: Http, base: str, url_filter: str = "", cap: int = 40) -> list[str]:
    """Categorie-URLs uit de navigatie van de startpagina."""
    resp = http.get(base)
    if resp is None:
        return []
    host = urlsplit(base).netloc
    seen: dict[str, None] = {}
    for href in _HREF_RE.findall(resp.text):
        full = urljoin(base, href)
        p = urlsplit(full)
        if p.netloc != host or NOISE_WORDS.search(full):
            continue
        if url_filter and url_filter not in full:
            continue
        path = p.path
        segs = [s for s in path.split("/") if s]
        if CATEGORY_WORDS.search(path) and 1 <= len(segs) <= 4:
            clean = f"{p.scheme}://{p.netloc}{path}"
            seen.setdefault(clean, None)
        if len(seen) >= cap * 3:
            break
    # kortste paden eerst: hoofdcategorieën vangen hun subcategorieën af
    ranked = sorted(seen, key=lambda u: (urlsplit(u).path.count("/"), len(u)))
    return ranked[:cap]
