"""Artikelsleutel uit de URL (key_from_url): Action wisselde t/m W40 elke week
de id in zijn ingebedde JSON; het productnummer in de URL bleef gelijk."""
from scraper import strategies
from scraper.config import load_retailers
from scraper.models import Product, ScrapeResult


def _p(key, url):
    return Product(key=key, title="Pyjama", url=url, price=7.99)


def test_sleutel_wordt_het_urlnummer_en_dubbelen_vallen_samen():
    res = ScrapeResult(retailer_id="action", products=[
        _p("253741", "https://www.action.com/nl-nl/p/2555484/pyjama/"),
        _p("999999", "https://www.action.com/nl-nl/p/2555484/pyjama/"),
        _p("abc", "https://www.action.com/nl-nl/p/3219005/pyjama/"),
        _p("zonder-match", "https://www.action.com/nl-nl/c/mode/"),
    ])
    strategies.sleutel_uit_url(res, r"/p/(\d+)/")
    assert [p.key for p in res.products] == ["2555484", "3219005", "zonder-match"]
    assert any("1 dubbele" in n for n in res.notes)


def test_action_config_draagt_het_patroon():
    cfg = {c.id: c for c in load_retailers()}["action"]
    assert cfg.key_from_url == r"/p/(\d+)/"
