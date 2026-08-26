"""De van-prijs moet te rijmen zijn met de voor-prijs.

KiK leverde in week 35 tientallen kaarten met "van €199,00 voor €0,66": de
bron rendert de centen apart, waardoor 1,99 als 199 wordt gelezen. Zulke
waarden tellen mee in sale-druk en kortingsdiepte en maken de bron
onbruikbaar — liever geen van-prijs dan een verzonnen van-prijs.
"""
from scraper.models import Product
from scraper.normalize import WAS_MAX_RATIO, plausibele_was_prijs, to_staging_rows


def test_gewone_aanbieding_blijft_staan():
    assert plausibele_was_prijs(7.00, 12.99) == 12.99
    assert plausibele_was_prijs(3.00, 4.00) == 4.00


def test_diepe_maar_denkbare_korting_blijft_staan():
    # 80% korting komt in een opruiming echt voor
    assert plausibele_was_prijs(1.00, 5.00) == 5.00


def test_onmogelijke_verhouding_valt_weg():
    # het KiK-patroon: €199 "was" bij een artikel van €0,66
    assert plausibele_was_prijs(0.66, 199.00) is None
    assert plausibele_was_prijs(2.99, 199.00) is None


def test_grens_ligt_op_de_ratio():
    prijs = 1.00
    assert plausibele_was_prijs(prijs, prijs * WAS_MAX_RATIO) == prijs * WAS_MAX_RATIO
    assert plausibele_was_prijs(prijs, prijs * WAS_MAX_RATIO + 0.01) is None


def test_van_prijs_onder_de_voor_prijs_is_geen_van_prijs():
    assert plausibele_was_prijs(9.99, 4.99) is None
    assert plausibele_was_prijs(9.99, 9.99) is None
    assert plausibele_was_prijs(None, 9.99) is None
    assert plausibele_was_prijs(9.99, None) is None


def test_staging_rij_gebruikt_de_vangrail():
    rows = to_staging_rows("kik", [
        Product(key="a1", title="Sneakersokken", price=0.66, was_price=199.00,
                category_raw="dames/sokken"),
        Product(key="a2", title="Damesslip", price=7.00, was_price=12.99,
                category_raw="dames/ondergoed"),
    ])
    was = {r["product_key"]: r["was_price"] for r in rows}
    assert was == {"a1": None, "a2": 12.99}
