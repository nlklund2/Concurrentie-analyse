"""Dekkingsregels: de scraper mag geen doelgroep of artikel wegkappen zonder
dat op te merken. Beide gevallen hieronder kostten in week 32 echte data."""
from scraper.discover import spread_by_audience
from scraper.models import Product
from scraper.strategies.sitemap_pages import _eigen_product


def test_spread_by_audience_niet_alleen_dames():
    """KiK-scenario: 500 categorieën, alfabetisch geclusterd. Zonder spreiding
    zijn de eerste 20 uitsluitend dames en telt de bron nul heren."""
    urls = ([f"https://x.nl/c/dames/ondergoed-{i}" for i in range(30)]
            + [f"https://x.nl/c/heren/ondergoed-{i}" for i in range(30)]
            + [f"https://x.nl/c/kinder/ondergoed-{i}" for i in range(30)])
    gekozen = spread_by_audience(urls, 12)
    assert len(gekozen) == 12
    for woord in ("dames", "heren", "kinder"):
        assert sum(1 for u in gekozen if woord in u) == 4
    # volgorde bínnen een doelgroep blijft de oorspronkelijke rangschikking
    dames = [u for u in gekozen if "dames" in u]
    assert dames == [f"https://x.nl/c/dames/ondergoed-{i}" for i in range(4)]


def test_spread_by_audience_randgevallen():
    urls = ["https://x.nl/a", "https://x.nl/b"]
    assert spread_by_audience(urls, 5) == urls   # onder de cap: ongemoeid
    assert spread_by_audience(urls, 0) == []
    # zonder doelgroepwoord blijft het gewoon de eerste n
    assert spread_by_audience(urls, 1) == ["https://x.nl/a"]


def test_eigen_product_kiest_het_artikel_van_de_pagina():
    """Zeeman-scenario: de productpagina bevat ook een aanraderblok. Zonder
    URL-match won de aanrader, en vielen 2.478 producten samen tot 15."""
    pagina = "https://www.zeeman.com/nl-nl/dames/ondergoed/slip-3-pack-123"
    found = [
        Product(key="promo-1", title="Aanrader met een hele lange titel",
                url="https://www.zeeman.com/nl-nl/acties/zomerdeal", price=9.99),
        Product(key="sku-123", title="Slip 3-pack", url=pagina, price=3.99),
    ]
    assert _eigen_product(found, pagina).key == "sku-123"


def test_eigen_product_valt_terug_zonder_url_match():
    pagina = "https://voorbeeld.nl/p/iets"
    found = [Product(key="a", title="Kort", price=None),
             Product(key="b", title="Wel een prijs", price=4.99)]
    assert _eigen_product(found, pagina).key == "b"
    assert _eigen_product([], pagina) is None


def test_eigen_product_kiest_de_juiste_kleurvariant():
    """Zeeman zet elke kleur als eigen pagina neer maar toont in alle varianten
    dezelfde productlijst. Zonder naamgelijkenis won steeds dezelfde variant en
    vielen 60 pagina's samen tot 4 artikelen."""
    varianten = [
        Product(key="s-paars", title="Amely Slip - Paars", price=5.99),
        Product(key="s-rood", title="Amely Slip - Rood", price=5.99),
        Product(key="s-zwart", title="Amely Slip - Zwart", price=5.99),
    ]
    basis = "https://www.zeeman.com/nl-nl/dames/ondergoed/"
    for kleur, sleutel in (("rood", "s-rood"), ("zwart", "s-zwart"), ("paars", "s-paars")):
        gekozen = _eigen_product(varianten, f"{basis}amely-slip-{kleur}-98765")
        assert gekozen.key == sleutel, kleur


def test_eigen_product_negeert_zwakke_naamgelijkenis():
    """Een aanrader die toevallig één woord deelt mag niet winnen."""
    found = [Product(key="promo", title="Zomerdeal handdoeken set", price=9.99)]
    gekozen = _eigen_product(found, "https://x.nl/dames/ondergoed/amely-slip-rood-123")
    assert gekozen.key == "promo"   # valt terug op de heuristiek, niet op de slug


def test_kleurfilterpaden_tellen_niet_als_categorie():
    """KiK biedt elke categorie ook per kleur aan (/c_wit); die crawlen kost
    budget en levert dezelfde artikelen op."""
    from scraper.discover import split_product_category_urls
    _, cats = split_product_category_urls([
        "https://www.kik.nl/c/dames/dameskleding-ondergoed",
        "https://www.kik.nl/c/dames/dameskleding-ondergoed/c_wit",
    ])
    assert cats == ["https://www.kik.nl/c/dames/dameskleding-ondergoed"]
