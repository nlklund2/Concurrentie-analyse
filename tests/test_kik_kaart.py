"""KiK via Firecrawl (sinds W46): de kaart zet de prijs als
'€<span>5</span><sup>99</sup>'. De statische kaartlezer plakte tekstdelen met
een spatie aan elkaar ('€ 5 99') en las €5,00. Validatie 12-11: 'Pyjama met
beren en egels' €5,00 tegen €5,99 in de database (W45)."""
from scraper.strategies.render_listing import cards_from_html

# Ingekort uit de Firecrawl-dump van /c/meisjes/meisjes-babys-nachtkleding (12-11).
KIK_TEGELS = """<html><body><div class="grid">
<div data-testid="product_card"><div class="flex h-full flex-col">
 <div class="relative"><a href="https://www.kik.nl/p/pyjama-met-beren-en-egels-2-delige-set-creme-1208/1226230" class="block"><img alt="Pyjama met beren en egels" src="a.webp"></a>
  <button aria-label="Toevoegen aan verlanglijstje"><svg><path d="M19.664 4.99c-2.64"></path></svg></button></div>
 <a href="https://www.kik.nl/p/pyjama-met-beren-en-egels-2-delige-set-creme-1208/1226230" aria-label="Pyjama met beren en egels">Pyjama met beren en egels</a>
 <p>2 delige set</p>
 <div><a href="https://www.kik.nl/p/pyjama-met-beren-en-egels-2-delige-set-creme-1208/1226230" aria-label="Pyjama met beren en egels"><div><div><p>€<span>5</span><sup>99</sup></p></div></div></a></div>
</div></div>
<div data-testid="product_card"><div class="flex h-full flex-col">
 <div class="relative"><a href="https://www.kik.nl/p/pyjama-met-berenmotief-set-van-2-stuks-offwhite-1215/1231357" class="block"><img alt="Pyjama met berenmotief" src="b.webp"></a></div>
 <a href="https://www.kik.nl/p/pyjama-met-berenmotief-set-van-2-stuks-offwhite-1215/1231357" aria-label="Pyjama met berenmotief">Pyjama met berenmotief</a>
 <div><a href="https://www.kik.nl/p/pyjama-met-berenmotief-set-van-2-stuks-offwhite-1215/1231357" aria-label="Pyjama met berenmotief"><div><div><p>€<span>12</span><sup>99</sup></p></div></div></a></div>
</div></div>
</div></body></html>"""


def test_kik_centen_in_superscript():
    prijzen = {p.title: p.price for p in cards_from_html(
        KIK_TEGELS, "https://www.kik.nl/c/meisjes/meisjes-babys-nachtkleding")}
    assert prijzen == {"Pyjama met beren en egels": 5.99,
                       "Pyjama met berenmotief": 12.99}


def test_gewone_prijs_met_spatie_blijft_heel():
    """Elders blijft '€ 3,99' (los tekstknooppunt na het €-teken) gewoon €3,99."""
    html = ('<div><a href="https://www.hema.nl/p/slip">dames slip</a>'
            '<span>€</span> <span>3,99</span></div>')
    assert [p.price for p in cards_from_html(html, "https://www.hema.nl/c")] == [3.99]
