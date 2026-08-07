"""Fase-2-strategie: headless browser (Playwright/Chromium) voor bronnen die
hun pagina's client-side renderen of eenvoudige botfilters hanteren.

Zwaarder en trager dan de HTTP-strategieën (±3-5 s per pagina), daarom alleen
expliciet via `strategy: render` en met eigen, krappere caps in retailers.yml.
Werkwijze per categorie: pagina laden, laten renderen, en dan dezelfde
JSON-extractie als altijd op de gerenderde HTML — met een generieke
DOM-kaartjes-extractie (links met een €-prijs) als vangnet.

Eerlijke verwachting: JavaScript-renderers (bv. C&A, KiK) lost dit op;
zware botmuren met challenges (bv. Akamai) mogelijk niet — dat blijkt uit
de Validatie bronnen-run en blijft dan zichtbaar in de gezondheidstabel.
"""
from __future__ import annotations

import re
import time
from urllib.parse import urlsplit

from .. import discover
from ..config import RetailerCfg
from ..http import Http
from ..jsonscan import products_from_html, url_key
from ..models import Product, ScrapeResult
from ..normalize import parse_price

PRICE_TEXT_RE = re.compile(r"€\s*(\d+(?:[.,]\d{2})?|\d+[.,]-)")
BLOCK_HINTS = re.compile(r"access denied|just a moment|are you human|captcha|"
                         r"request blocked|pardon our interruption", re.I)

DOM_SCAN_JS = """
() => {
  const out = [];
  const seen = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    const t = (a.innerText || '').trim();
    if (!t || !/€\\s*\\d/.test(t)) continue;
    const href = a.href;
    if (!href || href.startsWith('javascript:') || seen.has(href)) continue;
    seen.add(href);
    out.push({ href, text: t.slice(0, 300) });
    if (out.length >= 200) break;
  }
  return out;
}
"""


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

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            locale="nl-NL",
            viewport={"width": 1366, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"))
        page = context.new_page()
        try:
            if not cats:
                cats = _nav_categories_via_browser(page, cfg)
                if cats:
                    res.notes.append("categorieën via gerenderde navigatie")
            cats = cats[: cfg.max_categories]
            res.categories_found = len(cats)
            if not cats:
                res.error = "geen categorie-URLs gevonden (ook niet via de browser)"
                return res

            blocked_pages = 0
            for cat_url in cats:
                cat_path = urlsplit(cat_url).path.strip("/").replace("/", " > ")
                for n in range(1, cfg.max_pages_per_category + 1):
                    url = cat_url if n == 1 else \
                        f"{cat_url}{'&' if '?' in cat_url else '?'}page={n}"
                    html = _load(page, url)
                    time.sleep(pause)
                    if html is None:
                        blocked_pages += 1
                        break
                    found = products_from_html(html, url) or _dom_products(page)
                    new = _absorb(seen, found, cat_path)
                    if not new:
                        break
                    if (limit and len(seen) >= limit) or len(seen) >= cfg.max_products:
                        break
                if (limit and len(seen) >= limit) or len(seen) >= cfg.max_products:
                    break
            if blocked_pages:
                res.notes.append(f"{blocked_pages} pagina('s) geblokkeerd of niet geladen")
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


def _load(page, url: str) -> str | None:
    """Pagina laden en laten renderen; None bij fout of blokkadepagina."""
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception:
        return None
    if resp is not None and resp.status in (403, 429, 503):
        return None
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass  # druk-bezette pagina's worden nooit 'idle' — inhoud is er vaak al
    try:
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight / 2)")
        page.wait_for_timeout(700)
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(700)
        html = page.content()
    except Exception:
        return None
    head = html[:4000]
    if BLOCK_HINTS.search(head) and "product" not in head.lower():
        return None
    return html


def _dom_products(page) -> list[Product]:
    """Vangnet: productkaarten uit de gerenderde DOM (links met een €-prijs)."""
    try:
        raw = page.evaluate(DOM_SCAN_JS)
    except Exception:
        return []
    products: list[Product] = []
    for item in raw:
        href, text = item.get("href", ""), item.get("text", "")
        prices = [parse_price(m) for m in PRICE_TEXT_RE.findall(text)]
        prices = [p for p in prices if p]
        if not prices:
            continue
        price, was = min(prices), None
        if len(prices) > 1 and max(prices) > min(prices):
            was = max(prices)
        lines = [l.strip() for l in text.splitlines() if l.strip() and "€" not in l]
        title = lines[0] if lines else ""
        if not title:
            continue
        products.append(Product(key=url_key(href), title=title[:200], url=href,
                                price=price, was_price=was))
    return products


def _absorb(seen: dict[str, Product], found: list[Product], cat_path: str) -> int:
    new = 0
    for p in found:
        if not p.category_raw:
            p.category_raw = cat_path
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
