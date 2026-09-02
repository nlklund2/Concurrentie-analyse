"""Producten vinden in HTML: JSON-LD, __NEXT_DATA__ en andere ingebedde JSON.

Dit is de generieke motor achter de listing- en sitemap-strategieën. Werkwijze:
1. alle <script type="application/ld+json"> parsen → schema.org Product/ItemList;
2. alle overige JSON-scripts (__NEXT_DATA__, application/json) parsen en
   recursief doorzoeken naar 'product-achtige' objecten (naam + prijsveld).
"""
from __future__ import annotations

import hashlib
import html as html_mod
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

# Productdata die alleen in gewone JS-code zit: dataLayer.push({...}) van
# GTM-ecommerce en window.__STATE__-achtige toestandsobjecten. Wibra's
# productpagina's dragen geen JSON-LD, geen JSON-scripts en geen og:prijs —
# als de data ergens machineleesbaar staat, dan hier.
_JS_STATE_RE = re.compile(
    r"dataLayer\s*(?:\.\s*push\s*\(|\s*=\s*\[)|"
    r"(?:window\s*\.\s*)?__[A-Z][A-Z_]{3,30}__\s*=\s*", re.I)

NAME_KEYS = ("name", "title", "displayName", "productName", "displayTitle")
PRICE_KEYS = ("price", "sellingPrice", "salePrice", "currentPrice", "priceValue",
              "priceIncTax", "unitPrice", "priceInCents", "priceCents", "value", "amount",
              "current", "sales", "finalPrice", "specialPrice", "actualPrice")
WAS_KEYS = ("listPrice", "oldPrice", "originalPrice", "strikePrice", "wasPrice",
            "compareAtPrice", "compare_at_price", "rrp", "recommendedPrice",
            "advertisedPrice", "regularPrice", "strikethroughPrice", "previousPrice",
            "crossedPrice", "basePrice", "was")
KEY_KEYS = ("sku", "productID", "productId", "product_id", "id", "objectID", "code",
            "articleNumber", "articleId", "itemNo", "ean", "mpn", "key",
            # HEMA-tegels (meting 10-08) dragen alleen masterSKU/groupSKU;
            # master eerst — dat is het artikel, group de kleurvariantgroep.
            "masterSKU", "groupSKU")
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
            # HEMA vult een leeg maatveld met het wóórd 'empty'; dat is geen
            # maat en zou de dekkingscijfers vals op 100% zetten.
            if text and text.lower() not in ("empty", "null", "none", "n/a", "-"):
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


def _offer_availability(offers) -> bool | None:
    """Voorraadstatus volgens schema.org availability; None = niet vermeld.

    terStal (Magento) laat verlopen artikelen als pagina bestaan met
    OutOfStock + prijs 0.00 — zulke pagina's zijn geen actief assortiment.
    Bij meerdere offers geldt: één op voorraad = op voorraad; pas als álle
    offers expliciet uitverkocht melden, telt het artikel als uitverkocht.
    """
    lijst = offers if isinstance(offers, list) else [offers]
    gezien: set[bool] = set()
    for o in lijst:
        if not isinstance(o, dict):
            continue
        waarde = str(o.get("availability") or "").lower()
        if not waarde:
            continue
        if any(w in waarde for w in ("outofstock", "soldout", "discontinued")):
            gezien.add(False)
        else:                       # InStock, PreOrder, BackOrder, LimitedAvailability …
            gezien.add(True)
    if True in gezien:
        return True
    if False in gezien:
        return False
    return None


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
                                     price=price, was_price=was,
                                     in_stock=_offer_availability(offers)))
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


def _balanced_blob(text: str, start: int, cap: int = 2_000_000) -> str | None:
    """Het gebalanceerde {...}- of [...]-blok vanaf de eerste opener,
    string-bewust (accolades bínnen "..." tellen niet mee)."""
    i = start
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    if i >= len(text) or text[i] not in "{[":
        return None
    open_c, close_c = text[i], {"{": "}", "[": "]"}[text[i]]
    diepte, in_str, escape = 0, False, False
    for j in range(i, min(len(text), i + cap)):
        c = text[j]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == open_c:
            diepte += 1
        elif c == close_c:
            diepte -= 1
            if diepte == 0:
                return text[i:j + 1]
    return None


def products_from_js_state(html: str, base_url: str = "") -> list[Product]:
    """dataLayer.push / window.__STATE__: JS-objecten met naam én prijs.
    Alleen geldig-JSON-blokken tellen; JS-expressies vallen stil af."""
    products: list[Product] = []
    for n, m in enumerate(_JS_STATE_RE.finditer(html)):
        if n >= 12:
            break
        blob = _balanced_blob(html, m.end())
        if blob is None:
            continue
        data = _json_loads_lenient(blob)
        if data is not None:
            products.extend(deep_find_products(data, base_url))
    return products


# JSON die HTML-ge-escaped in een attribuut zit: ="{&quot;price&quot;:…}".
# HEMA's producttegels (meting 10-08) dragen zo hun naam, SKU en prijs —
# onzichtbaar voor tekst-, script- én dataLayer-lezers.
_ESCAPED_ATTR_RE = re.compile(r'"(\[?\{&quot;[^"]{20,200000}[\}\]])"')


def products_from_escaped_attrs(html: str, base_url: str = "") -> list[Product]:
    products: list[Product] = []
    for n, m in enumerate(_ESCAPED_ATTR_RE.finditer(html)):
        if n >= 400:
            break
        data = _json_loads_lenient(html_mod.unescape(m.group(1)))
        if data is not None:
            products.extend(deep_find_products(data, base_url))
    return products


def products_from_html(html: str, base_url: str = "") -> list[Product]:
    """Alle beschikbare extractiemethoden op één pagina, ontdubbeld op sleutel."""
    products: list[Product] = []
    products.extend(products_from_jsonld(extract_jsonld(html), base_url))

    for rx in (_NEXTDATA_RE, _JSONSCRIPT_RE):
        for m in rx.finditer(html):
            data = _json_loads_lenient(m.group(1))
            if data is not None:
                products.extend(deep_find_products(data, base_url))
    products.extend(products_from_js_state(html, base_url))
    products.extend(products_from_escaped_attrs(html, base_url))

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
