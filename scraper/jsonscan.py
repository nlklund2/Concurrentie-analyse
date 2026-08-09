"""Producten vinden in HTML: JSON-LD, __NEXT_DATA__ en andere ingebedde JSON.

Dit is de generieke motor achter de listing- en sitemap-strategieën. Werkwijze:
1. alle <script type="application/ld+json"> parsen → schema.org Product/ItemList;
2. alle overige JSON-scripts (__NEXT_DATA__, application/json) parsen en
   recursief doorzoeken naar 'product-achtige' objecten (naam + prijsveld).
"""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit

from .models import Product
from .normalize import parse_price

_LDJSON_RE = re.compile(
    r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I)
_JSONSCRIPT_RE = re.compile(
    r'<script[^>]*type\s*=\s*["\']application/json["\'][^>]*>(.*?)</script>',
    re.S | re.I)
_NEXTDATA_RE = re.compile(
    r'<script[^>]+id\s*=\s*["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', re.S | re.I)

NAME_KEYS = ("name", "title", "displayName", "productName", "displayTitle")
PRICE_KEYS = ("price", "sellingPrice", "salePrice", "currentPrice", "priceValue",
              "priceIncTax", "unitPrice", "priceInCents", "priceCents", "value", "amount",
              "current", "sales", "finalPrice", "specialPrice", "actualPrice")
WAS_KEYS = ("listPrice", "oldPrice", "originalPrice", "strikePrice", "wasPrice",
            "compareAtPrice", "compare_at_price", "rrp", "recommendedPrice",
            "advertisedPrice", "regularPrice", "strikethroughPrice", "previousPrice",
            "crossedPrice", "basePrice", "was")
KEY_KEYS = ("sku", "productID", "productId", "product_id", "id", "objectID", "code",
            "articleNumber", "articleId", "itemNo", "ean", "mpn", "key")
URL_KEYS = ("url", "productUrl", "link", "href", "slug", "seoUrl", "pdpUrl", "path")
BRAND_KEYS = ("brand", "brandName", "vendor", "manufacturer")
CATEGORY_KEYS = ("category", "categoryPath", "breadcrumb", "categories", "productType",
                 "primaryCategory", "categoryName")
COLOR_KEYS = ("color", "colour", "kleur", "colorName", "colourName", "baseColor",
              "colorDescription", "variantColor", "colorFamily", "mainColor")
SIZE_KEYS = ("sizes", "maten", "availableSizes", "sizeVariants", "sizeList",
             "availableSizeNames", "size")


def _text_from(value) -> str:
    """Kleur/maat-velden zijn strings, getallen, lijsten of {name/value}-dicts."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        parts = [_text_from(v) for v in value]
        return ", ".join(p for p in parts if p)
    if isinstance(value, dict):
        for k in ("name", "value", "label", "text"):
            v = value.get(k)
            if isinstance(v, (str, int, float)):
                return str(v).strip()
    return ""


def _attr_from(d: dict, keys) -> str:
    for k in keys:
        if k in d and d[k] is not None:
            text = _text_from(d[k])
            if text:
                return text
    return ""


def url_key(url: str) -> str:
    """Stabiele sleutel uit een product-URL (pad zonder querystring)."""
    path = urlsplit(url).path.rstrip("/")
    return hashlib.sha1(path.encode()).hexdigest()[:16]


def _json_loads_lenient(text: str):
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        # veelvoorkomend: trailing commas of afgekapte blokken — dan overslaan
        return None


def extract_jsonld(html: str) -> list:
    out = []
    for m in _LDJSON_RE.finditer(html):
        data = _json_loads_lenient(m.group(1))
        if data is None:
            continue
        out.extend(data if isinstance(data, list) else [data])
    return out


def _offer_prices(offers) -> tuple[float | None, float | None]:
    if offers is None:
        return None, None
    if isinstance(offers, list):
        offers = offers[0] if offers else None
        if offers is None:
            return None, None
    if not isinstance(offers, dict):
        return None, None
    price = parse_price(offers.get("price") or offers.get("lowPrice"))
    was = None
    spec = offers.get("priceSpecification")
    if isinstance(spec, list):
        for s in spec:
            if isinstance(s, dict) and s.get("priceType", "").endswith("ListPrice"):
                was = parse_price(s.get("price"))
    return price, was


def products_from_jsonld(objs: list, base_url: str = "") -> list[Product]:
    """schema.org Product-objecten (los, in @graph of in ItemList)."""
    found: list[Product] = []

    def walk(node):
        if isinstance(node, list):
            for x in node:
                walk(x)
            return
        if not isinstance(node, dict):
            return
        t = node.get("@type", "")
        types = t if isinstance(t, list) else [t]
        if "Product" in types:
            url = urljoin(base_url, str(node.get("url") or node.get("@id") or ""))
            price, was = _offer_prices(node.get("offers"))
            brand = node.get("brand")
            if isinstance(brand, dict):
                brand = brand.get("name", "")
            key = str(node.get("sku") or node.get("productID") or node.get("mpn") or "") \
                or (url_key(url) if url else "")
            cat = node.get("category") or ""
            if isinstance(cat, dict):
                cat = cat.get("name", "")
            color = _text_from(node.get("color"))
            sizes = _text_from(node.get("size"))
            offers = node.get("offers")
            if not sizes and isinstance(offers, list):
                offer_sizes = [_text_from(o.get("size")) for o in offers if isinstance(o, dict)]
                sizes = ", ".join(dict.fromkeys(s for s in offer_sizes if s))
            name = str(node.get("name") or "").strip()
            if name and key:
                found.append(Product(key=str(key), title=name, url=url,
                                     brand=str(brand or ""), category_raw=str(cat),
                                     color=color, sizes=sizes,
                                     price=price, was_price=was))
        for v in node.values():
            if isinstance(v, (dict, list)):
                walk(v)

    walk(objs)
    return found


def _first_key(d: dict, keys) -> tuple[str, object]:
    for k in keys:
        if k in d and d[k] is not None:
            return k, d[k]
    return "", None


def _price_from(value, key_hint: str) -> float | None:
    """Prijsvelden kunnen scalair zijn of geneste dicts ({value: 4.99})."""
    if isinstance(value, dict):
        for k in PRICE_KEYS:
            if k in value:
                return _price_from(value[k], k)
        return None
    if isinstance(value, (int, float, str)):
        return parse_price(value, key_hint)
    return None


def _looks_like_product(d: dict) -> bool:
    has_name = any(k in d and isinstance(d[k], str) and d[k].strip() for k in NAME_KEYS)
    has_price = any(k in d for k in PRICE_KEYS + WAS_KEYS + ("prices", "priceInfo", "price_info"))
    return has_name and has_price


def deep_find_products(obj, base_url: str = "", _depth: int = 0) -> list[Product]:
    """Doorzoekt willekeurige JSON (bv. __NEXT_DATA__) naar productobjecten."""
    found: list[Product] = []
    if _depth > 12:
        return found
    if isinstance(obj, list):
        for x in obj:
            found.extend(deep_find_products(x, base_url, _depth + 1))
        return found
    if not isinstance(obj, dict):
        return found

    if _looks_like_product(obj):
        _, name = _first_key(obj, NAME_KEYS)
        price = None
        for k in PRICE_KEYS:
            if k in obj:
                price = _price_from(obj[k], k)
                if price is not None:
                    break
        if price is None:
            for holder in ("prices", "priceInfo", "price_info"):
                if isinstance(obj.get(holder), dict):
                    price = _price_from(obj[holder], holder)
                    break
        was = None
        for k in WAS_KEYS:
            if k in obj:
                was = _price_from(obj[k], k)
                if was is not None:
                    break
        _, rawurl = _first_key(obj, URL_KEYS)
        url = urljoin(base_url, str(rawurl)) if rawurl else ""
        _, rawkey = _first_key(obj, KEY_KEYS)
        key = str(rawkey) if rawkey else (url_key(url) if url else "")
        _, brand = _first_key(obj, BRAND_KEYS)
        if isinstance(brand, dict):
            brand = brand.get("name", "")
        cat = ""
        for k in CATEGORY_KEYS:
            v = obj.get(k)
            if isinstance(v, str):
                cat = v
                break
            if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                cat = " > ".join(v)
                break
        if key and price is not None:
            found.append(Product(key=key, title=str(name).strip(), url=url,
                                 brand=str(brand or ""), category_raw=cat,
                                 color=_attr_from(obj, COLOR_KEYS),
                                 sizes=_attr_from(obj, SIZE_KEYS),
                                 price=price, was_price=was))
            return found  # niet verder afdalen in een gevonden product

    for v in obj.values():
        if isinstance(v, (dict, list)):
            found.extend(deep_find_products(v, base_url, _depth + 1))
    return found


# Microdata (schema.org in HTML-attributen). Veel shops zetten geen JSON-LD
# neer maar wél <meta itemprop="price" content="7.99">. Zonder deze route
# missen we op zulke productpagina's de prijs — bij terStal bleef daardoor 57%
# van de artikelen prijsloos.
_MICRO_PRICE_RE = re.compile(
    r'itemprop\s*=\s*["\'](?:price|lowPrice)["\'][^>]*?content\s*=\s*["\']([^"\']+)["\']'
    r'|content\s*=\s*["\']([^"\']+)["\'][^>]*?itemprop\s*=\s*["\'](?:price|lowPrice)["\']',
    re.I)
# Bewust géén 'highPrice': dat is in schema.org de bovenkant van een prijsréeks
# over varianten, niet de doorgestreepte oude prijs. Als was-prijs opvoeren zou
# korting verzinnen en de sale-druk in het weekrapport opblazen.
_MICRO_WAS_RE = re.compile(
    r'itemprop\s*=\s*["\']listPrice["\'][^>]*?content\s*=\s*["\']([^"\']+)["\']', re.I)
_META_PROP_RE = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*["\'](?:product:price:amount|og:price:amount|'
    r'twitter:data1)["\'][^>]+content\s*=\s*["\']([^"\']+)["\']', re.I)


def price_from_microdata(html: str) -> tuple[float | None, float | None]:
    """(prijs, was-prijs) uit microdata en og:-metatags van een productpagina."""
    prijs = was = None
    for m in _MICRO_PRICE_RE.finditer(html):
        prijs = parse_price(m.group(1) or m.group(2))
        if prijs is not None:
            break
    if prijs is None:
        for m in _META_PROP_RE.finditer(html):
            prijs = parse_price(m.group(1))
            if prijs is not None:
                break
    m = _MICRO_WAS_RE.search(html)
    if m:
        was = parse_price(m.group(1))
    return prijs, (was if (was and prijs and was > prijs) else None)


_OG_TITLE_RE = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*["\']og:title["\'][^>]+content\s*=\s*["\']([^"\']+)["\']'
    r'|<meta[^>]+content\s*=\s*["\']([^"\']+)["\'][^>]+(?:property|name)\s*=\s*["\']og:title["\']',
    re.I)


def product_from_meta(html: str, url: str) -> Product | None:
    """Vangnet voor productpagina's zonder ingebedde JSON: og:title plus de
    micro-/metaprijs. Vrijwel elke webshop zet deze tags voor social shares."""
    m = _OG_TITLE_RE.search(html)
    titel = (m.group(1) or m.group(2)).strip() if m else ""
    titel = titel.split(" | ")[0].strip()   # "…naam | Winkelnaam" → naam
    prijs, was = price_from_microdata(html)
    if not titel or prijs is None:
        return None
    return Product(key=url_key(url), title=titel[:200], url=url,
                   price=prijs, was_price=was)


def products_from_html(html: str, base_url: str = "") -> list[Product]:
    """Alle beschikbare extractiemethoden op één pagina, ontdubbeld op sleutel."""
    products: list[Product] = []
    products.extend(products_from_jsonld(extract_jsonld(html), base_url))

    for rx in (_NEXTDATA_RE, _JSONSCRIPT_RE):
        for m in rx.finditer(html):
            data = _json_loads_lenient(m.group(1))
            if data is not None:
                products.extend(deep_find_products(data, base_url))

    unique: dict[str, Product] = {}
    for p in products:
        cur = unique.get(p.key)
        if cur is None:
            unique[p.key] = p
            continue
        if cur.price is None and p.price is not None:
            unique[p.key], cur, p = p, p, cur
        # ontbrekende velden aanvullen vanuit de andere waarneming
        for field in ("color", "sizes", "brand", "category_raw", "url"):
            if not getattr(cur, field) and getattr(p, field):
                setattr(cur, field, getattr(p, field))
        if cur.was_price is None and p.was_price is not None:
            cur.was_price = p.was_price
    return list(unique.values())
