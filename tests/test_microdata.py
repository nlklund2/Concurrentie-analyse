"""Prijzen die niet in JSON staan maar in HTML-attributen.

Bij terStal bleef 57% van de artikelen prijsloos omdat de extractie alleen naar
JSON keek. Microdata en og:-metatags zijn de standaard tweede plek.
"""
from scraper.jsonscan import price_from_microdata


def test_microdata_prijs_in_meta_tag():
    assert price_from_microdata('<meta itemprop="price" content="7.99">') == (7.99, None)


def test_microdata_prijs_met_omgekeerde_attribuutvolgorde():
    html = '<span content="4,99" itemprop="price">4,99</span>'
    assert price_from_microdata(html) == (4.99, None)


def test_listprice_is_een_echte_van_prijs():
    html = ('<meta itemprop="price" content="7.99">'
            '<meta itemprop="listPrice" content="12.99">')
    assert price_from_microdata(html) == (7.99, 12.99)


def test_highprice_is_geen_van_prijs():
    """highPrice is de bovenkant van een prijsreeks over varianten. Als
    van-prijs opvoeren verzint korting en blaast de sale-druk op."""
    html = ('<meta itemprop="price" content="7.99">'
            '<meta itemprop="highPrice" content="12.99">')
    assert price_from_microdata(html) == (7.99, None)


def test_open_graph_prijs_als_terugval():
    html = '<meta property="product:price:amount" content="3.49">'
    assert price_from_microdata(html) == (3.49, None)


def test_van_prijs_lager_dan_prijs_telt_niet():
    html = ('<meta itemprop="price" content="9.99">'
            '<meta itemprop="listPrice" content="5.00">')
    assert price_from_microdata(html) == (9.99, None)


def test_geen_prijs_geeft_niets():
    assert price_from_microdata("<div>uitverkocht</div>") == (None, None)
