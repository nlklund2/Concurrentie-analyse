"""Toegangsladder (scraper/fetch.py): klimmen bij een weigering, niet eerder.

Zeeman 14-09-2026: HTTP 403 op de eerste seed betekende een week zonder
cijfers. De ladder moet dan zelf naar de volgende trede, dat in de notities
en de strategie van het rapport laten zien, robots.txt via de nieuwe trede
opnieuw lezen, en pas 'alle treden geweigerd' zeggen als dat ook zo is.
Alle treden zijn hier nep — het netwerk naar de retailers is dicht."""
import pytest

import scraper.fetch as fetch
import scraper.strategies.listing_crawl as lc
from scraper import strategies
from scraper.config import RetailerCfg
from scraper.http import BlockedError
from scraper.models import ScrapeResult
from tests.test_flight import BASE, _item, _pagina

ROBOTS = "https://www.zeeman.com/robots.txt"


class _Resp:
    def __init__(self, text, status=200, headers=None):
        self.text, self.status_code, self.headers = text, status, headers or {}


class _Http:
    """Nep-requests-client: per URL een antwoord, of een BlockedError."""
    def __init__(self, paginas, blokkade=None):
        self.paginas, self.blokkade = paginas, blokkade or {}
        self.opgehaald, self.requests_done, self.robots_skipped = [], 0, 0
        self.user_agent, self.min_delay, self._robots = "test-agent", 0, {}

    def get(self, url):
        self.opgehaald.append(url)
        self.requests_done += 1
        if url in self.blokkade:
            status = self.blokkade[url]
            raise BlockedError(f"HTTP {status} op {url}", status=status, url=url,
                               headers={"server": "cloudflare", "cf-ray": "x"},
                               body="<title>Just a moment...</title>")
        return _Resp(self.paginas[url]) if url in self.paginas else None


def _cfg(**kw):
    kw.setdefault("fetch_ladder", ["http", "chrome", "browser", "firecrawl"])
    kw.setdefault("min_delay", 0)
    return RetailerCfg(id="zeeman", name="Zeeman", base="https://www.zeeman.com/nl-nl",
                       strategy="listing", seeds=[BASE], **kw)


def _trede_nep(monkeypatch, naam, paginas, blokkade=(), log=None):
    """Een hogere trede vervangen door een woordenboek-lezer."""
    def via(self, url):
        if log is not None:
            log.append((naam, url))
        if url in blokkade:
            raise BlockedError(f"HTTP 403 op {url} ({naam})", status=403, url=url)
        return paginas.get(url)
    monkeypatch.setattr(fetch.Fetcher, f"_via_{naam}", via)


def _pagina_1():
    return _pagina([_item(f"Slip {i} - Wit", f"10-{i}", 399) for i in range(3)], total=3, pages=1)


# ---- klimmen -----------------------------------------------------------------

def test_zonder_weigering_blijft_de_ladder_op_http():
    http = _Http({BASE: _pagina_1()})
    res = lc.scrape(_cfg(), http)
    assert len(res.products) == 3 and res.strategy == "listing"
    assert not any(n.startswith("toegang:") for n in res.notes)


def test_403_op_http_klimt_naar_chrome_en_leest_robots_opnieuw(monkeypatch):
    log = []
    http = _Http({}, blokkade={BASE: 403})
    _trede_nep(monkeypatch, "chrome", {ROBOTS: "User-agent: *\nDisallow: /api/\n",
                                        BASE: _pagina_1()}, log=log)
    res = lc.scrape(_cfg(), http)
    assert len(res.products) == 3
    assert res.strategy == "listing+chrome"
    assert res.error == ""
    # robots.txt is via de nieuwe trede gelezen vóór de eerste pagina
    assert log[0] == ("chrome", ROBOTS) and log[1] == ("chrome", BASE)
    assert any(n.startswith("toegang: trede 'http' geweigerd") and "verder via 'chrome'" in n
               for n in res.notes)
    assert http.requests_done == 1 + len(log)   # hogere treden tellen mee in de requests-kolom


def test_robots_via_de_nieuwe_trede_wordt_gerespecteerd(monkeypatch):
    http = _Http({}, blokkade={BASE: 403})
    _trede_nep(monkeypatch, "chrome", {ROBOTS: "User-agent: *\nDisallow: /nl-nl/dames/\n",
                                        BASE: _pagina_1()})
    res = lc.scrape(_cfg(), http)
    assert res.products == []
    assert http.robots_skipped == 1


def test_klimt_door_tot_de_laatste_trede_en_meldt_dan_alles(monkeypatch):
    http = _Http({}, blokkade={BASE: 403})
    _trede_nep(monkeypatch, "chrome", {ROBOTS: ""}, blokkade={BASE})
    _trede_nep(monkeypatch, "browser", {ROBOTS: ""}, blokkade={BASE})
    _trede_nep(monkeypatch, "firecrawl", {ROBOTS: ""}, blokkade={BASE})
    res = lc.scrape(_cfg(), http)
    assert res.products == [] and res.strategy == "listing"
    assert res.error.startswith("alle treden van de toegangsladder geweigerd — http: HTTP 403")
    assert "chrome:" in res.error and "browser:" in res.error and "firecrawl:" in res.error
    assert sum(n.startswith("toegang:") for n in res.notes) == 3


def test_ontbrekende_trede_wordt_overgeslagen_met_notitie(monkeypatch):
    def geen_curl(self, url):
        raise fetch.TredeOntbreekt("curl_cffi niet geïnstalleerd")
    monkeypatch.setattr(fetch.Fetcher, "_via_chrome", geen_curl)
    http = _Http({}, blokkade={BASE: 403})
    _trede_nep(monkeypatch, "browser", {ROBOTS: "", BASE: _pagina_1()})
    res = lc.scrape(_cfg(), http)
    assert res.strategy == "listing+browser"
    assert any("trede 'chrome' niet beschikbaar (curl_cffi niet geïnstalleerd)" in n
               for n in res.notes)


def test_429_krijgt_een_herkansing_op_dezelfde_trede(monkeypatch):
    monkeypatch.setattr(fetch, "WACHT_BIJ_429", 0)
    pogingen = {"n": 0}

    class _Http429(_Http):
        def get(self, url):
            pogingen["n"] += 1
            if pogingen["n"] == 1:
                raise BlockedError("HTTP 429", status=429, url=url)
            return _Resp(self.paginas[url])

    res = lc.scrape(_cfg(), _Http429({BASE: _pagina_1()}))
    assert len(res.products) == 3 and res.strategy == "listing"
    assert pogingen["n"] == 2


def test_challenge_pagina_met_http_200_telt_als_weigering(monkeypatch):
    http = _Http({BASE: "<html><title>Just a moment...</title><body>Checking your browser…"})
    _trede_nep(monkeypatch, "chrome", {ROBOTS: "", BASE: _pagina_1()})
    res = lc.scrape(_cfg(), http)
    assert res.strategy == "listing+chrome"
    assert any("challenge-pagina" in n for n in res.notes)


def test_ladder_zonder_config_is_alleen_http_en_escalatie_stopt_meteen():
    http = _Http({}, blokkade={BASE: 403})
    res = lc.scrape(_cfg(fetch_ladder=[]), http)
    assert fetch.ladder_van(_cfg(fetch_ladder=[])) == ["http"]
    assert res.error.startswith("alle treden van de toegangsladder geweigerd — http:")
    assert res.strategy == "listing"


def test_onbekende_treden_worden_genegeerd():
    assert fetch.ladder_van(_cfg(fetch_ladder=["browser", "raket", "http", "browser"])) == ["browser", "http"]


# ---- firecrawl-trede: cap en credits --------------------------------------------

def test_firecrawl_trede_telt_credits_en_stopt_op_de_cap(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    import scraper.strategies.firecrawl_api as fc_api
    gehaald = []

    def nep(session, url, res, raw=False, **kw):
        gehaald.append(url)
        assert raw is True
        return {ROBOTS: "", BASE: _pagina_1()}.get(url)
    monkeypatch.setattr(fc_api, "_firecrawl_html", nep)

    http = _Http({}, blokkade={BASE: 403})
    res = lc.scrape(_cfg(fetch_ladder=["http", "firecrawl"], firecrawl_page_cap=5), http)
    assert res.strategy == "listing+firecrawl" and len(res.products) == 3
    assert res.credits_used == len(gehaald) == 2      # robots.txt + de pagina

    res2 = ScrapeResult(retailer_id="zeeman")
    f = fetch.Fetcher(_cfg(fetch_ladder=["firecrawl"], firecrawl_page_cap=1, respect_robots=False),
                      _Http({}), res2)
    assert f.html(BASE) is not None
    with pytest.raises(BlockedError, match="Firecrawl-cap van 1"):
        f.html(BASE + "?page=2")


def test_firecrawl_trede_zonder_sleutel_is_niet_beschikbaar(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    http = _Http({}, blokkade={BASE: 403})
    res = lc.scrape(_cfg(fetch_ladder=["http", "firecrawl"]), http)
    assert "firecrawl: FIRECRAWL_API_KEY niet gezet" in res.error


# ---- via het strategieregister: notities en requests blijven bewaard -----------

def test_strategies_run_bewaart_ladder_notities_bij_volledige_weigering(monkeypatch):
    monkeypatch.setattr(strategies, "Http", lambda **kw: _Http({}, blokkade={BASE: 403}))
    _trede_nep(monkeypatch, "chrome", {ROBOTS: ""}, blokkade={BASE})
    res = strategies.run(_cfg(fetch_ladder=["http", "chrome"]))
    assert res.error.startswith("alle treden van de toegangsladder geweigerd")
    assert any(n.startswith("toegang: trede 'http' geweigerd") for n in res.notes)
    assert res.strategy == "listing"
