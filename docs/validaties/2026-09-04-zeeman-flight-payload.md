# Zeeman — groen: de producten zaten al die tijd in de Next.js-flight-payload

**Datum:** 04-09-2026 · **Runs:** [33883093620](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/33883093620) (16:19 NL, diagnose op `main`, vóór de fix: bewijs dat GitHub Actions de volledige pagina krijgt) en [33884808717](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/33884808717) (bewijsprobe mét de flight-extractor, limiet 1.500)
**Besluit:** Zeeman gaat op de listing-route met flight-extractor mee in de weekrun. Het eindoordeel van 18-08 en de pagineringsmeting van 19-08 zijn herroepen; de groencriteria uit dat laatste dossier blijven de acceptatie-eis.

## Aanleiding

Zeeman stond sinds W32 rood: elke weekrun leverde 6 tot 15 "artikelen" (Trusted-Shops- en
Cookiebot-badges) tegen een minimum van 25. Het dossier van 18-08 concludeerde dat Zeeman
geautomatiseerde bezoekers op elke laag uitgeklede pagina's serveert. Bij een heronderzoek op
04-09 bleek een gewone thuis-pc voor `nl-nl/dames/ondergoed` een pagina van 710.037 tekens te
krijgen mét 30 producten en de teller "296 artikelen" — en de diagnose van 19-08 op GitHub
Actions had voor `?page=2` 690.115 tekens gemeld. Dat verschil met een echt lege pagina
(130.212 tekens voor een 404) was te groot voor "uitgeklede serving".

## Meting 1 — GitHub Actions krijgt dezelfde pagina als een browser

Run 33883093620, diagnose op `main` (dus nog zónder flight-extractor), 16:19 NL:

| Bron | Pagina | HTML-omvang | Bevinding |
|---|---|---:|---|
| GitHub Actions | `/nl-nl/dames/ondergoed` | 710.037 | "artikelteller op de pagina: «296 artikelen»"; 0 producten via de extractie |
| thuis-pc, curl | `/nl-nl/dames/ondergoed` | 710.037 | identiek; 30 producten in de flight-payload, `total: 296, totalPages: 10` |
| thuis-pc, curl | `/nl-nl/dames/ondergoed?page=2` | 694.295 | 30 producten; 19-08 mat GitHub hiervoor 690.115 |
| thuis-pc, curl | niet-bestaande categorie | 130.212 | HTTP 404: zó ziet een pagina zonder producten eruit |

Het user-agent doet er niet toe: `python-requests/2.32.3`, `Python-urllib`, een expliciete
bot-naam en Chrome krijgen alle vier dezelfde 710.037 tekens met 206 keer `packSize`.
Er is dus geen blokkade en geen aparte serving; de blokkadehypothese van 18-08 vervalt.

## Meting 2 — waar de producten dan wél staan

Zeeman draait Next.js met de App Router. Die zet de serverdata niet in
`<script id="__NEXT_DATA__">` maar in een reeks `<script>self.__next_f.push([1,"…"])</script>`-
blokken: JS-stringliterals die aaneengeplakt de React-serverstroom vormen. Daarin staat per
categoriepagina een `"results":[…]`-lijst van 30 producten, gevolgd door `"total"` en
`"totalPages"`. Per product:

| Veld | Bron | Voorbeeld |
|---|---|---|
| sleutel | `primaryVariant.attributes.variantId` | `124200-1` (artikel + kleur; SKU `124200-1-1` is per maat) |
| naam | `name` | `Boxer - Blauw` |
| prijs | `primaryVariant.price.gross.centAmount` | `469` → € 4,69 |
| van-prijs | `primaryVariant.regularPrice.gross.centAmount` | gelijk aan de prijs bij alle 1.202 artikelen |
| pakgrootte | `packSize` | `2` |
| categorie | `primaryCategory.ancestors` + `name` | `Dames > Ondergoed > Slips` |
| maten | `variants[].attributes.size` | `S, M, L, XL, XXL` |
| voorraad | `availability` | `IN_STOCK` / `OUT_OF_STOCK` |
| labels | `marketingRibbons`, `promotionRibbons` | `Uit onze folder` (46×), `Web-Only` (6×) |
| overig | `ean`, `assortmentType`, `publishAfterDateTime` | |

De drie signalen waar de diagnose tot 04-09 op keek — eurotekens, JSON-LD-producten en
`__NEXT_DATA__` — zijn op Zeeman alle drie echt nul: prijzen worden als losse cijfers
gerenderd (`9` `.` `99`), de JSON-LD bevat alleen WebPage/WebSite/Organization en
`__NEXT_DATA__` bestaat niet in de App Router. De diagnose meldt de flight-payload sinds
04-09 als apart signaal.

## Meting 3 — bewijsprobe met de flight-extractor

Lokaal (thuis-pc, 04-09 ±17:30 NL), `python -m scraper probe --retailer zeeman --limit 1500`
op de nieuwe configuratie (14 vaste seeds, `strategy: listing`):

| Categorieën | Artikelen | Binnen focus | Prijsdekking | Verdacht laag | Kleur | Maten | Promo | Mapping | Requests |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14 | 1.200 | 1.083 | 100% | 0% | 100% | 100% | 4% | 100% | 49 |

- Tellercontrole: 1.261 van 1.264 vermeldingen die de bron zelf telt (100%).
- Doelgroepen: dames 470, kinderen 299, heren 146, baby 68, meisjes 53, jongens 47.
- Promoteksten: 'Uit onze folder' ×46. Geen enkel artikel met een van-prijs boven de prijs.
- Dezelfde probe op GitHub Actions: run 33884808717 (18:00 NL, branch `zeeman-flight-extractor`) — 1.177 artikelen, 1.059 binnen focus, 100% prijs, 100% kleur en maten, 49 verzoeken, tellercontrole 1.238 van 1.264 (98%), advies 'klaar voor de wekelijkse run'. Het verschil met de lokale meting (23 vermeldingen) komt door Zeeman's standaardsortering op populariteit: die verschuift tussen twee opvragingen, waardoor een artikel soms op twee pagina's en soms op geen enkele staat. `?sort=` is per robots.txt uitgesloten, dus dit blijft een bekende variatie van ±2%; de poort laat tot 5% toe.

Een eerste proef leverde 1.230 van 1.265 vermeldingen (97%): de listing-crawl stopte bij een
pagina zonder *globaal* nieuwe sleutels, en Zeeman's lingerie- en ondergoedcategorieën
overlappen. Sinds deze fix telt "nieuw" bij een bron met teller per categorie.

## Groencriteria (dossier 19-08) tegen deze meting

| # | Criterium | Meting 04-09 |
|---|---|---|
| 1 | ≥90% prijsdekking | 100% |
| 2 | ≥95% unieke artikelsleutels | 100% (1.200 sleutels, geen sjabloonherhaling) |
| 3 | artikelaantal binnen ±5% van de paginatelling van de bron | 99,8%; de kwaliteitspoort bewaakt dit nu elke week (`TELLER_MARGE`) |
| 4 | 0 badge-records | 0 (de DOM-kaartscan draait op deze route niet) |

De poort vereist bovendien minimaal 600 artikelen (`min_products_expected`); de bron krijgt pas
na drie opeenvolgende groene weekruns het predicaat structureel groen.

## Wat er is veranderd

- `scraper/jsonscan.py`: `flight_payload`, `flight_listings`, `flight_meta`,
  `products_from_flight`; `products_from_html` roept de flight-route aan naast JSON-LD,
  `__NEXT_DATA__`, JS-state en escaped attrs.
- `scraper/strategies/listing_crawl.py`: de teller van de bron stuurt de paginering
  (geen verzoek voorbij `totalPages`, geen tweede pagina bij `totalPages: 1`) en vult
  `ScrapeResult.coverage` per categorie.
- `scraper/__main__.py`: `_beoordeel` keurt een week af als de oogst meer dan 5% onder de
  eigen telling van de bron blijft; zonder teller verandert er niets.
- `scraper/retailers.yml`: Zeeman op `listing` met 14 seeds, minimum 600, geen verrijking.
- `scraper/diagnose.py`: meldt de flight-payload (omvang, producten, teller) als signaal.
- `tests/test_flight.py`: extractor, paginering op de teller, tellercontrole in de poort.

## Wat níet is gedaan

- De weekhistorie W32–W36 bevat geen Zeeman-producten en is niet te reconstrueren; de ruwe
  artifacts van die runs dragen alleen de badge-records. Zeeman start met W37 (7 september).
  Een handmatige run vóór die datum geeft een vergelijkingsbasis voor 14 september.
- De folder- en multibuy-acties (`/nl-nl/aanbiedingen/…` in de contentsitemap) worden nog
  niet ingelezen; dat is de vervolgstap uit PLAN.md §11.11/11.13.
- Productpagina's dragen nu wél een JSON-LD `Product` met prijs; die route kost 15.744
  verzoeken tegen 49 voor de lijstroute en wordt niet gebruikt.
