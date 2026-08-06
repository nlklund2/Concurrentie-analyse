"""Shopify-winkels: /products.json levert 250 artikelen per request."""
from __future__ import annotations

from ..config import RetailerCfg
from ..http import Http
from ..models import Product, ScrapeResult


def detect(cfg: RetailerCfg, http: Http) -> bool:
    data = http.get(f"{cfg.base.rstrip('/')}/products.json?limit=1", as_json=True)
    return isinstance(data, dict) and "products" in data


def scrape(cfg: RetailerCfg, http: Http, limit: int | None = None) -> ScrapeResult:
    res = ScrapeResult(retailer_id=cfg.id, strategy="shopify")
    base = cfg.base.rstrip("/")
    page = 1
    while True:
        data = http.get(f"{base}/products.json?limit=250&page={page}", as_json=True)
        items = (data or {}).get("products") or []
        if not items:
            break
        for it in items:
            variants = it.get("variants") or [{}]
            v = variants[0]
            price = _price(v.get("price"))
            was = _price(v.get("compare_at_price"))
            cat = it.get("product_type") or ""
            tags = it.get("tags")
            if isinstance(tags, list):
                cat = f"{cat} {' '.join(tags)}".strip()
            res.products.append(Product(
                key=str(it.get("id")),
                title=it.get("title", "").strip(),
                url=f"{base}/products/{it.get('handle', '')}",
                brand=it.get("vendor", "") or "",
                category_raw=cat,
                price=price,
                was_price=was if (was and price and was > price) else None,
            ))
        page += 1
        if limit and len(res.products) >= limit:
            res.products = res.products[:limit]
            break
        if len(res.products) >= cfg.max_products or page > 200:
            res.notes.append("productplafond bereikt")
            break
    return res


def _price(v) -> float | None:
    from ..normalize import parse_price
    return parse_price(v)
