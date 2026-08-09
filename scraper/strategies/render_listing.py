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
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

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
    "#CybotCookiebotDialogBodyButtonAcceptAll",
    "#usercentrics-root >>> button[data-testid='uc-accept-all-button']",
    "button[data-testid='uc-accept-all-button']",
    "button[id*='accept-all' i]",
    "button[class*='accept-all' i]",
    "[data-cy='cookie-accept-all']",
    "[data-test-id='cookie-accept-all']",
)
# 'alles toestaan' is de Nederlandse Cookiebot-standaard (Zeeman) — zonder die
# tekst bleef de muur daar staan en laadde het Algolia-productraster nooit
CONSENT_TEXTS = ("alles toestaan", "sta alle cookies toe", "alles accepteren",
                 "accepteer alles", "alle cookies accepteren",
                 "cookies accepteren", "accepteren", "akkoord", "ik ga akkoord",
                 "accept all", "allow all")

# Beide schrijfwijzen: '€ 24,99' én '24,99 €' — C&A zet het teken achter het
# getal, waardoor een €-eerst-regex maar een fractie van de kaarten las.
PRICE_TEXT_RE = re.compile(r"€\s*(\d+(?:[.,]\d{2})?|\d+[.,]-)"
                           r"|(\d+(?:[.,]\d{2})?)\s*€")
# Sommige shops zetten het €-teken via CSS (::before) neer; dan staat er in de
# tekst alleen '3,99'. Bewust smal: twee decimalen achter een komma/punt, geen
# maten ('35 - 46'), geen losse getallen en geen versienummers ('5.51.0' —
# de diagnose telde die op Zeeman als prijs). Alleen gebruikt als de pagina
# nergens een €-teken toont — anders is het te grof.
PRICE_LOOSE_RE = re.compile(r"(?<![\d.,])(\d{1,3}[.,]\d{2})(?![.,]?\d)")


def _prijzen(text: str, prijs_los: bool = False) -> list[float]:
    if prijs_los:
        ruw = PRICE_LOOSE_RE.findall(text)
    else:
        ruw = [m.group(1) or m.group(2) for m in PRICE_TEXT_RE.finditer(text)]
    return [p for p in (parse_price(r) for r in ruw) if p]
# prijsdelen uit de kaarttekst knippen om de titel over te houden — titel en
# prijs staan lang niet altijd op een eigen regel
PRICE_STRIP_RE = re.compile(r"€\s*\d+(?:[.,]\d{2})?|\d+(?:[.,]\d{2})?\s*€|"
                            r"\b(?:van|nu|nu voor|vanaf|adviesprijs)\b", re.I)
BLOCK_HINTS = re.compile(r"access denied|just a moment|are you human|captcha|"
                         r"request blocked|pardon our interruption", re.I)

# Navigatietegels dragen vaak óók een prijs ("vanaf € 9,00") en komen in het
# losse DOM-vangnet als artikel binnen. Bij C&A stonden zo 'shoppen', 'Voor
# meisjes' en 'Voor jongens' in de weekcijfers.
NAV_TITEL_RE = re.compile(
    r"^(?:shop(?:pen)?|bekijk(?:\s+alles)?|alles?\s+bekijken|meer\s+\w+|"
    r"voor\s+(?:haar|hem|meisjes|jongens|kinderen|baby'?s?|dames|heren)|"
    r"alle\s+\w+|sale|nieuw|ontdek(?:ken)?|lees\s+meer|verder\s+winkelen)$", re.I)

DOM_SCAN_JS = """
([streng, prijsLos]) => {
  const out = [];
  const seen = new Set();
  // '€ 24,99' én '24,99 €' (C&A); losse ronde weert versienummers als 5.51.0
  const priceRe = prijsLos ? /(?:^|[^\\d.,])\\d{1,3}[.,]\\d{2}(?![.,]?\\d)/
                           : /€\\s*\\d|\\d[\\d.,]*\\s*€/;
  // Productkaart = een link naar een productpagina, met ergens in de
  // omliggende kaart een prijs. Titel komt uit aria-label / img-alt /
  // heading, niet uit de ruwe kaarttekst (die is vervuild met prijs/labels).
  // In de strenge ronde moet de link ook echt naar een product wijzen:
  // zonder die eis werden bij Action banners ('Veiligheidswaarschuwing…')
  // en bij C&A navigatietegels ('Voor meisjes') als artikel opgevoerd.
  const padRe = /\\/p\\/|\\/p-|\\/product|\\/artikel|\\/dp\\//i;
  const links = document.querySelectorAll('a[href]');
  for (const a of links) {
    const href = a.href;
    if (!href || href.startsWith('javascript:') || seen.has(href)) continue;
    if (streng) {
      const laatste = (href.split(/[?#]/)[0].replace(/\\/$/, '').split('/').pop() || '');
      if (!padRe.test(href) && !/\\d{4,}/.test(laatste)) continue;
    }
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
            diagnoses = 0
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
                        found = _dom_products(page, res)
                    new = _absorb(seen, found, cat_path)
                    if not new:
                        # Meerdere diagnoses: één pagina zegt te weinig. Bij Zeeman
                        # bleek de eerste categorie een redactionele pagina te zijn
                        # (0 €-tekens) — dat zei niets over de échte lijstpagina's.
                        if not seen and diagnoses < 3:
                            res.notes.append(f"diagnose {cat_path[:60]}: {_diagnose(page)}")
                            diagnoses += 1
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
    geklikt = not consent
    if consent:
        try:
            geklikt = accept_consent(page)
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
    except Exception:
        return None
    if not geklikt:
        # Cookiemuren (Cookiebot e.d.) laden asynchroon en staan er vaak pas ná
        # de eerste klikpoging — bij Zeeman bleef de muur zo onopgemerkt staan
        # en laadde het productraster nooit. Na een late klik even wachten
        # zodat het raster (en zijn API-calls) alsnog kan opkomen.
        try:
            if accept_consent(page):
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                page.wait_for_timeout(800)
        except Exception:
            pass
    try:
        html = page.content()
    except Exception:
        return None
    head = html[:4000]
    if BLOCK_HINTS.search(head) and "product" not in head.lower():
        return None
    return html


class _AnkerLezer(HTMLParser):
    """Verzamelt per <a>: href, aria-label/title, img-alt en de tekst erbinnen.
    De statische tegenhanger van de DOM-scan, voor HTML die al elders gerenderd
    is (Firecrawl) en waar dus geen browser meer omheen staat."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ankers: list[dict] = []
        self._open: dict | None = None
        self._diepte = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a":
            if self._open is not None:
                self._diepte += 1
                return
            self._open = {"href": a.get("href") or "", "tekst": [],
                          "label": a.get("aria-label") or a.get("title") or ""}
            self._diepte = 1
        elif self._open is not None:
            if tag == "img" and not self._open["label"]:
                self._open["label"] = a.get("alt") or ""
            if a.get("aria-label") and not self._open["label"]:
                self._open["label"] = a["aria-label"]

    def handle_endtag(self, tag):
        if tag != "a" or self._open is None:
            return
        self._diepte -= 1
        if self._diepte <= 0:
            self._open["tekst"] = re.sub(r"\s+", " ", " ".join(self._open["tekst"])).strip()
            self.ankers.append(self._open)
            self._open = None

    def handle_data(self, data):
        if self._open is not None and data.strip():
            self._open["tekst"].append(data.strip())


def lees_ankers(html: str) -> list[dict]:
    lezer = _AnkerLezer()
    try:
        lezer.feed(html)
    except Exception:
        pass  # kapotte HTML: houden wat er tot dan toe gelezen is
    return lezer.ankers


def cards_from_html(html: str, base_url: str) -> list[Product]:
    """Productkaarten uit reeds gerenderde HTML — zelfde vangnet als de
    DOM-scan, maar zonder browser. Nodig voor Firecrawl-bronnen (HEMA) die
    hun lijsten wél renderen maar geen JSON-LD of __NEXT_DATA__ insluiten."""
    ankers = lees_ankers(html)
    host = urlsplit(base_url).netloc
    heeft_euro = "€" in html or "&euro;" in html
    for prijs_los in (False, True):
        if prijs_los and heeft_euro:
            break   # losse getallen alleen als er nérgens een €-teken staat
        producten: dict[str, Product] = {}
        for a in ankers:
            href = a["href"]
            if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
                continue
            vol = urljoin(base_url, href)
            p_url = urlsplit(vol)
            if p_url.netloc != host or discover.NOISE_WORDS.search(vol):
                continue
            prijzen = [p for p in _prijzen(a["tekst"], prijs_los=prijs_los) if p <= 200]
            if not prijzen:
                continue
            titel = _clean_title(a["label"], a["tekst"])
            if not titel or NAV_TITEL_RE.match(titel):
                continue
            key = url_key(vol)
            if key not in producten:
                producten[key] = Product(
                    key=key, title=titel, url=vol, price=min(prijzen),
                    was_price=max(prijzen) if max(prijzen) > min(prijzen) else None)
        if producten:
            return list(producten.values())
    return []


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
            # Action plakt de maatvermelding en varianten aan de titel vast:
            # "CompressiesokkenMaten 35 - 46 | 2 paar | diverse kleuren".
            # Alles vanaf de eerste scheiding of maatvermelding valt weg.
            kandidaat = kandidaat.split("|")[0]
            # alleen een vastgeplakte maatvermelding ("...sokkenMaten 35 - 46");
            # een losse "Maat 40" met spatie ervoor hoort wél bij de naam
            kandidaat = re.sub(r"(?<=[a-z])Ma(?:at|ten)\b.*", "", kandidaat)
            kandidaat = re.sub(r"\s{2,}", " ", kandidaat).strip(" -–|,.\t")
            # een echte titel bevat een letter en is geen los getal/label
            if len(kandidaat) >= 3 and re.search(r"[a-zA-Z]", kandidaat):
                return kandidaat[:200]
    return ""


def _dom_products(page, res: ScrapeResult | None = None) -> list[Product]:
    """Vangnet: productkaarten uit de gerenderde DOM (link + prijs + titel).

    Vier rondes, van meest naar minst betrouwbaar; de eerste die iets oplevert
    wint, en elke afwijking van de strengste ronde komt in het rapport.
      1. productlink + €-prijs      — het normale geval
      2. alle links + €-prijs       — C&A: productlinks zijn niet herkenbaar
      3. productlink + los getal    — €-teken komt uit CSS i.p.v. uit de tekst
      4. alle links + los getal     — laatste redmiddel
    Rondes 3 en 4 draaien alleen als er nérgens een €-teken staat; anders is
    'ieder getal met twee decimalen' te grof en vist het maten en gewichten op.
    """
    for streng in (True, False):
        gevonden = _dom_ronde(page, streng=streng, prijs_los=False)
        if gevonden:
            _meld(res, streng, False, len(gevonden))
            return gevonden
    if _pagina_toont_euro(page):
        return []
    for streng in (True, False):
        gevonden = _dom_ronde(page, streng=streng, prijs_los=True)
        if gevonden:
            _meld(res, streng, True, len(gevonden))
            return gevonden
    return []


def _pagina_toont_euro(page) -> bool:
    try:
        return bool(page.evaluate(
            "() => (document.body.innerText || '').includes('\\u20ac')"))
    except Exception:
        return True   # bij twijfel niet de losse prijsronde inzetten


def _meld(res: ScrapeResult | None, streng: bool, prijs_los: bool, aantal: int) -> None:
    if res is None or (streng and not prijs_los):
        return          # de normale route hoeft niet gemeld te worden
    waarom = []
    if not streng:
        waarom.append("geen herkenbare productlinks")
    if prijs_los:
        waarom.append("geen €-teken in de tekst")
    boodschap = f"DOM-vangnet: {' en '.join(waarom)} — {aantal} kaarten gelezen"
    if not any(n.startswith("DOM-vangnet") for n in res.notes):
        res.notes.append(boodschap)


def _dom_ronde(page, streng: bool, prijs_los: bool = False) -> list[Product]:
    try:
        raw = page.evaluate(DOM_SCAN_JS, [streng, prijs_los])
    except Exception:
        return []
    products: list[Product] = []
    for item in raw:
        href = item.get("href", "")
        text = item.get("text", "")
        prices = _prijzen(text, prijs_los)
        # ondergoed/nachtmode/sokken: prijzen boven €200 zijn vrijwel zeker ruis
        # (artikelnummers, postcodes) uit een verkeerd kaart-element
        prices = [p for p in prices if p <= 200]
        if not prices:
            continue
        price, was = min(prices), None
        if len(prices) > 1 and max(prices) > min(prices):
            was = max(prices)
        title = _clean_title(item.get("title", ""), text)
        if not title or NAV_TITEL_RE.match(title):
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
