"""Prijzen parsen en categorieën mappen naar de uniforme taxonomie."""
from __future__ import annotations

import re
from functools import lru_cache

import yaml

from .config import MAPPING_FILE
from .models import Product

_NUM_RE = re.compile(r"(\d{1,4}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+)(?:\s*,\s*-)?")


def parse_price(value, key_hint: str = "") -> float | None:
    """Zet ruwe prijswaarden om naar euro's.

    Ondersteunt: 4.99, "4,99", "€ 4,99", "1.299,95", "5,-", "vanaf € 3,99",
    en centen-integers (1299 → 12.99; ook <1000 wanneer de veldnaam 'cent' bevat).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        if v <= 0:
            return None
        hint = key_hint.lower()
        if "cent" in hint or (isinstance(value, int) and value >= 1000):
            v = v / 100.0
        return round(v, 2)
    s = str(value).strip()
    if not s:
        return None
    m = _NUM_RE.search(s)
    if not m:
        return None
    num = m.group(1)
    if "," in num and "." in num:
        # laatste scheidingsteken is decimaal
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif "," in num:
        head, _, tail = num.rpartition(",")
        if len(tail) == 3 and head:      # 1,299 → duizendtal
            num = head + tail
        else:
            num = num.replace(",", ".")
    try:
        v = float(num)
    except ValueError:
        return None
    if v <= 0 or v > 10000:
        return None
    return round(v, 2)


@lru_cache(maxsize=1)
def _rules() -> dict:
    raw = yaml.safe_load(MAPPING_FILE.read_text(encoding="utf-8"))
    return {
        "audience": [(r["label"], re.compile(r["match"], re.I)) for r in raw["audience"]],
        "product_type": [(r["label"], re.compile(r["match"], re.I)) for r in raw["product_type"]],
    }


def map_category(category_raw: str, title: str = "", url: str = "") -> tuple[str, str]:
    """(audience, product_type) volgens de regels in mapping.yml.

    Doelgroep: het bronpad weegt zwaarder dan titel/URL (two-pass).
    Producttype: regelvolgorde wint over pad-vs-titel — een pyjama in een
    "lingerie & ondergoed"-pad is nachtmode; de specifiekere regel mag van
    pad óf titel komen (gevalideerd op o.a. Primark).
    """
    rules = _rules()
    primary = (category_raw or "").lower()
    fallback = f"{title or ''} {url or ''}".lower()

    audience = "onbekend"
    for label, rx in rules["audience"]:
        if rx.search(primary):
            audience = label
            break
    else:
        for label, rx in rules["audience"]:
            if rx.search(fallback):
                audience = label
                break

    ptype = "overig"
    for label, rx in rules["product_type"]:
        if rx.search(primary) or rx.search(fallback):
            ptype = label
            break

    return audience, ptype


def to_staging_rows(retailer_id: str, products: list[Product]) -> list[dict]:
    """Ontdubbelt op sleutel en bouwt rijen voor staging_products."""
    seen: dict[str, dict] = {}
    for p in products:
        if not p.key or not p.title:
            continue
        audience, ptype = map_category(p.category_raw, p.title, p.url)
        row = {
            "retailer_id": retailer_id,
            "product_key": p.key[:200],
            "url": (p.url or "")[:1000],
            "title": p.title[:500],
            "brand": (p.brand or "")[:200],
            "category_raw": (p.category_raw or "")[:500],
            "audience": audience,
            "product_type": ptype,
            "color": (p.color or "")[:200],
            "sizes": (p.sizes or "")[:200],
            "price": p.price,
            "was_price": p.was_price if (p.was_price and p.price and p.was_price > p.price) else None,
        }
        # bij dubbele sleutels: rij mét prijs wint, daarna rij mét maten;
        # ontbrekende velden worden aangevuld vanuit de andere waarneming
        old = seen.get(row["product_key"])
        if old is None:
            seen[row["product_key"]] = row
            continue
        best, rest = old, row
        if (old["price"] is None and row["price"] is not None) or \
           (old["price"] is not None) == (row["price"] is not None) and not old["sizes"] and row["sizes"]:
            best, rest = row, old
        for field in ("color", "sizes", "brand", "category_raw", "url", "was_price"):
            if not best.get(field):
                best[field] = rest.get(field) or best.get(field)
        seen[row["product_key"]] = best
    return list(seen.values())


def apply_focus(rows: list[dict], focus_types: list[str]) -> list[dict]:
    """Houd alleen de productgroepen uit de focus over (leeg = alles)."""
    if not focus_types:
        return rows
    wanted = set(focus_types)
    return [r for r in rows if r["product_type"] in wanted]


def mapping_coverage(rows: list[dict]) -> float:
    """Aandeel rijen dat aan een echte groep is toegekend (kwaliteitsmaat)."""
    if not rows:
        return 0.0
    ok = sum(1 for r in rows if r["audience"] != "onbekend" or r["product_type"] != "overig")
    return round(ok / len(rows), 3)
