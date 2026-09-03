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


def test_maat_voor_euroteken_is_geen_prijs():
    """Action-maillots (W36): de kaart schrijft 'Maten 40 - 42 € 0,84/st'.
    De kale-integer-variant van getal-eerst las de maat '42 €' als prijs én
    at het €-teken op, zodat de echte prijs erna wegviel — twintig panty's
    kregen hun maat (42/46/50, kinderlengte 170) als prijs in de weekfoto."""
    assert _prijzen("Maten 40 - 42 € 0,84/st") == [0.84]
    assert _prijzen("Maten 164 - 170 € 1,70/st") == [1.70]
    # kale integer vóór een € blijft bewust ongelezen (nooit een NL-prijsvorm)
    assert _prijzen("42 €") == []


def test_per_stuk_notatie_is_geen_tweede_verkoopprijs():
    """Action (03-09): kaarten schrijven '€ 2,48/st'. Naast een pakprijs is dat
    een omgerekende stukprijs — zonder filter zou min() de stukprijs als
    actieprijs nemen en de echte verkoopprijs als doorstreepprijs opvoeren."""
    assert _prijzen("€ 4,95 € 2,48/st") == [4.95]
    assert _prijzen("€ 4,95 (€ 2,48/stuk)") == [4.95]
    assert _prijzen("€ 1,24/paar € 2,48") == [2.48]
    # los verkocht artikel: de /st-prijs is gewoon dé verkoopprijs
    assert _prijzen("€ 2,48/st") == [2.48]
    # echte afprijzing houdt twee prijzen (was/voor blijft werken)
    assert _prijzen("van € 14,99 voor € 9,99") == [14.99, 9.99]


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
