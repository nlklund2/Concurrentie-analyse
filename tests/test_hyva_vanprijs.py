"""terStal (Hyvä/Magento): de normale prijs staat alleen in het Alpine-prijsblok,
niet in JSON-LD. Fragment ingekort uit de productpagina van 25-11 (−30%-actie)."""
from scraper.jsonscan import regular_price_hyva

ACTIE = """<div role="group" aria-label="Price">
 <div x-data="initPrice222303()" x-bind="eventListeners" class="price-box">
  <div x-show="!activeProductsPriceData &amp;&amp; !isPriceHidden()">
   <div class="old-price"><span id="product-price-222303" class="price-wrapper">
    <span class="price" x-html="((7.99 + getCustomOptionPrice())).toFixed(2)">7.99</span></span></div>
   <div class="final-price" itemprop="offers" itemscope="" itemtype="https://schema.org/Offer">
    <span id="product-price-222303" class="price-wrapper">
    <span class="price" x-html="getFormattedFinalPrice()">5.59</span></span></div>
  </div>
 </div>
</div>"""

ZONDER_ACTIE = ACTIE.replace("7.99", "5.59")


def test_normale_prijs_uit_prijsblok():
    assert regular_price_hyva(ACTIE) == 7.99


def test_zonder_actie_gelijk_aan_actieprijs():
    assert regular_price_hyva(ZONDER_ACTIE) == 5.59


def test_geen_prijsblok_geen_vanprijs():
    """Aanbevelingen gebruiken hetzelfde sjabloon zonder initPrice-blok: negeren."""
    los = '<span x-html="((12.99 + getCustomOptionPrice())).toFixed(2)">12.99</span>'
    assert regular_price_hyva(los) is None
