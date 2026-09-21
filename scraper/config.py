"""Configuratie: retailers.yml + omgevingsvariabelen."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone, tzinfo
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
    enrich: bool = True            # kleur/maten aanvullen via productpagina's
    enrich_limit: int = 150        # max productpagina's per bron per week
    # Firecrawl-varianten: 'listing' crawlt categoriepagina's; 'pages' haalt
    # focus-gefilterde productpagina's uit de sitemap stuk voor stuk op —
    # voor sites zonder bruikbare lijstpagina's (Wibra). Let op: 'pages'
    # kost 1 credit per artikel per week (cap hieronder).
    firecrawl_mode: str = "listing"
    firecrawl_page_cap: int = 120
    # Extra rendertijd per Firecrawl-fetch in ms; 0 = de standaard (5000).
    # Voor rasters die ook na scrollen traag hydrateren (HEMA-hypothese).
    firecrawl_wait_ms: int = 0
    # Kanarie: een bron die aantoonbaar geen data prijsgeeft mag wél elke week
    # opnieuw geprobeerd worden, maar niet tegen de volle prijs. Na dit aantal
    # opvragingen zonder leesbaar artikel stopt de run; levert de kanarie wél
    # iets op, dan loopt hij door tot de gewone cap. 0 = uit (volle run).
    firecrawl_canary: int = 0
    # Proxyklasse voor Firecrawl: '' (standaard), 'basic', 'enhanced'
    # (residentieel IP — de enige route langs een WAF die datacenter-IP's
    # weert, zoals Zeeman's CloudFront sinds 14-09) of 'auto' (basic, en bij
    # een weigering alsnog enhanced). Let op het tarief van je plan.
    firecrawl_proxy: str = ""
    focus_categories: str = ""     # regex: beperk de crawl tot deze categorieën
    focus_product_types: list[str] = field(default_factory=list)  # filter na mapping
    # Toegangsladder voor de lijstroute (scraper/fetch.py): treden in volgorde
    # van goedkoop naar zwaar — http, chrome (curl_cffi-impersonatie), browser
    # (Playwright), firecrawl (betaald, gecapt door firecrawl_page_cap). Leeg =
    # alleen http. De crawl klimt pas bij een aantoonbare weigering (403/429
    # of challenge-pagina) en meldt de gebruikte trede in het weekrapport.
    fetch_ladder: list[str] = field(default_factory=list)
    notes: str = ""


def nl_tz(nu: datetime | None = None) -> tzinfo:
    """Nederlandse tijd zonder externe afhankelijkheid (zoneinfo kan op een
    kale runner ontbreken): CEST van de laatste zondag van maart t/m de
    laatste zondag van oktober, anders CET."""
    nu = nu or datetime.now(timezone.utc)
    jaar = nu.year

    def laatste_zondag(maand: int) -> datetime:
        d = datetime(jaar, maand + 1, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
        return d - timedelta(days=(d.weekday() + 1) % 7)

    zomer = laatste_zondag(3) <= nu < laatste_zondag(10)
    return timezone(timedelta(hours=2 if zomer else 1))


def vandaag_nl(nu: datetime | None = None) -> date:
    """De kalenderdag in Nederland. De runner loopt in UTC: zondag 23:07 UTC
    is in Nederland al maandag, en hoort dus bij de nieuwe week."""
    nu = nu or datetime.now(timezone.utc)
    return nu.astimezone(nl_tz(nu)).date()


def week_monday(d: date | None = None) -> date:
    """De maandag van de ISO-week — onze waarnemingsdatum. Zonder argument:
    de week van vandaag in Nederlandse tijd (niet UTC), zodat een run vlak na
    maandag 00:00 NL niet nog bij de vorige week wordt geboekt."""
    d = d or vandaag_nl()
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
