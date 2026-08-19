# Wibra — groen via de open WooCommerce Store-API

**Datum:** 10-08-2026 (meetronde 2 van het routeonderzoek, bewijsrun dezelfde avond)
**Besluit:** Wibra loopt volwaardig mee via `firecrawl_mode: wp_store`; de eerdere productpagina-route (leeg, ±40 credits voor nul resultaat) is vervangen.

## Wat er is gevonden

wibra.nl draait op WordPress/WooCommerce en de **publieke Store-API staat
open**: `/wp-json/wc/store/v1/products?per_page=100&page=N`. Dit is de
JSON-API die de eigen webshop-frontend van Wibra zelf gebruikt — geen
verborgen of robots-verboden endpoint.

## Meting

- Volledige catalogus: **762 producten** in geldige JSON, opgehaald in
  ±8 opvragingen (per_page=100).
- Elk product draagt: naam, prijs in minor units (`currency_minor_unit`,
  dus 599 = €5,99 — de parser deelt door 10^minor_unit), doorstreepprijs
  (`regular_price`), permalink, categorieën én maat/kleur-attributen.
- Prijsplausibiliteit gecontroleerd: alle prijzen in de verwachte €1–€30-
  range, geen minor-units-fouten (geen "€599"-artefacten).
- HTML-entities in namen (`&amp;` e.d.) worden ge-unescaped.
- Ter vergelijking: de productpagina's zelf (meetronde 6, 09-08) droegen
  níéts machineleesbaars — zonder deze API was Wibra rood gebleven.

## Kosten en bewaking

- **±8–9 Firecrawl-credits per week** voor de complete catalogus, mét maten
  en kleuren (de rijkste data van alle acht bronnen).
- De kwaliteitspoort (min. 25 producten, ≥50% van de vorige goedgekeurde
  meting) bewaakt elke weekrun; valt de API ooit dicht (401/403), dan logt
  de strategie dat expliciet en kleurt de bron rood zonder de database te
  vervuilen.

## Reproduceren

"Validatie bronnen"-workflow → retailer `wibra`, limiet 800. Verwacht:
±762 artikelen in ±8 opvragingen, prijzen tussen €1 en €30.
