"""Fase-2b-strategie: Firecrawl — externe scrape-dienst met residentiële proxies.

Voor bronnen die het datacenter-IP van GitHub Actions categorisch weren (bv.
Wibra, HEMA): een eigen headless browser helpt daar niet, want het probleem is
het herkenbare server-IP, niet de browser. Firecrawl draait de scrape vanaf
roterende residentiële IP's en geeft gerenderde HTML terug, waarna we dezelfde
JSON-/DOM-extractie toepassen als altijd.

BEWUSTE AFWEGING (zie PLAN.md §8):
- Kost geld: gratis start (~500 pagina's eenmalig), daarna ±€16/mnd hobby-tier.
- Stuurt de te scrapen product-URL's naar een derde partij.
- Alleen actief met FIRECRAWL_API_KEY; zonder key blijft de bron eerlijk rood.
Daarom is dit een aparte, expliciet te kiezen strategie (`strategy: firecrawl`),
geen automatische stap in de waterval.
"""
from __future__ import annotations

import os
import re
import time
from urllib.parse import urljoin, urlsplit

import requests

from .. import discover
from ..config import RetailerCfg
from ..http import Http
from ..jsonscan import product_from_meta, products_from_html
from ..models import Product, ScrapeResult
from .listing_crawl import _voeg_samen
from .render_listing import cards_from_html, lees_ankers
from .sitemap_pages import _eigen_product

FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v1/scrape"

# Het gratis tier staat ±10 scrapes per minuut toe. Zonder tempo eronder
# kaatste elke categoriefetch op HTTP 429 (validatierun 18: 19 van de 20).
PAUZE_TUSSEN_CALLS = 6.5
WACHT_BIJ_429 = (12, 30)
_laatste_call = [0.0]

# HEMA's productraster laadt lui: zonder scrollen bevat de snapshot alleen de
# promoblokken erboven (run 19 las koffie en koekjes als 'bodywear').
# Zelfde recept als onze eigen browser bij Action/C&A: scrollen en wachten.
ACTIES_SCROLL = [
    {"type": "wait", "milliseconds": 1500},
    {"type": "scroll", "direction": "down"},
    {"type": "wait", "milliseconds": 1200},
    {"type": "scroll", "direction": "down"},
    {"type": "wait", "milliseconds": 1200},
]

_PRIJS_LOS_RE = re.compile(r"(?<![\d.,])\d{1,4}[.,]\d{2}(?![.,]?\d)")
_API_HINT_RE = re.compile(
    r"https?://[^\s\"'<>\\]{6,140}(?:api|graphql|search|catalog)[^\s\"'<>\\]{0,80}",
    re.I)


def _signalen(html: str) -> str:
    """Compacte meting van een pagina die niets opleverde: waar zou extractie
    op kúnnen aanhaken? Elke fetch kost een credit, dus meet meteen mee in
    plaats van later een aparte diagnoserit te rijden."""
    apis: list[str] = []
    for m in _API_HINT_RE.finditer(html):
        u = m.group(0).split("?")[0][:90]
        if u not in apis:
            apis.append(u)
        if len(apis) >= 3:
            break
    jsonld = html.count("application/ld+json")
    jscripts = html.count("application/json") - jsonld
    return (f"{len(html)} tekens, {html.count('€')}×€, "
            f"{len(_PRIJS_LOS_RE.findall(html))} prijsachtig, "
            f"jsonld={jsonld}, jsonscripts={jscripts}, "
            f"dataLayer={'ja' if 'dataLayer' in html else 'nee'}, "
            f"nextdata={'ja' if '__NEXT_DATA__' in html else 'nee'}"
            + (f", api-hints: {apis}" if apis else ""))


def scrape(cfg: RetailerCfg, http: Http, limit: int | None = None) -> ScrapeResult:
    res = ScrapeResult(retailer_id=cfg.id, strategy="firecrawl")
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        res.error = ("FIRECRAWL_API_KEY niet gezet — deze bron blijft ongescrapet. "
                     "Zet de sleutel als GitHub-secret om Firecrawl te activeren "
                     "(betaalde dienst, zie PLAN.md §8).")
        return res

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"})

    if cfg.firecrawl_mode == "pages":
        return _scrape_productpaginas(session, cfg, res, limit)

    cats = _category_urls(cfg, http, res)
    if not cats:
        # De sitemap is bij deze bronnen net zo geblokkeerd als de rest — maar
        # Firecrawl kan hem wél lezen. Dat is de betrouwbaarste bron: de
        # navigatie bleek bij Wibra alleen productteasers te bevatten.
        cats = _sitemap_via_firecrawl(session, cfg, res)
    if not cfg.seeds and len(cats) < 5 and not res.error:
        # Wibra's sitemap kent nauwelijks lijstpagina's (1 landingspagina);
        # de navigatie vult dan aan met de thema-/afdelingspagina's.
        # Expliciete seeds zijn een bewuste keuze en worden nooit aangevuld.
        extra = [c for c in _nav_via_firecrawl(session, cfg, res) if c not in cats]
        cats = cats + extra
    if not cats:
        # een al gezette fout (401/402) is de échte oorzaak — niet overschrijven
        res.error = res.error or (
            "geen categorie-URLs gevonden (sitemap én startpagina) — "
            "voeg `seeds` toe in retailers.yml om Firecrawl te sturen")
        return res
    cats = discover.spread_by_audience(cats, cfg.max_categories)
    res.categories_found = len(cats)
    res.notes.append("gecrawlde categorieën: " + ", ".join(
        urlsplit(u).path for u in cats[:10]))
    seen: dict[str, Product] = {}
    credits = res.requests_done   # navigatie-opvraag telt mee
    uit_kaarten = 0
    uit_json = 0
    missers = 0
    for n, cat_url in enumerate(cats, start=1):
        cat_path = urlsplit(cat_url).path.strip("/").replace("/", " > ")
        html = _firecrawl_html(session, cat_url, res, actions=ACTIES_SCROLL,
                               wait_ms=cfg.firecrawl_wait_ms)
        credits += 1
        if html is None:
            if res.error:      # sleutel ongeldig of credits op: stoppen
                break
            continue
        found = products_from_html(html, cat_url)
        uit_json += len(found)
        if not found:
            # HEMA rendert de lijst wél maar sluit geen JSON in — dan is de
            # kaartweergave zelf de enige bron (zelfde vangnet als de DOM-scan).
            found = cards_from_html(html, cat_url)
            uit_kaarten += len(found)
            if not found and missers < 2:
                # Waaróm leeg? Meet het ter plekke — dat scheelt een aparte
                # diagnoserit van een credit per pagina (les van week 32).
                missers += 1
                res.notes.append(f"miss-signaal {cat_url[:70]}: {_signalen(html)}")
        for p in found:
            # crawlpad (doelgroep) én bron-categorie (producttype) allebei bewaren
            p.category_raw = _voeg_samen(cat_path, p.category_raw)
            seen.setdefault(p.key, p)
        if (limit and len(seen) >= limit) or len(seen) >= cfg.max_products:
            break
        # Kanarie: bij HEMA rendert het productraster niet, en dan leest het
        # kaart-vangnet alleen de promoblokken eromheen (koffie, koekjes). Het
        # eerlijke signaal is dus de JSON-route, niet de kaartoogst.
        if cfg.firecrawl_canary and n >= cfg.firecrawl_canary and not uit_json:
            res.notes.append(
                f"kanarie: {n} categorieën zonder ingebedde productdata — "
                f"gestopt vóór de volle {len(cats)} (bespaart credits; "
                "levert de kanarie wél data, dan loopt de run door)")
            break
    res.requests_done = credits
    if uit_kaarten:
        res.notes.append(f"kaart-vangnet: {uit_kaarten} artikelen uit de "
                         "gerenderde HTML (geen ingebedde JSON)")
    res.notes.append(f"{credits} Firecrawl-credits gebruikt (± {credits} pagina's)")
    res.products = list(seen.values())[: limit or cfg.max_products]
    if not res.products and not res.error:
        res.error = "Firecrawl leverde HTML maar geen producten — extractie nalopen"
    return res


def _category_urls(cfg: RetailerCfg, http: Http, res: ScrapeResult) -> list[str]:
    """Categorieën uit seeds of sitemap. De sitemap zelf kan ook geblokkeerd
    zijn voor het datacenter-IP; dan zijn expliciete `seeds` nodig."""
    if cfg.seeds:
        return list(cfg.seeds)
    cats: list[str] = []
    try:
        for sm in discover.find_sitemaps(http, cfg.base):
            urls = discover.sitemap_urls(http, sm, cfg.url_filter)
            _, sm_cats = discover.split_product_category_urls(urls)
            cats.extend(sm_cats)
            if len(cats) >= cfg.max_categories * 3:
                break
    except Exception:
        pass
    if cats and cfg.focus_categories:
        rx = re.compile(cfg.focus_categories, re.I)
        focused = [u for u in cats if rx.search(u)]
        if focused:
            cats = focused
    return cats


def _focus_smal(cats: list[str], cfg: RetailerCfg) -> list[str]:
    """Versmal tot focus-categorieën, maar alleen als er dan iets overblijft."""
    if cats and cfg.focus_categories:
        rx = re.compile(cfg.focus_categories, re.I)
        focused = [u for u in cats if rx.search(u)]
        if focused:
            return focused
    return cats


def _sitemap_locs_via_firecrawl(session: requests.Session, cfg: RetailerCfg,
                                res: ScrapeResult,
                                voorkeur_subs: str = "categor|collection|listing"
                                ) -> list[str]:
    """Alle sitemap-URLs, opgehaald via Firecrawl (rawHtml — geen rendering
    nodig, dus goedkoop en betrouwbaar). Max ±5 credits."""
    root = discover.origin(cfg.base)
    for pad in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        xml = _firecrawl_html(session, root + pad, res, raw=True)
        res.requests_done += 1
        if not xml or "<loc" not in xml:
            if res.error:
                return []
            continue
        locs = discover.sitemap_locs(xml)
        if re.search(r"<sitemap[\s>]", xml, re.I):
            # index: alleen de meest belovende sub-sitemaps ophalen
            subs = sorted(locs, key=lambda u: 0 if re.search(
                voorkeur_subs, u, re.I) else 1)[:3]
            locs = []
            for sm in subs:
                sub = _firecrawl_html(session, sm, res, raw=True)
                res.requests_done += 1
                if sub:
                    locs.extend(discover.sitemap_locs(sub))
        if cfg.url_filter:
            locs = [u for u in locs if cfg.url_filter in u]
        if locs:
            return list(dict.fromkeys(locs))
    return []


def _sitemap_via_firecrawl(session: requests.Session, cfg: RetailerCfg,
                           res: ScrapeResult) -> list[str]:
    """Categorie-URLs uit de via Firecrawl gelezen sitemap."""
    locs = _sitemap_locs_via_firecrawl(session, cfg, res)
    locs = _zonder_productnamespace(locs)
    _, cats = discover.split_product_category_urls(locs)
    cats = _focus_smal(list(dict.fromkeys(cats)), cfg)
    if cats:
        res.notes.append("categorieën uit de sitemap via Firecrawl")
    return cats


def _scrape_productpaginas(session: requests.Session, cfg: RetailerCfg,
                           res: ScrapeResult, limit: int | None) -> ScrapeResult:
    """firecrawl_mode 'pages': focus-gefilterde productpagina's uit de sitemap,
    stuk voor stuk — voor sites zonder bruikbare lijstpagina's (Wibra: de
    sitemap kent duizenden /assortiment/<artikel>/ maar amper lijstpagina's).
    Kost 1 credit per pagina; de cap begrenst het weekverbruik."""
    locs = _sitemap_locs_via_firecrawl(session, cfg, res,
                                       voorkeur_subs="product|assortiment")
    if not locs:
        res.error = res.error or "geen sitemap bereikbaar voor productpagina's"
        return res
    if cfg.focus_categories:
        rx = re.compile(cfg.focus_categories, re.I)
        urls = [u for u in locs if rx.search(urlsplit(u).path)]
    else:
        urls = list(locs)
    if not urls:
        res.error = "geen productpagina's binnen focus in de sitemap"
        return res
    # vaste (gesorteerde) steekproef: week-op-week vergelijkbaar, zoals bij Zeeman
    urls.sort()
    cap = min(limit or cfg.firecrawl_page_cap, cfg.firecrawl_page_cap)
    res.notes.append(f"{len(urls)} sitemap-URLs binnen focus; vaste steekproef "
                     f"van {min(cap, len(urls))} productpagina's (1 credit per stuk)")

    credits = res.requests_done
    gemist = herhaald = 0
    gezien: dict[str, str] = {}
    for n, url in enumerate(urls[:cap], start=1):
        # Kanarie: Wibra gaf in week 32 op alle 38 productpagina's niets prijs.
        # De bron blijft wekelijks meelopen, maar zodra de eerste handvol
        # pagina's opnieuw leeg is heeft doorgaan geen zin — dat scheelt
        # credits die anders binnen een maand op zijn.
        if (cfg.firecrawl_canary and n > cfg.firecrawl_canary
                and not res.products):
            res.notes.append(
                f"kanarie: eerste {cfg.firecrawl_canary} productpagina's zonder "
                f"leesbare data — gestopt vóór de volle {min(cap, len(urls))} "
                "(bespaart credits; levert de kanarie wél data, dan loopt de "
                "run door tot de cap)")
            break
        html = _firecrawl_html(session, url, res, wait_ms=cfg.firecrawl_wait_ms)
        credits += 1
        if html is None:
            if res.error:
                break
            continue
        p = _eigen_product(products_from_html(html, url), url) \
            or product_from_meta(html, url)
        if p is None:
            gemist += 1
            if gemist <= 2:
                # Waaróm onleesbaar? Meet het ter plekke, mét de URL — zo is
                # het pad naar een echte productpagina meteen bekend voor een
                # gerichte vervolg-diagnose.
                res.notes.append(f"miss-signaal {url[:80]}: {_signalen(html)}")
            continue
        if p.key in gezien:     # gedeeld blok i.p.v. eigen artikel (Zeeman-les)
            herhaald += 1
            continue
        gezien[p.key] = p.title
        # Bij Wibra draagt de artikelslug zelf de categorie ('baby-pyjama-…');
        # het volledige pad dus meenemen, niet alleen de mapstructuur erboven.
        segs = [s for s in urlsplit(url).path.split("/") if s]
        p.category_raw = _voeg_samen(
            p.category_raw, " ".join(s.replace("-", " ") for s in segs))
        if not p.url:
            p.url = url
        res.products.append(p)
        if limit and len(res.products) >= limit:
            break
    res.requests_done = credits
    if gemist:
        res.notes.append(f"{gemist} productpagina's zonder leesbare productdata")
    if herhaald:
        res.notes.append(f"{herhaald} pagina's leverden een al gezien artikel")
    res.notes.append(f"{credits} Firecrawl-credits gebruikt (± {credits} pagina's)")
    if not res.products and not res.error:
        res.error = "Firecrawl leverde HTML maar geen producten — extractie nalopen"
    return res


def _zonder_productnamespace(locs: list[str]) -> list[str]:
    """Padsegmenten waar vrijwel álle sitemap-URLs onder hangen zijn het
    productnamespace (Wibra: duizenden /assortiment/<artikel>/). Die URLs
    zien er voor de padheuristiek uit als categorie ('baby-pyjama-…') maar
    zijn productpagina's; de échte lijstpagina's staan in de rest."""
    from collections import Counter

    def eerste_seg(u: str) -> str:
        segs = [s for s in urlsplit(u).path.split("/") if s]
        return segs[0].lower() if segs else ""

    telling = Counter(eerste_seg(u) for u in locs)
    totaal = len(locs) or 1
    massa = {s for s, n in telling.items() if n > 100 and n / totaal > 0.5}
    return [u for u in locs if eerste_seg(u) not in massa] if massa else locs


def _nav_via_firecrawl(session: requests.Session, cfg: RetailerCfg,
                       res: ScrapeResult) -> list[str]:
    """Categorieën uit de door Firecrawl gerenderde startpagina (1 credit)."""
    html = _firecrawl_html(session, cfg.base, res)
    res.requests_done += 1
    if not html:
        return []
    cats = discover.categories_from_html(html, cfg.base, cfg.url_filter,
                                         cfg.max_categories)
    # Een 'navigatielink' mét prijs in de kaart eromheen is een productteaser,
    # geen categorie — bij Wibra wonnen pyjama-teasers het zo van de echte
    # afdelingen (de prijs staat er búiten het anker, dus kijk naar de kaart).
    met_prijs = set()
    for a in lees_ankers(html):
        if a["href"] and "€" in a["kaart"]:
            p = urlsplit(urljoin(cfg.base, a["href"]))
            met_prijs.add(f"{p.scheme}://{p.netloc}{p.path}")
    cats = [c for c in cats if c not in met_prijs]
    if cfg.focus_categories and cats:
        # focus vooraan sorteren maar niets wegfilteren: bij Wibra droeg geen
        # enkele echte afdeling een focuswoord, en een lege lijst is erger
        # dan een paar credits aan bredere categorieën
        rx = re.compile(cfg.focus_categories, re.I)
        cats.sort(key=lambda u: 0 if rx.search(u) else 1)
    if cats:
        res.notes.append("categorieën via de Firecrawl-gerenderde startpagina "
                         "(sitemap onbereikbaar voor het datacenter-IP)")
    return cats


def _firecrawl_html(session: requests.Session, url: str, res: ScrapeResult,
                    raw: bool = False, actions: list | None = None,
                    wait_ms: int = 0) -> str | None:
    """raw=True haalt de onbewerkte bron op (sitemap-XML) zonder rendering;
    actions (scrollen/wachten) laten lui ladende rasters eerst renderen;
    wait_ms > 0 vervangt de standaard-rendertijd van 5000 ms."""
    payload = {
        "url": url,
        "formats": ["rawHtml"] if raw else ["html"],
        "onlyMainContent": False,
        # HEMA's raster rendert traag; bij 2500 ms was de lijst nog leeg
        "waitFor": 0 if raw else (wait_ms or 5000),
        "timeout": 30000 if not actions else 45000,
        "location": {"country": "NL", "languages": ["nl-NL"]},
    }
    if actions:
        payload["actions"] = actions
    for poging in range(len(WACHT_BIJ_429) + 1):
        wacht = PAUZE_TUSSEN_CALLS - (time.monotonic() - _laatste_call[0])
        if wacht > 0:
            time.sleep(wacht)
        try:
            r = session.post(FIRECRAWL_ENDPOINT, json=payload, timeout=60)
        except requests.RequestException as e:
            _laatste_call[0] = time.monotonic()
            res.notes.append(f"Firecrawl-netwerkfout: {str(e)[:120]}")
            return None
        _laatste_call[0] = time.monotonic()
        if r.status_code != 429:
            break
        if poging < len(WACHT_BIJ_429):
            time.sleep(WACHT_BIJ_429[poging])
    if r.status_code == 429:
        res.notes.append(f"Firecrawl-limiet (HTTP 429) hield aan op {url[:60]}")
        return None
    if r.status_code == 400 and actions:
        # acties niet beschikbaar op dit plan of afgekeurd: zonder proberen,
        # dan komt er in elk geval een snapshot (zonder scroll) terug
        if "acties niet geaccepteerd — zonder acties verder" not in res.notes:
            res.notes.append("acties niet geaccepteerd — zonder acties verder")
        return _firecrawl_html(session, url, res, raw=raw, actions=None,
                               wait_ms=wait_ms)
    if r.status_code == 402:
        res.error = "Firecrawl-credits op (HTTP 402) — tegoed bijvullen of tier verhogen"
        return None
    if r.status_code == 401:
        res.error = "Firecrawl-sleutel ongeldig (HTTP 401)"
        return None
    if r.status_code >= 400:
        res.notes.append(f"Firecrawl HTTP {r.status_code} op {url[:60]}")
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    d = data.get("data") or {}
    return d.get("rawHtml") or d.get("html")
