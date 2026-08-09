"""Firecrawl-strategie offline getest: het hele pad van API-antwoord tot
producten, zonder credits te verbranden. De echte dienst wisselt alleen de
HTML-inhoud; de logica eromheen (sleutel, fouten, categorie-samenvoeging,
credit-stop) ligt hier vast."""
import json

import pytest

from scraper.config import RetailerCfg
from scraper.strategies import firecrawl_api


LISTING_HTML = """<html><body>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
  {"@type": "ListItem", "position": 1, "item": {
     "@type": "Product", "name": "Dames hipsters 2-pack", "sku": "W1",
     "url": "https://www.wibra.nl/p/dames-hipsters",
     "offers": {"@type": "Offer", "price": "3.99", "priceCurrency": "EUR"}}},
  {"@type": "ListItem", "position": 2, "item": {
     "@type": "Product", "name": "Herensokken 5-pack", "sku": "W2",
     "url": "https://www.wibra.nl/p/herensokken",
     "offers": {"@type": "Offer", "price": "4.49", "priceCurrency": "EUR"}}}
]}
</script></body></html>"""

START_HTML = """<html><body><nav>
<a href="/dames/ondergoed">Dames ondergoed</a>
<a href="/heren/ondergoed">Heren ondergoed</a>
<a href="/klantenservice">Klantenservice</a>
</nav></body></html>"""


class _Resp:
    def __init__(self, status=200, html=None, body=None):
        self.status_code = status
        payload = body if body is not None else {"success": True, "data": {"html": html}}
        self.text = json.dumps(payload)
        self._payload = payload

    def json(self):
        return self._payload


def _sessie(monkeypatch, antwoorden):
    """session.post vervangen: elke aanroep levert het volgende antwoord."""
    calls = []

    def post(self, url, json=None, timeout=None):
        calls.append(json["url"])
        uit = antwoorden[min(len(calls) - 1, len(antwoorden) - 1)]
        return uit

    monkeypatch.setattr("requests.Session.post", post)
    return calls


def _cfg(**over):
    return RetailerCfg(id="wibra", name="Wibra", base="https://www.wibra.nl",
                       strategy="firecrawl", enrich=False, **over)


def test_zonder_sleutel_schone_fout(monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    calls = _sessie(monkeypatch, [_Resp(500)])
    res = firecrawl_api.scrape(_cfg(), http=None)
    assert "FIRECRAWL_API_KEY" in res.error
    assert calls == []          # geen credit verbrand zonder sleutel


def test_producten_uit_gerenderde_html(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    calls = _sessie(monkeypatch, [_Resp(html=LISTING_HTML)])
    cfg = _cfg(seeds=["https://www.wibra.nl/dames/ondergoed"])
    res = firecrawl_api.scrape(cfg, http=None)
    assert res.error == ""
    assert {p.title for p in res.products} == {"Dames hipsters 2-pack",
                                               "Herensokken 5-pack"}
    # crawlpad (doelgroep) wordt vóór de bron-categorie geplakt
    assert all(p.category_raw.startswith("dames > ondergoed") for p in res.products)
    assert any("1 Firecrawl-credits" in n for n in res.notes)


def test_credits_op_stopt_meteen(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    calls = _sessie(monkeypatch, [_Resp(402)])
    cfg = _cfg(seeds=["https://www.wibra.nl/dames/ondergoed",
                      "https://www.wibra.nl/heren/ondergoed"])
    res = firecrawl_api.scrape(cfg, http=None)
    assert "credits op" in res.error
    assert len(calls) == 1      # niet doorstoken op een lege portemonnee


def test_ongeldige_sleutel_niet_overschreven(monkeypatch):
    """Als de sitemap niets oplevert én de nav-poging 401 geeft, moet de
    401 de foutmelding zijn — niet 'geen categorie-URLs gevonden'."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-ongeldig")
    _sessie(monkeypatch, [_Resp(401)])
    monkeypatch.setattr(firecrawl_api, "_category_urls", lambda cfg, http, res: [])
    res = firecrawl_api.scrape(_cfg(), http=None)
    assert "ongeldig" in res.error


def test_navigatie_fallback_zonder_sitemap(monkeypatch):
    """Sitemap geblokkeerd → startpagina via Firecrawl → categorieën → producten."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    calls = _sessie(monkeypatch, [_Resp(html=START_HTML),
                                  _Resp(html=LISTING_HTML),
                                  _Resp(html=LISTING_HTML)])
    monkeypatch.setattr(firecrawl_api, "_category_urls", lambda cfg, http, res: [])
    cfg = _cfg(focus_categories="ondergoed")
    res = firecrawl_api.scrape(cfg, http=None)
    assert calls[0] == "https://www.wibra.nl"
    assert set(calls[1:]) == {"https://www.wibra.nl/dames/ondergoed",
                              "https://www.wibra.nl/heren/ondergoed"}
    assert len(res.products) == 2
    assert any("startpagina" in n for n in res.notes)
    # klantenservice-link is ruis en mag geen credit kosten
    assert not any("klantenservice" in c for c in calls)
