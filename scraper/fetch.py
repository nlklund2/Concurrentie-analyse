"""Toegangsladder: dezelfde pagina via een steeds zwaardere client ophalen.

Zeeman, 14-09-2026: op 07-09 kreeg GitHub Actions nog byte voor byte dezelfde
categoriepagina als een gewone browser (W37: 1.058 artikelen); een week later
was élke request HTTP 403, vanaf de allereerste seed. Niets aan onze kant was
veranderd — de bron had een poortwachter aangezet. Zo'n omslag komt vaker
voor (Action 03-09: sessiewering; Wibra/HEMA: datacenter-IP geweerd), en tot
nu toe betekende hij een week rood plus handwerk.

De ladder maakt daar een automatisme van. Per bron staat in retailers.yml
een volgorde van treden; de crawl begint op de eerste en klimt pas als een
trede aantoonbaar geweigerd wordt (403/429 of een challenge-pagina):

  http       requests — de gewone Python-client (gratis, ±0,3 s per pagina)
  chrome     curl_cffi met het TLS-/HTTP2-handschrift van Chrome — voor
             poortwachters die op de fingerprint van de client filteren
             (Cloudflare Bot Fight Mode, Vercel-firewall) (gratis)
  browser    echte Chromium via Playwright — lost JavaScript-challenges op;
             de HTML komt uit de browser, de extractie blijft dezelfde
             (gratis, ±2 s per pagina)
  firecrawl  externe dienst met residentiële IP's — als het datacenter-IP
             zelf geweerd wordt (betaald: 1 credit per pagina, gecapt)

Wat níet verandert: ±1 request per seconde, robots.txt wordt gerespecteerd
(opgehaald via dezelfde ladder, dus ook als de eerste trede dicht is),
alleen publieke lijstpagina's, één run per week. De trede die het werk deed
staat in het weekrapport als 'listing+chrome' e.d., zodat een verschuiving
zichtbaar is vóór hij een probleem wordt. Zie PLAN.md §8.
"""
from __future__ import annotations

import os
import time
import urllib.robotparser
from urllib.parse import urlsplit

from . import blokkade
from .config import RetailerCfg
from .http import BlockedError, Http
from .jsonscan import flight_payload
from .models import ScrapeResult

TREDEN = ("http", "chrome", "browser", "firecrawl")
STANDAARD_LADDER = ["http"]
CHROME_TARGET = "chrome"      # curl_cffi: de nieuwste Chrome die de bibliotheek kent
WACHT_BIJ_429 = 20            # seconden; één herkansing op dezelfde trede
CHALLENGE_WACHT_S = 20        # een JS-challenge die zichzelf oplost krijgt zoveel tijd
BROWSER_TIMEOUT_MS = 45000

# Zelfde anti-detectie als de render-strategie; hier los gedefinieerd zodat
# de ladder niet aan het strategiepakket hangt.
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'languages', {get: () => ['nl-NL', 'nl', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
"""
_BALLAST = {"image", "media", "font"}


class TredeOntbreekt(RuntimeError):
    """De trede kan niet draaien (bibliotheek/sleutel ontbreekt) — overslaan."""


def ladder_van(cfg: RetailerCfg) -> list[str]:
    treden = [t for t in (cfg.fetch_ladder or STANDAARD_LADDER) if t in TREDEN]
    return list(dict.fromkeys(treden)) or list(STANDAARD_LADDER)


class Fetcher:
    """Haalt HTML op via de laagste trede die nog werkt.

    html(url) geeft de pagina-HTML, None als de pagina er niet is (404,
    netwerkfout, robots.txt) en gooit BlockedError als álle treden nee zeggen.
    Escalatie is definitief voor de rest van de run: niet heen en weer
    springen, dat kost alleen maar geweigerde requests."""

    def __init__(self, cfg: RetailerCfg, http: Http, res: ScrapeResult):
        self.cfg, self.http, self.res = cfg, http, res
        self.ladder = ladder_van(cfg)
        self.k = 0
        self.geweigerd: list[str] = []
        self.credits = 0
        self._chrome: Http | None = None
        self._pw = self._browser = self._context = self._page = None
        self._fc_session = None
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._laatste = 0.0

    # -- publiek ---------------------------------------------------------
    @property
    def trede(self) -> str:
        return self.ladder[self.k]

    @property
    def geklommen(self) -> bool:
        return self.trede != "http"

    def html(self, url: str) -> str | None:
        return self._ophalen(url)

    def close(self) -> None:
        for sluit in (lambda: self._context.close() if self._context else None,
                      lambda: self._browser.close() if self._browser else None,
                      lambda: self._pw.stop() if self._pw else None):
            try:
                sluit()
            except Exception:
                pass
        self._pw = self._browser = self._context = self._page = None

    # -- ladder ----------------------------------------------------------
    def _ophalen(self, url: str, robots: bool = True) -> str | None:
        herkanst_429 = False
        while True:
            # Op de http-trede doet de client de robots-check zelf; op de
            # hogere treden doet de ladder het, via diezelfde trede — anders
            # zou een 403 op robots.txt gelden als 'geen robots.txt'. Buiten
            # de try: is robots.txt op álle treden dicht, dan is dat het
            # eindoordeel en geen aanleiding om nóg eens te klimmen.
            if robots and self.trede != "http" and self.cfg.respect_robots \
                    and not self._toegestaan(url):
                self.http.robots_skipped = getattr(self.http, "robots_skipped", 0) + 1
                return None
            trede = self.trede
            try:
                return self._via(trede, url)
            except BlockedError as e:
                if e.status == 429 and not herkanst_429:
                    # Een tempo-limiet is geen wering: even wachten en
                    # dezelfde trede nog één keer, vóór het zwaardere geschut.
                    herkanst_429 = True
                    time.sleep(WACHT_BIJ_429)
                    continue
                self._escaleer(trede, str(e), e)
            except TredeOntbreekt as e:
                self._escaleer(trede, str(e), None, ontbreekt=True)

    def _escaleer(self, trede: str, reden: str, e: BlockedError | None,
                  ontbreekt: bool = False) -> None:
        self.geweigerd.append(f"{trede}: {reden[:140]}")
        if self.k + 1 >= len(self.ladder):
            raise BlockedError(
                "alle treden van de toegangsladder geweigerd — " + "; ".join(self.geweigerd),
                status=getattr(e, "status", 0), headers=getattr(e, "headers", None),
                body=getattr(e, "body", ""), url=getattr(e, "url", ""))
        self.k += 1
        self._robots.clear()                 # robots.txt opnieuw via de nieuwe trede
        self.res.notes.append(
            f"toegang: trede '{trede}' {'niet beschikbaar' if ontbreekt else 'geweigerd'} "
            f"({reden[:120]}) → verder via '{self.trede}'")

    def _via(self, trede: str, url: str) -> str | None:
        if trede == "http":
            return self._via_http(url)
        self._tel()          # ook de hogere treden tellen mee in de requests-kolom
        if trede == "chrome":
            return self._via_chrome(url)
        if trede == "browser":
            return self._via_browser(url)
        if trede == "firecrawl":
            return self._via_firecrawl(url)
        raise TredeOntbreekt(f"onbekende trede '{trede}'")

    # -- treden ----------------------------------------------------------
    def _via_http(self, url: str) -> str | None:
        resp = self.http.get(url)
        if resp is None:
            return None
        return _challenge_check(resp.text, resp, url, "http")

    def _via_chrome(self, url: str) -> str | None:
        if self._chrome is None:
            try:
                self._chrome = Http(min_delay=self.cfg.min_delay, respect_robots=False,
                                    impersonate=CHROME_TARGET)
            except ImportError:
                raise TredeOntbreekt("curl_cffi niet geïnstalleerd (pip install curl_cffi)")
        resp = self._chrome.get(url)
        if resp is None:
            return None
        return _challenge_check(resp.text, resp, url, "chrome")

    def _via_browser(self, url: str) -> str | None:
        if self._page is None:
            self._start_browser()
        self._wacht(self.cfg.min_delay)
        page = self._page
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
        except Exception:
            return None                      # timeout/netwerk: pagina overslaan
        status = resp.status if resp is not None else 0
        headers = dict(resp.headers) if resp is not None else {}
        html: str | None = None
        if status == 200:
            try:
                html = resp.text()           # de bytes zoals de browser ze kreeg
            except Exception:
                html = None
            if not html:
                html = _veilig_content(page)
        if status in (403, 429, 503) or (html is not None and blokkade.is_challenge(html)):
            # Challenge die zichzelf oplost (Cloudflare, Vercel): de browser
            # draait het script, de pagina laadt opnieuw — even geduld.
            html = self._wacht_op_challenge(page)
            if html is None:
                body = _veilig_content(page) or ""
                sig = blokkade.signatuur(status, headers, body)
                raise BlockedError(f"HTTP {status} op {url} (browser) — {blokkade.kort(sig)}",
                                   status=status, headers=headers, body=body, url=url)
            return html
        if status != 200:
            return None
        return html

    def _via_firecrawl(self, url: str) -> str | None:
        if not os.environ.get("FIRECRAWL_API_KEY"):
            raise TredeOntbreekt("FIRECRAWL_API_KEY niet gezet")
        if self.credits >= self.cfg.firecrawl_page_cap:
            raise BlockedError(f"Firecrawl-cap van {self.cfg.firecrawl_page_cap} pagina's "
                               "bereikt (firecrawl_page_cap in retailers.yml)", url=url)
        from .strategies.firecrawl_api import _firecrawl_fetch
        if self._fc_session is None:
            import requests
            self._fc_session = requests.Session()
            self._fc_session.headers.update({
                "Authorization": f"Bearer {os.environ['FIRECRAWL_API_KEY']}",
                "Content-Type": "application/json"})
        # Eén opvraging = één credit op het basistarief; een residentiële
        # proxy kan op sommige plannen meer kosten — het Firecrawl-dashboard
        # is de waarheid, deze teller het signaal in het weekrapport.
        self.credits += 1
        self.res.credits_used = self.credits
        self._wacht(self.cfg.min_delay)
        proxy = self.cfg.firecrawl_proxy
        html, status = _firecrawl_fetch(self._fc_session, url, self.res, raw=True, proxy=proxy)
        label = f"firecrawl/{proxy}" if proxy else "firecrawl"
        if status in (403, 429) or (html is not None and blokkade.is_challenge(html)):
            sig = blokkade.signatuur(status or 200, {}, html or "")
            raise BlockedError(f"HTTP {status or 200} op {url} ({label}) — {blokkade.kort(sig)}",
                               status=status or 200, body=html or "", url=url)
        if html is None:
            if self.res.error:               # 401/402: de dienst zelf zegt nee
                fout, self.res.error = self.res.error, ""
                raise BlockedError(fout, url=url)
            return None
        return html

    # -- hulpjes ---------------------------------------------------------
    def _start_browser(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise TredeOntbreekt("playwright niet geïnstalleerd")
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                args=["--disable-blink-features=AutomationControlled"])
            # De echte user-agent van deze Chromium, zonder 'Headless': een
            # verzonnen Chrome/126 bij een nieuwere engine is zelf een signaal.
            proef = self._browser.new_context()
            try:
                ua = proef.new_page().evaluate("() => navigator.userAgent")
            finally:
                proef.close()
            self._context = self._browser.new_context(
                locale="nl-NL", timezone_id="Europe/Amsterdam",
                viewport={"width": 1366, "height": 900},
                user_agent=str(ua).replace("HeadlessChrome", "Chrome"),
                extra_http_headers={"Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"})
            self._context.add_init_script(STEALTH_JS)
            # Plaatjes, video en fonts dragen geen productdata; niet laden
            # scheelt bandbreedte en tijd (de flight-payload zit in de HTML).
            self._context.route("**/*", lambda route: (
                route.abort() if route.request.resource_type in _BALLAST else route.continue_()))
            self._page = self._context.new_page()
        except Exception as e:
            self.close()
            raise TredeOntbreekt(f"browser start niet: {type(e).__name__}: {str(e)[:80]}")

    def _wacht_op_challenge(self, page) -> str | None:
        for _ in range(CHALLENGE_WACHT_S):
            try:
                page.wait_for_timeout(1000)
            except Exception:
                return None
            html = _veilig_content(page)
            if html and not blokkade.is_challenge(html) and (flight_payload(html) or len(html) > 30000):
                return html
        return None

    def _toegestaan(self, url: str) -> bool:
        host = urlsplit(url).netloc
        if host not in self._robots:
            rp: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
            tekst = self._ophalen(f"https://{host}/robots.txt", robots=False)
            if tekst:
                rp.parse(tekst.splitlines())
            else:
                rp = None                    # geen robots.txt → alles toegestaan
            self._robots[host] = rp
        rp = self._robots[host]
        return rp is None or rp.can_fetch(getattr(self.http, "user_agent", "*"), url)

    def _tel(self) -> None:
        """Ook de hogere treden tellen mee in de requests-kolom van het rapport."""
        self.http.requests_done = getattr(self.http, "requests_done", 0) + 1

    def _wacht(self, min_delay: float) -> None:
        rest = min_delay - (time.monotonic() - self._laatste)
        if rest > 0:
            time.sleep(rest)
        self._laatste = time.monotonic()


def _veilig_content(page) -> str | None:
    try:
        return page.content()
    except Exception:
        return None


def _challenge_check(html: str, resp, url: str, trede: str) -> str:
    """Een challenge-pagina met HTTP 200 is óók een weigering."""
    if blokkade.is_challenge(html):
        sig = blokkade.signatuur(200, getattr(resp, "headers", None), html)
        raise BlockedError(f"challenge-pagina op {url} ({trede}) — {blokkade.kort(sig)}",
                           status=200, headers=getattr(resp, "headers", None), body=html, url=url)
    return html


# ---------------------------------------------------------------------------
# Meetinstrument voor de diagnose: elke trede los, zonder escalatie.
# ---------------------------------------------------------------------------

def toegangsmatrix(url: str) -> list[str]:
    """Per client: krijgt hij de pagina, en zo nee — wie zegt nee?

    De combinatie verraadt het soort poortwachter:
      requests ✗, requests+browserheaders ✓  → filter op headers;
      beide ✗, chrome ✓                       → TLS-/HTTP2-fingerprint;
      chrome ✗, browser ✓                     → JavaScript-challenge;
      alles ✗, firecrawl basic ✓              → het IP van GitHub Actions;
      ook basic ✗, firecrawl enhanced ✓       → élk datacenter-IP (alleen
                                                 residentieel komt binnen)."""
    regels: list[str] = []
    varianten: list[tuple[str, str, str]] = [
        ("requests (kaal, zoals de scraper tot 14-09)", "http", ""),
        ("requests + volledige Chrome-headerset", "http+headers", ""),
        ("curl_cffi chrome-impersonatie (TLS/HTTP2-handschrift)", "chrome", ""),
        ("Chromium via Playwright (echte browser)", "browser", ""),
        ("Firecrawl basic (datacenter-proxy, 1 credit)", "firecrawl", "basic"),
        ("Firecrawl enhanced (residentieel IP)", "firecrawl", "enhanced"),
    ]
    for label, trede, proxy in varianten:
        cfg = RetailerCfg(id="diagnose", name="diagnose", base=url, respect_robots=False,
                          min_delay=0.5, firecrawl_proxy=proxy)
        res = ScrapeResult(retailer_id="diagnose")
        http = Http(min_delay=0.5, respect_robots=False, browser_headers=(trede == "http+headers"))
        f = Fetcher(cfg, http, res)
        t0 = time.monotonic()
        try:
            html = f._via("http" if trede == "http+headers" else trede, url)
            duur = time.monotonic() - t0
            if html is None:
                regels.append(f"- {label}: geen antwoord (404/netwerk) na {duur:.1f} s")
                continue
            stroom = flight_payload(html)
            if stroom:
                from .jsonscan import flight_meta, products_from_flight
                teller = flight_meta(html)
                n = len(products_from_flight(html, url))
                regels.append(f"- {label}: **HTTP 200**, {len(html):,} tekens, flight-payload "
                              f"met {n} producten" +
                              (f", teller {teller['total']} artikelen op {teller['totalPages']} "
                               "pagina's" if teller else "") + f" ({duur:.1f} s)")
            else:
                regels.append(f"- {label}: HTTP 200 maar {len(html):,} tekens zónder flight-payload "
                              f"(titel {blokkade.titel(html)!r}) — uitgeklede pagina? ({duur:.1f} s)")
        except BlockedError as e:
            regels.append(f"- {label}: **geweigerd** — {e} · handtekening: {e.signatuur} "
                          f"(titel {blokkade.titel(e.body)!r}, {len(e.body):,} tekens, "
                          f"{time.monotonic() - t0:.1f} s)")
        except TredeOntbreekt as e:
            regels.append(f"- {label}: niet beschikbaar — {e}")
        except Exception as e:
            regels.append(f"- {label}: fout — {type(e).__name__}: {str(e)[:120]}")
        finally:
            f.close()
        for n in res.notes:
            regels.append(f"    - {n}")
    return regels
