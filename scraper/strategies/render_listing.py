"""Fase-2-strategie: headless browser (Playwright/Chromium) voor bronnen die
hun pagina's client-side renderen of eenvoudige botfilters hanteren.

Zwaarder en trager dan de HTTP-strategieën (±3-5 s per pagina), daarom alleen
expliciet via `strategy: render` en met eigen, krappere caps in retailers.yml.
Per categoriepagina worden drie bronnen van productdata gecombineerd, van
schoon naar rommelig:
  1. onderschepte JSON-API-calls die de webshop zélf maakt (Algolia, eigen
     product-/zoek-API) — de schoonste route, vangt data die nooit in de HTML komt;
  2. ingebedde JSON in de gerenderde HTML (JSON-LD / __NEXT_DATA__);
  3. een generieke DOM-kaartjes-extractie (links met een €-prijs) als vangnet.
Plus lichte anti-detectie (webdriver-vlag verbergen, echte headers) zodat
client-side renderers en eenvoudige botfilters passeerbaar worden.

Eerlijke verwachting: JavaScript-renderers en API-gedreven shops lost dit op;
zware challenge-muren (bv. Akamai/DataDome) die de browser al bij het laden
tegenhouden, mogelijk niet — dat blijkt uit de Validatie bronnen-run en blijft
dan zichtbaar in de gezondheidstabel.
"""
from __future__ import annotations

import re
import time
from urllib.parse import urlsplit

from .. import discover
from ..config import RetailerCfg
from ..http import Http
from ..jsonscan import deep_find_products, products_from_html, url_key
from ..models import Product, ScrapeResult
from ..normalize import parse_price

# API-endpoints die productlijsten teruggeven, herkenbaar aan de URL.
API_URL_RE = re.compile(r"product|search|catalog|listing|/plp|/api/|graphql|"
                        r"algolia|findify|bloomreach|/browse|/category", re.I)

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['nl-NL', 'nl', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
"""

# Nederlandse webshops zetten vrijwel altijd een cookiemuur vóór de inhoud;
# zolang die er staat, rendert de productlijst niet. Eerst de bekende
# knop-id's (OneTrust, Cookiebot, Usercentrics), dan op knoptekst.
CONSENT_SELECTORS = (
    "#onetrust-accept-btn-handler",
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
    "#CybotCookiebotDialogBodyButtonAccept",
    "#usercentrics-root >>> button[data-testid='uc-accept-all-button']",
    "button[data-testid='uc-accept-all-button']",
    "button[id*='accept-all' i]",
    "button[class*='accept-all' i]",
    "[data-cy='cookie-accept-all']",
    "[data-test-id='cookie-accept-all']",
)
CONSENT_TEXTS = ("alles accepteren", "accepteer alles", "alle cookies accepteren",
                 "cookies accepteren", "accepteren", "akkoord", "ik ga akkoord",
                 "accept all", "allow all")

PRICE_TEXT_RE = re.compile(r"€\s*(\d+(?:[.,]\d{2})?|\d+[.,]-)")
# prijsdelen uit de kaarttekst knippen om de titel over te houden — titel en
# prijs staan lang niet altijd op een eigen regel
PRICE_STRIP_RE = re.compile(r"€\s*\d+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?\s*€|"
                            r"\b(?:van|nu|nu voor|vanaf|adviesprijs)\b", re.I)
BLOCK_HINTS = re.compile(r"access denied|just a moment|are you human|captcha|"
                         r"request blocked|pardon our interruption", re.I)

DOM_SCAN_JS = """
() => {
  const out = [];
  const seen = new Set();
  const priceRe = /€\\s*\\d/;
  // Productkaart = een link naar een productpagina, met ergens in de
  // omliggende kaart een prijs. Titel komt uit aria-label / img-alt /
  // heading, niet uit de ruwe kaarttekst (die is vervuild met prijs/labels).
  const links = document.querySelectorAll(
    'a[href*="/p/"],a[href*="/p-"],a[href*="/product"],a[href*="/artikel"],a[href]');
  for (const a of links) {
    const href = a.href;
    if (!href || href.startsWith('javascript:') || seen.has(href)) continue;
    let card = a, hops = 0;
    while (card && hops < 5 && !priceRe.test(card.innerText || '')) {
      card = card.parentElement; hops++;
    }
    if (!card || !priceRe.test(card.innerText || '')) continue;
    let title = (a.getAttribute('aria-label') || '').trim();
    if (!title) {
      const img = a.querySelector('img[alt]') || card.querySelector('img[alt]');
      if (img) title = (img.getAttribute('alt') || '').trim();
    }
    if (!title) title = (a.textContent || '').trim();
    if (!title) {
      const h = card.querySelector('h1,h2,h3,h4,[class*="title" i],[class*="name" i]');
      if (h) title = (h.textContent || '').trim();
    }
    seen.add(href);
    out.push({ href, title: title.slice(0, 200), text: (card.innerText || '').slice(0, 400) });
    if (out.length >= 250) break;
  }
  return out;
}
"""


class _ApiSink:
    """Vangt productdata op uit JSON-responses die de pagina zelf ophaalt."""

    def __init__(self):
        self._buf: list[Product] = []

    def reset(self):
        self._buf = []

    @property
    def products(self) -> list[Product]:
        return self._buf

    def handle(self, response):
        try:
            url = response.url
            if not API_URL_RE.search(url):
                return
            ctype = (response.headers or {}).get("content-type", "")
            if "json" not in ctype.lower():
                return
            data = response.json()
        except Exception:
            return
        try:
            self._buf.extend(deep_find_products(data, url))
        except Exception:
            pass


def scrape(cfg: RetailerCfg, http: Http, limit: int | None = None) -> ScrapeResult:
    res = ScrapeResult(retailer_id=cfg.id, strategy="render")
    try:
        from playwright.sync_api import Error as PwError
        from playwright.sync_api import sync_playwright
    except ImportError:
        res.error = ("playwright niet geïnstalleerd — zie de workflowstap "
                     "'Headless browser voor render-bronnen'")
        return res

    cats = _category_urls_via_http(cfg, http, res)
    seen: dict[str, Product] = {}
    pause = max(cfg.min_delay, 1.0)
    api_hits = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=["--disable-blink-features=AutomationControlled",
                  "--disable-features=IsolateOrigins,site-per-process"])
        context = browser.new_context(
            locale="nl-NL",
            timezone_id="Europe/Amsterdam",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"))
        context.add_init_script(STEALTH_JS)
        sink = _ApiSink()
        page = context.new_page()
        page.on("response", sink.handle)
        try:
            if not cats:
                cats = _nav_categories_via_browser(page, cfg)
                if cats:
                    res.notes.append("categorieën via gerenderde navigatie")
            cats = discover.spread_by_audience(cats, cfg.max_categories)
            res.categories_found = len(cats)
            if not cats:
                res.error = "geen categorie-URLs gevonden (ook niet via de browser)"
                return res
            # Welke categorieën gecrawld worden bepaalt of de doelgroep herkenbaar
            # is; zichtbaar maken scheelt gokwerk bij het instellen van `seeds`.
            # (Zo kwam bij Primark aan het licht dat 'vrouwen'/'mannen' ontbraken.)
            res.notes.append("gecrawlde categorieën: " + ", ".join(
                urlsplit(u).path for u in cats[:10]))

            blocked_pages = 0
            diagnose_gedaan = False
            for cat_url in cats:
                cat_path = urlsplit(cat_url).path.strip("/").replace("/", " > ")
                for n in range(1, cfg.max_pages_per_category + 1):
                    url = cat_url if n == 1 else \
                        f"{cat_url}{'&' if '?' in cat_url else '?'}page={n}"
                    sink.reset()
                    html = _load(page, url)
                    time.sleep(pause)
                    if html is None:
                        blocked_pages += 1
                        break
                    # 1) onderschepte API-JSON, 2) ingebedde JSON, 3) DOM-vangnet
                    from_api = list(sink.products)
                    api_hits += len(from_api)
                    found = from_api + products_from_html(html, url)
                    if not found:
                        found = _dom_products(page)
                    new = _absorb(seen, found, cat_path)
                    if not new:
                        if not diagnose_gedaan and not seen:
                            res.notes.append(f"diagnose {cat_path[:40]}: {_diagnose(page)}")
                            diagnose_gedaan = True
                        break
                    if (limit and len(seen) >= limit) or len(seen) >= cfg.max_products:
                        break
                if (limit and len(seen) >= limit) or len(seen) >= cfg.max_products:
                    break
            if blocked_pages:
                res.notes.append(f"{blocked_pages} pagina('s) geblokkeerd of niet geladen")
            if api_hits:
                res.notes.append(f"{api_hits} artikelen uit onderschepte API-calls")
        except PwError as e:
            res.error = f"browserfout: {str(e)[:200]}"
        finally:
            browser.close()

    res.products = list(seen.values())[: limit or cfg.max_products]
    if not res.products and not res.error:
        res.error = ("browser laadde pagina's maar vond geen producten — "
                     "vermoedelijk hardere botdetectie (challenge) of afwijkende opbouw")
    return res


def _category_urls_via_http(cfg: RetailerCfg, http: Http, res: ScrapeResult) -> list[str]:
    """Goedkope route eerst: categorieën uit de sitemap (kan bij deze bronnen
    ook geblokkeerd zijn — dan valt de browser-navigatie in)."""
    cats = list(cfg.seeds)
    if cats:
        return cats
    try:
        for sm in discover.find_sitemaps(http, cfg.base):
            urls = discover.sitemap_urls(http, sm, cfg.url_filter)
            _, sm_cats = discover.split_product_category_urls(urls)
            cats.extend(sm_cats)
            if len(cats) >= cfg.max_categories * 3:
                break
    except Exception:
        return []
    if cats and cfg.focus_categories:
        rx = re.compile(cfg.focus_categories, re.I)
        focused = [u for u in cats if rx.search(u)]
        if focused:
            res.notes.append(f"focus: {len(focused)} van {len(cats)} categorieën")
            cats = focused
    return cats


def _nav_categories_via_browser(page, cfg: RetailerCfg) -> list[str]:
    if _load(page, cfg.base) is None:
        return []
    try:
        hrefs = page.evaluate(
            "() => [...document.querySelectorAll('a[href]')].map(a => a.href)")
    except Exception:
        return []
    host = urlsplit(cfg.base).netloc
    rx_focus = re.compile(cfg.focus_categories, re.I) if cfg.focus_categories else None
    seen: dict[str, None] = {}
    for href in hrefs:
        p = urlsplit(href)
        if p.netloc != host or discover.NOISE_WORDS.search(href):
            continue
        if cfg.url_filter and cfg.url_filter not in href:
            continue
        path = p.path
        segs = [s for s in path.split("/") if s]
        if not (1 <= len(segs) <= 4):
            continue
        relevant = (rx_focus and rx_focus.search(path)) or \
            discover.CATEGORY_WORDS.search(path)
        if relevant:
            seen.setdefault(f"{p.scheme}://{p.netloc}{path}", None)
    ranked = sorted(seen, key=lambda u: (0 if (rx_focus and rx_focus.search(u)) else 1,
                                         urlsplit(u).path.count("/"), len(u)))
    return ranked


def accept_consent(page) -> bool:
    """Cookiemuur wegklikken (ook in een iframe). True als er geklikt is."""
    for sel in CONSENT_SELECTORS:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=700):
                el.click(timeout=2500)
                page.wait_for_timeout(900)
                return True
        except Exception:
            continue
    for frame in page.frames:
        for txt in CONSENT_TEXTS:
            try:
                btn = frame.get_by_role("button", name=re.compile(txt, re.I)).first
                if btn.is_visible(timeout=500):
                    btn.click(timeout=2500)
                    page.wait_for_timeout(900)
                    return True
            except Exception:
                continue
    return False


def _load(page, url: str, consent: bool = True) -> str | None:
    """Pagina laden, cookiemuur wegklikken en laten renderen.
    None bij fout of blokkadepagina."""
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        return None
    if resp is not None and resp.status in (403, 429, 503):
        return None
    if consent:
        try:
            accept_consent(page)
        except Exception:
            pass
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass  # druk-bezette pagina's worden nooit 'idle' — inhoud is er vaak al
    try:
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight / 2)")
        page.wait_for_timeout(700)
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(900)
        html = page.content()
    except Exception:
        return None
    head = html[:4000]
    if BLOCK_HINTS.search(head) and "product" not in head.lower():
        return None
    return html


def _diagnose(page) -> str:
    """Korte diagnose als een pagina wél laadt maar niets oplevert — zodat het
    validatierapport vertelt wat er ís in plaats van alleen wat ontbreekt."""
    try:
        info = page.evaluate("""() => ({
          titel: (document.title || '').slice(0, 60),
          links: document.querySelectorAll('a[href]').length,
          prijzen: (document.body.innerText.match(/€/g) || []).length,
          tekst: (document.body.innerText || '').trim().length,
        })""")
        return (f"titel='{info['titel']}', {info['links']} links, "
                f"{info['prijzen']} €-tekens, {info['tekst']} tekens tekst")
    except Exception:
        return "pagina niet leesbaar"


def _clean_title(raw_title: str, card_text: str) -> str:
    """Titel opschonen; valt terug op de kaarttekst als er geen echte titel is."""
    for bron in (raw_title, card_text):
        for line in (bron or "").splitlines():
            kandidaat = PRICE_STRIP_RE.sub(" ", line)
            kandidaat = re.sub(r"\(\s*/?\s*stuk\s*\)|/\s*stuk|per stuk", " ", kandidaat, flags=re.I)
            kandidaat = re.sub(r"\s{2,}", " ", kandidaat).strip(" -–|,.\t")
            # een echte titel bevat een letter en is geen los getal/label
            if len(kandidaat) >= 3 and re.search(r"[a-zA-Z]", kandidaat):
                return kandidaat[:200]
    return ""


def _dom_products(page) -> list[Product]:
    """Vangnet: productkaarten uit de gerenderde DOM (link + prijs + titel)."""
    try:
        raw = page.evaluate(DOM_SCAN_JS)
    except Exception:
        return []
    products: list[Product] = []
    for item in raw:
        href = item.get("href", "")
        text = item.get("text", "")
        prices = [p for p in (parse_price(m) for m in PRICE_TEXT_RE.findall(text)) if p]
        # ondergoed/nachtmode/sokken: prijzen boven €200 zijn vrijwel zeker ruis
        # (artikelnummers, postcodes) uit een verkeerd kaart-element
        prices = [p for p in prices if p <= 200]
        if not prices:
            continue
        price, was = min(prices), None
        if len(prices) > 1 and max(prices) > min(prices):
            was = max(prices)
        title = _clean_title(item.get("title", ""), text)
        if not title:
            continue
        products.append(Product(key=url_key(href), title=title, url=href,
                                price=price, was_price=was))
    return products


def _absorb(seen: dict[str, Product], found: list[Product], cat_path: str) -> int:
    from .listing_crawl import _voeg_samen
    new = 0
    for p in found:
        # crawlpad (doelgroep) én bron-categorie (producttype) allebei bewaren
        p.category_raw = _voeg_samen(cat_path, p.category_raw)
        cur = seen.get(p.key)
        if cur is None:
            seen[p.key] = p
            new += 1
            continue
        for field in ("color", "sizes", "brand", "category_raw", "url"):
            if not getattr(cur, field) and getattr(p, field):
                setattr(cur, field, getattr(p, field))
        if cur.price is None and p.price is not None:
            cur.price = p.price
    return new
