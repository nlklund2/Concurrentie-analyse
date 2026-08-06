"""Configuratie: retailers.yml + omgevingsvariabelen."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yaml

PKG_DIR = Path(__file__).parent
RETAILERS_FILE = PKG_DIR / "retailers.yml"
MAPPING_FILE = PKG_DIR / "mapping.yml"
OUT_DIR = Path(os.environ.get("MONITOR_OUT_DIR", "out"))


@dataclass
class RetailerCfg:
    id: str
    name: str
    base: str                      # start-URL inclusief landen-/taalpad
    segment: str = "kern"
    enabled: bool = True
    strategy: str = "auto"         # auto | shopify | listing | sitemap_pages
    url_filter: str = ""           # substring waaraan product-/categorie-URLs moeten voldoen
    seeds: list[str] = field(default_factory=list)  # handmatige categorie-URLs (optioneel)
    min_delay: float = 0.7
    max_categories: int = 40
    max_pages_per_category: int = 40
    max_products: int = 30000
    sitemap_page_cap: int = 2500   # boven deze omvang geen productpagina-strategie
    min_products_expected: int = 25
    respect_robots: bool = True
    focus_categories: str = ""     # regex: beperk de crawl tot deze categorieën
    focus_product_types: list[str] = field(default_factory=list)  # filter na mapping
    notes: str = ""


def week_monday(d: date | None = None) -> date:
    """De maandag van de ISO-week — onze waarnemingsdatum."""
    d = d or date.today()
    return d - timedelta(days=d.weekday())


def load_retailers(only: list[str] | None = None, include_disabled: bool = False) -> list[RetailerCfg]:
    raw = yaml.safe_load(RETAILERS_FILE.read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    out: list[RetailerCfg] = []
    for rid, cfg in raw["retailers"].items():
        merged = {**defaults, **(cfg or {})}
        merged.pop("color_slot", None)  # alleen voor het dashboard van betekenis
        rc = RetailerCfg(id=rid, **merged)
        if only and rid not in only:
            continue
        if not rc.enabled and not include_disabled and not only:
            continue
        out.append(rc)
    if only:
        missing = set(only) - {r.id for r in out}
        if missing:
            raise SystemExit(f"Onbekende retailer(s): {', '.join(sorted(missing))}")
    return out


def focus_product_types() -> list[str]:
    """De focus uit de defaults (voor de scope-regel in het weekrapport)."""
    raw = yaml.safe_load(RETAILERS_FILE.read_text(encoding="utf-8"))
    return (raw.get("defaults") or {}).get("focus_product_types") or []


def env(name: str, required: bool = False) -> str | None:
    val = os.environ.get(name)
    if required and not val:
        raise SystemExit(f"Omgevingsvariabele {name} ontbreekt.")
    return val
