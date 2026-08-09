"""Fixes na de eerste echte weekrun (week 32): de doelgroep bleef 'onbekend'
omdat het crawlpad werd verdrongen door de categorie van de bron zelf."""
from scraper.models import Product
from scraper.normalize import map_category
from scraper.strategies.listing_crawl import _absorb, _voeg_samen
from scraper.strategies.sitemap_pages import _pad


def test_voeg_samen_ontdubbelt_en_behoudt_volgorde():
    assert _voeg_samen("dames > lingerie", "Pyjama's") == "dames > lingerie > Pyjama's"
    assert _voeg_samen("dames", "dames") == "dames"      # geen herhaling
    assert _voeg_samen("", "Pyjama's") == "Pyjama's"     # leeg deel valt weg
    assert _voeg_samen("dames", "") == "dames"


def test_absorb_behoudt_doelgroep_uit_crawlpad():
    """Het probleem uit week 32: bron gaf 'Pyjama's', crawlpad gaf 'dames'.
    Alleen samen levert dat dames / nachtmode op."""
    seen: dict[str, Product] = {}
    _absorb(seen, [Product(key="1", title="Korte pyjama met print",
                           category_raw="Pyjama's", price=15.0)],
            "nl-nl > dames > nachtmode")
    cat = seen["1"].category_raw
    assert "dames" in cat and "Pyjama" in cat
    assert map_category(cat, title="Korte pyjama met print") == ("dames", "nachtmode")


def test_absorb_vult_aan_bij_tweede_waarneming():
    """Zelfde artikel in twee categorieën: beide paden blijven bewaard."""
    seen: dict[str, Product] = {}
    _absorb(seen, [Product(key="1", title="Slip", category_raw="", price=None)], "dames")
    _absorb(seen, [Product(key="1", title="Slip", category_raw="Slips", price=4.99)], "dames > ondergoed")
    p = seen["1"]
    assert p.price == 4.99                      # rij mét prijs wint
    assert "dames" in p.category_raw and "Slips" in p.category_raw


def test_pad_uit_product_url():
    """Zeeman-patroon: de doelgroep zit alleen in het URL-pad."""
    pad = _pad("https://www.zeeman.com/nl/dames/ondergoed/slips/mady-slip-blauw-123")
    assert "dames" in pad and "ondergoed" in pad
    assert "mady slip blauw 123" not in pad      # de artikelslug zelf telt niet mee
    assert map_category(pad)[0] == "dames"
