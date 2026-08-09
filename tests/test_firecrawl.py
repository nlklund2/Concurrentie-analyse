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

# Wibra-scenario: de startpagina toont productteasers mét prijs die op de
# focusregex matchen, terwijl de echte afdelingen geen focuswoord dragen.
START_MET_TEASERS = """<html><body>
<nav><a href="/dames">Dames</a><a href="/heren">Heren</a></nav>
<div class="teaser">
  <a href="/assortiment/baby-pyjama-safari"><img alt="Baby pyjama safari">€ 6,99</a>
  <a href="/assortiment/baby-pyjama-bloem"><img alt="Baby pyjama bloem">€ 7,99</a>
</div></body></html>"""

# HEMA-scenario: gerenderde kaarten zonder ingebedde JSON; prijs vóór én
# achter het getal, plus een navigatietegel die geen artikel is.
KAARTEN_HTML = """<html><body>
<a href="/productoverzicht/dames-slips-123">
  <img alt="dames slips katoen - 3 paar"><span>7,50 €</span></a>
<a href="/productoverzicht/herensokken-456">
  <img alt="herensokken naadloos - 2 paar"><span>€ 4,00</span><del>€ 6,00</del></a>
<a href="/dames/lingerie">Bekijk alles <span>vanaf € 3,50</span></a>
<a href="/klantenservice">Klantenservice € 0,00</a>
</body></html>"""

# HEMA/C&A-vorm: de prijs staat búiten de link, in de omliggende kaart.
KAART_PRIJS_BUITEN_LINK = """<html><body><ul>
<li class="product-card">
  <a href="/productoverzicht/dames-hipsters-789"><img alt="dames hipsters - 2 paar"></a>
  <div class="prijs"><span>€ 6,50</span></div>
</li>
<li class="product-card">
  <a href="/productoverzicht/heren-boxers-101"><img alt="heren boxers - 3 paar"></a>
  <div class="prijs"><span>9,25 €</span></div>
</li>
</ul></body></html>"""

# Wibra-scenario: sitemap met duizenden productpagina's onder /assortiment/
# (die als categorie ogen) en een handvol echte lijstpagina's.
SITEMAP_XML = "<urlset>" + "".join(
    f"<url><loc>https://www.wibra.nl/assortiment/artikel-{i}-baby-pyjama/</loc></url>"
    for i in range(150)) + """
<url><loc>https://www.wibra.nl/thema/baby-ondergoed</loc></url>
<url><loc>https://www.wibra.nl/thema/dames-ondergoed</loc></url>
<url><loc>https://www.wibra.nl/klantenservice</loc></url>
</urlset>"""


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
    basis = dict(id="wibra", name="Wibra", base="https://www.wibra.nl",
                 strategy="firecrawl", enrich=False)
    basis.update(over)
    return RetailerCfg(**basis)


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


def test_kaart_vangnet_zonder_ingebedde_json(monkeypatch):
    """HEMA rendert de lijst maar sluit geen JSON in: kaarten zijn de bron."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    _sessie(monkeypatch, [_Resp(html=KAARTEN_HTML)])
    cfg = _cfg(base="https://www.hema.nl",
               seeds=["https://www.hema.nl/dames/lingerie"])
    res = firecrawl_api.scrape(cfg, http=None)
    by_title = {p.title: p for p in res.products}
    assert set(by_title) == {"dames slips katoen - 3 paar",
                             "herensokken naadloos - 2 paar"}
    assert by_title["dames slips katoen - 3 paar"].price == 7.50   # '7,50 €'
    sokken = by_title["herensokken naadloos - 2 paar"]
    assert (sokken.price, sokken.was_price) == (4.00, 6.00)
    assert any("kaart-vangnet" in n for n in res.notes)


def test_kaart_vangnet_prijs_buiten_de_link(monkeypatch):
    """HEMA/C&A-vorm: de prijs hangt naast het anker in de kaart. De statische
    lezer loopt dan omhoog, net als de DOM-scan in de browser."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    _sessie(monkeypatch, [_Resp(html=KAART_PRIJS_BUITEN_LINK)])
    cfg = _cfg(base="https://www.hema.nl",
               seeds=["https://www.hema.nl/dames/lingerie"])
    res = firecrawl_api.scrape(cfg, http=None)
    by_title = {p.title: p.price for p in res.products}
    assert by_title == {"dames hipsters - 2 paar": 6.50,
                       "heren boxers - 3 paar": 9.25}


def test_sitemap_via_firecrawl_weert_productnamespace(monkeypatch):
    """Wibra: de navigatie kent geen echte afdelingen; de sitemap wel — maar
    dan moeten de duizenden /assortiment/-productpagina's er eerst uit."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    calls = _sessie(monkeypatch, [_Resp(body={"success": True,
                                              "data": {"rawHtml": SITEMAP_XML}}),
                                  _Resp(html=LISTING_HTML),
                                  _Resp(html=LISTING_HTML)])
    monkeypatch.setattr(firecrawl_api, "_category_urls", lambda cfg, http, res: [])
    cfg = _cfg(focus_categories="ondergoed")
    res = firecrawl_api.scrape(cfg, http=None)
    assert calls[0] == "https://www.wibra.nl/sitemap.xml"
    assert set(calls[1:]) == {"https://www.wibra.nl/thema/baby-ondergoed",
                              "https://www.wibra.nl/thema/dames-ondergoed"}
    assert not any("/assortiment/" in c for c in calls)
    assert any("sitemap via Firecrawl" in n for n in res.notes)
    assert res.products


GEEN_SITEMAP = [_Resp(html="<html>geen sitemap hier</html>")] * 3


def test_nav_teasers_zijn_geen_categorieen(monkeypatch):
    """Wibra: productteasers mét prijs mogen de echte afdelingen niet
    verdringen, ook al matchen alleen de teasers de focusregex."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    calls = _sessie(monkeypatch, GEEN_SITEMAP + [_Resp(html=START_MET_TEASERS),
                                                 _Resp(html=LISTING_HTML)])
    monkeypatch.setattr(firecrawl_api, "_category_urls", lambda cfg, http, res: [])
    cfg = _cfg(focus_categories="ondergoed|pyjama", max_categories=2)
    res = firecrawl_api.scrape(cfg, http=None)
    gecrawld = set(calls[4:])
    assert gecrawld <= {"https://www.wibra.nl/dames", "https://www.wibra.nl/heren"}
    assert not any("assortiment" in c for c in gecrawld)
    assert res.products


def test_navigatie_fallback_zonder_sitemap(monkeypatch):
    """Sitemap geblokkeerd of leeg → startpagina via Firecrawl → categorieën."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test")
    calls = _sessie(monkeypatch, GEEN_SITEMAP + [_Resp(html=START_HTML),
                                                 _Resp(html=LISTING_HTML),
                                                 _Resp(html=LISTING_HTML)])
    monkeypatch.setattr(firecrawl_api, "_category_urls", lambda cfg, http, res: [])
    cfg = _cfg(focus_categories="ondergoed")
    res = firecrawl_api.scrape(cfg, http=None)
    assert calls[0] == "https://www.wibra.nl/sitemap.xml"   # eerst de sitemap proberen
    assert calls[3] == "https://www.wibra.nl"               # dan pas de startpagina
    assert set(calls[4:]) == {"https://www.wibra.nl/dames/ondergoed",
                              "https://www.wibra.nl/heren/ondergoed"}
    assert len(res.products) == 2
    assert any("startpagina" in n for n in res.notes)
    # klantenservice-link is ruis en mag geen credit kosten
    assert not any("klantenservice" in c for c in calls)
