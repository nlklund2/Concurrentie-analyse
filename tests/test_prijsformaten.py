"""Prijsschrijfwijzen: beide europosities, en wat géén prijs is.

Draait zonder browser — de regexes zelf waren de bron van twee meetfouten:
C&A's '24,99 €' werd overgeslagen, en Zeeman's 'algolia-client-js-5.51.0'
telde in de diagnose als prijs.
"""
from scraper.diagnose import PRIJS_LOS_RE
from scraper.strategies.render_listing import PRICE_LOOSE_RE, _prijzen


def test_beide_europosities():
    assert _prijzen("€ 24,99") == [24.99]
    assert _prijzen("24,99 €") == [24.99]
    assert _prijzen("Van 17,99 € voor 9,99 €") == [17.99, 9.99]
    assert _prijzen("€5,-") == [5.0]


def test_los_getal_telt_alleen_in_de_losse_ronde():
    assert _prijzen("gewoon 5,99 zonder teken") == []
    assert _prijzen("gewoon 5,99 zonder teken", prijs_los=True) == [5.99]


def test_versienummers_en_maten_zijn_geen_prijs():
    # Zeeman: scriptnaam in de cookiedialoog telde als 'prijsachtig getal'
    assert not PRICE_LOOSE_RE.search("algolia-client-js-5.51.0-W9KHG60MGI")
    assert not PRIJS_LOS_RE.search("algolia-client-js-5.51.0-W9KHG60MGI")
    assert not PRICE_LOOSE_RE.search("Maten 35 - 46")
    # maar een echte prijs aan het zinseinde blijft gewoon staan
    assert PRICE_LOOSE_RE.search("nu 5,99.")
    assert PRIJS_LOS_RE.search("nu 5,99.")
