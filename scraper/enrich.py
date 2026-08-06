"""Gecapte verrijking: kleur en maten aanvullen via de productpagina.

Lijstpagina's tonen zelden maten en niet altijd kleur. Voor artikelen die beide
missen (maar wel een URL hebben) halen we de productpagina op en parsen we
dezelfde ingebedde JSON als altijd. Gecapt per bron zodat de weekrun kort en
beleefd blijft; artikelen die nog niet in de database staan (nieuw) gaan voor,
want daar is de informatiewinst het grootst.
"""
from __future__ import annotations

from .config import RetailerCfg
from .http import BlockedError, Http
from .jsonscan import products_from_html
from .models import Product, ScrapeResult


def enrich_products(cfg: RetailerCfg, res: ScrapeResult,
                    known_keys: set[str] | None = None,
                    only_keys: set[str] | None = None) -> int:
    if not cfg.enrich or cfg.enrich_limit <= 0 or not res.products:
        return 0
    kandidaten = [p for p in res.products
                  if p.url and not (p.color and p.sizes)
                  and (only_keys is None or p.key[:200] in only_keys)]
    if not kandidaten:
        return 0
    if known_keys is not None:
        kandidaten.sort(key=lambda p: p.key in known_keys)  # onbekend (nieuw) eerst
    todo = kandidaten[: cfg.enrich_limit]

    http = Http(min_delay=cfg.min_delay, respect_robots=cfg.respect_robots)
    aangevuld = 0
    for p in todo:
        try:
            resp = http.get(p.url)
        except BlockedError:
            res.notes.append("verrijking gestopt: bron blokkeert productpagina's")
            break
        if resp is None:
            continue
        if _merge(p, products_from_html(resp.text, p.url)):
            aangevuld += 1
    res.requests_done += http.requests_done
    res.notes.append(f"verrijking kleur/maten: {aangevuld} van {len(kandidaten)} "
                     f"kandidaten aangevuld (cap {cfg.enrich_limit})")
    return aangevuld


def _merge(p: Product, found: list[Product]) -> bool:
    """Beste match van de productpagina in het bestaande product mengen."""
    match = next((f for f in found if f.key == p.key), None) \
        or next((f for f in found if f.title == p.title), None) \
        or next((f for f in found if f.sizes or f.color), None)
    if match is None:
        return False
    verbeterd = False
    if not p.color and match.color:
        p.color = match.color
        verbeterd = True
    if not p.sizes and match.sizes:
        p.sizes = match.sizes
        verbeterd = True
    if p.was_price is None and match.was_price and p.price and match.was_price > p.price:
        p.was_price = match.was_price
        verbeterd = True
    return verbeterd
