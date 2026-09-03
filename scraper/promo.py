"""Promotievormen — stap A: de ruwe promotekst vangen, níets interpreteren.

Tot W36 kende het systeem één promotievorm: de doorstreepprijs (was_price).
Multibuy ('2 voor € 7,50', '1+1 gratis', '2e halve prijs') en %-badges
stonden wél op de kaarten die we al ophalen, maar werden weggegooid vóór de
opslag. Deze module licht zulke fragmenten uit vrije tekst — kaarttekst,
tegel-HTML, badge-velden in JSON — en levert ze als één korte, ruwe string
(promo_text). Wat het ís (bundel, gratis erbij, percentage) beslist stap B
pas, op basis van de dekkingsmeting die dit veld mogelijk maakt.

Bewust níet als promo geteld: per-stuk-notaties ('€ 2,48/st' is een
prijsvorm), 'nieuw'-badges, en de was/voor-prijs zelf (die is al was_price).
Zie docs/promotievormen-onderzoek.md.
"""
from __future__ import annotations

import re

MAX_LEN = 120

_MATERIAAL = r"(?!\s*(?:katoen|elastaan|elasthan|polyester|polyamide|viscose|wol|spandex|modal))"

_PATRONEN = [
    # '2 voor € 7,50', '3 voor 10', '2 voor de prijs van 1'
    # (geen optionele '€' achter het bedrag: die zou het €-teken van de
    # vólgende prijs op de kaart opslokken)
    # De teller is een telwoord (1-12), nooit het decimaaldeel of de prijs
    # ervóór: 'van € 14,99 voor € 9,99' is was/voor, geen '99 voor € 9,99'.
    r"(?<![\d,.€])(?<!€ )\b(?:[1-9]|1[0-2])\s*voor\s*(?:€\s*)?\d{1,3}(?:[.,]\d{2})?(?:\s*euro)?(?![\d,.])"
    r"|\b\d\s*voor\s*de\s*prijs\s*van\s*\d\b",
    # '3 halen 2 betalen'
    r"\b\d\s*halen,?\s*\d\s*betalen\b",
    # '1+1 gratis', '2+1', '1 + 1 gratis'
    r"\b\d\s*\+\s*\d(?:\s*gratis)?\b",
    # '2e halve prijs', '2e artikel halve prijs', 'tweede voor de halve prijs'
    r"\b(?:2e|tweede)\s*(?:artikel\s*)?(?:voor\s*de\s*)?halve\s*prijs\b",
    # '2e artikel 50%', '2e voor 50%'
    r"\b(?:2e|tweede)\s*(?:artikel\s*)?(?:voor\s*)?\d{1,2}\s*%",
    # '-30%' (geen '95%-5%' of '- 5% elastaan'), '30% korting', 'tot 50% korting'
    r"(?<![\d%])-\s*\d{1,2}\s*%" + _MATERIAAL + r"|\b(?:tot\s*)?\d{1,2}\s*%\s*korting\b",
    # ondubbelzinnige actiebadges ('sale' en 'actie' zijn te generiek: navigatie)
    r"\b(?:aanbieding|actieprijs|opruiming|uitverkoop|op=op)\b",
]
PROMO_RE = re.compile("|".join(_PATRONEN), re.I)


def promo_fragmenten(text: str | None) -> str:
    """Alle herkende promofragmenten uit een tekst, ontdubbeld, ' · '-gescheiden,
    afgekapt op MAX_LEN. Leeg als er niets promotie-achtigs in staat."""
    if not text:
        return ""
    schoon = re.sub(r"\s+", " ", str(text))
    gezien: list[str] = []
    for m in PROMO_RE.finditer(schoon):
        frag = re.sub(r"\s+", " ", m.group(0)).strip(" ,.;:")
        if frag and frag.lower() not in {g.lower() for g in gezien}:
            gezien.append(frag)
    return " · ".join(gezien)[:MAX_LEN]


def promo_uit_html(fragment: str | None) -> str:
    """Zelfde, maar op een stuk HTML: tags eruit, entiteiten terug naar tekst."""
    if not fragment:
        return ""
    import html as html_mod
    tekst = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", fragment, flags=re.S | re.I)
    tekst = re.sub(r"<[^>]+>", " ", tekst)
    return promo_fragmenten(html_mod.unescape(tekst))
