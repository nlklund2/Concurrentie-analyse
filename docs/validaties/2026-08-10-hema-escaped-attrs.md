# HEMA — groen via escaped-attrs-tegel-JSON

**Datum:** 10-08-2026 (meetronde 5–6 van het routeonderzoek; bewijsprobe met validatierapport 21:51 NL, artifact `validatierapport` 9077251520)
**Besluit:** HEMA loopt volwaardig mee via Firecrawl-rendering met 8 s extra wachttijd plus de escaped-attrs-extractie.

## Wat er is gevonden

Het HEMA-productraster rendert traag: met de standaard-wachttijd (5 s) is het
raster nog leeg. Met **`firecrawl_wait_ms: 8000`** verschijnt het — en dan
blijkt elke producttegel zijn volledige data als **HTML-ge-escapete JSON in
een attribuut** te dragen: `&quot;price&quot;:&quot;8.69&quot;` plus
`masterSKU`/`groupSKU` als stabiele artikelsleutel.

De nieuwe extractie `products_from_escaped_attrs` (in `scraper/jsonscan.py`)
leest die attributen: unescapen, gebalanceerd knippen, dan dezelfde
product-deep-find als elders. Placeholder-waarden ("empty", "null", "-")
tellen niet als maat/kleur.

## Meting (bewijsprobe, 20 categorieën)

Rapportrij uit het validatierapport van 10-08, 21:51 NL:

> 181 | 159 | 100% | 100% | 100% | 100% | 1 | 🟢 ok

- **181 artikelen** uit 20 categorieën, **159 binnen de bodywear-focus**;
- **100% prijsdekking en 100% kleurdekking** — de tegel-JSON is compleet;
- 1 artikel buiten de plausibiliteitsrange (gecontroleerd, geen parsefout).

## Kosten en bewaking

- **±24 Firecrawl-credits per week** (20 categorieën × rendertijd). Dit is
  de duurste bron; bij creditkrapte is `max_categories: 8` (≈10 cr/wk) het
  afschaalpad — besluit ligt bij de eigenaar (beslismoment eind augustus).
- De kanarie (`firecrawl_canary: 5`) kijkt bewust naar de JSON-route en niet
  naar de kaartoogst: een niet-renderend raster levert alleen promoblokken
  (koffie, koekjes) en zou de bron anders ten onrechte groen praten.
- `min_products_expected: 60` als extra slot op de deur.

## Reproduceren

"Validatie bronnen"-workflow → retailer `hema`, limiet 30 (±7 credits) voor
een steekproef, of 200 voor de volle 20 categorieën. Verwacht: ≥60 artikelen,
100% prijsdekking.
