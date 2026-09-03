# Onderzoek: promotievormen in de dataverzameling

*Datum: 3 september 2026 · status: voorstel, wacht op besluit eigenaar — er is
nog niets van gebouwd.*

## Vraag

> Onderzoek hoe de verschillende soorten van promotie (bv. korting, 2 voor 1,
> etc.) in de dataverzameling kunnen worden meegenomen.

## Samenvatting

Het systeem herkent vandaag **één** promotievorm: de klassieke afprijzing
(doorstreepprijs → actieprijs). Alle andere vormen — "2 voor €5", "1+1
gratis", "2e halve prijs", "-30%"-badges — passeren de meting onherkend,
terwijl juist díe vormen bij discounters het echte prijsbeeld bepalen: een
boxershort van €4,95 in "2 voor €7,50" is effectief €3,75 en dat ziet de
inkoper nu nergens. De promoteksten staan wél in de data die we al ophalen
(kaartteksten, tegel-JSON, API-antwoorden) maar worden weggegooid vóór de
opslag. Voorstel: de ruwe promotekst bewaren, een conservatieve parser die
alleen herkende patronen vertaalt naar een promotype plus effectieve
stukprijs, en een eerlijke dekkingsmeting per bron. Kost geen extra
requests of Firecrawl-credits; wel een kleine databasemigratie.

## 1. Wat het systeem vandaag vastlegt

| Laag | Wat er is | Wat het dekt |
| --- | --- | --- |
| Scraper | `was_price` naast `price` (doorstreepprijs, geplausibiliseerd in `normalize.plausibele_was_prijs`) | alleen was/voor-korting |
| Weekfoto (`weekly_articles`) | `van_prijs` / `voor_prijs` per artikel | idem |
| Weekcijfers (`weekly_stats`) | `sale_share` (aandeel artikelen met was-prijs), `avg_discount_pct` | idem |
| Mutaties (`price_events`) | `promo_start` / `promo_end` zodra een was-prijs verschijnt/verdwijnt | idem |
| Weekrapport & dashboard | sale-druk-signaal bij ±10 pt verschuiving; sale-percentage per bron | idem |

**Structureel onzichtbaar:** multibuy ("2 voor €X", "1+1 gratis", "2+1"),
"2e artikel halve prijs", percentage-badges zonder doorstreepprijs
("-30%"), tijdelijke acties zonder was-prijs, en per-stuk-notaties bij
multipacks (Action schrijft "€ 2,48/st"). Een grep over de codebase
bevestigt: nergens wordt "2 voor", "1+1", "halve prijs" of een
percentagebadge geparset.

## 2. Waar het promosignaal per bron zit

Empirie uit de meetrondes van augustus/september (diagnoses, probes en de
routes die per bron in productie staan):

| Bron | Route | Promosignaal beschikbaar? |
| --- | --- | --- |
| terStal | JSON-LD op productpagina's | was/voor zit in `offers`; multibuy-acties staan alleen als marketingtekst op de pagina — beperkt machineleesbaar. De koninklijke route blijft de eigen PIM/kassa-export. |
| Zeeman | — (bron rood, uitgeklede servering) | niets te vangen zolang de site ons niets serveert; folder blijft het kanaal. |
| Wibra | WooCommerce Store-API | `regular_price`/`sale_price` per artikel (was/voor werkt al); multibuy kent de Store-API niet als dataveld — badgeteksten zitten er niet in. |
| Primark | lijstpagina's (HTTP) | was/voor aanwezig; Primark verkoopt niet online en voert nauwelijks online promoties — verwachte dekking laag, en dat is dan een eerlijk "geen promo". |
| Action | headless browser, DOM-kaarten | **rijkste bron**: de kaarttekst (die we al in handen hebben, tot 400 tekens per kaart) draagt badges en notaties, o.a. "€ 2,48/st" (diagnose 03-09). Action werkt in de winkel veel met multibuy; wat online zichtbaar is, is te vangen. |
| HEMA | Firecrawl, tegel-JSON in attributen | de tegel-JSON draagt prijs en voorraad; badgeteksten ("2e halve prijs" e.d.) staan als losse elementen in dezelfde tegel-HTML die we al binnenhalen — per tegel uit te knippen. |
| C&A | headless browser, DOM-kaarten | kaarttekst beschikbaar; C&A toont %-badges en was/voor in het raster. |
| KiK | headless browser, DOM-kaarten | kaarttekst beschikbaar; KiK voert vooral vaste lage prijzen — verwachte dekking laag. |

Kern: **voor de drie DOM-bronnen (Action, C&A, KiK) en HEMA zit het signaal
al in de opgehaalde bytes.** Er is geen extra request, geen extra credit en
geen nieuwe blokkade-blootstelling nodig — alleen niet meer weggooien wat
we al hebben.

## 3. Voorstel

### Stap A — ruwe promotekst vangen (bewijs eerst)

Nieuw veld `Product.promo_text` (afgekapt op ±120 tekens), gevuld per route:

- **DOM-scan / kaartlezer** (Action, C&A, KiK; ook HEMA-tegels): uit de
  kaarttekst de fragmenten lichten die op een promopatroon lijken
  (regex-familie: `\d+\s*voor\s*€?\d`, `\d\s*\+\s*\d(\s*gratis)?`,
  `2e\s*(artikel\s*)?halve prijs`, `-\s*\d{1,2}\s*%`, `€\s*\d+[.,]\d\d\s*/st`).
- **JSON-routes** (`deep_find_products`): nieuwe alias-lijst `PROMO_KEYS`
  (`promotion`, `promoText`, `badge`, `badges`, `label`, `flag`,
  `offerText`, `actie`) naast de bestaande NAME/PRICE/WAS-lijsten.
- De ruwe tekst gaat mee door staging naar `products` en `weekly_articles`
  — net als kleur/maten: best effort, leeg is eerlijk leeg.

Alleen dit al maakt promoties zichtbaar en controleerbaar in de
artikelverkenner, vóór er ook maar iets geïnterpreteerd wordt.

### Stap B — conservatieve parser naar structuur

`normalize.parse_promo(promo_text, price)` vertaalt **alleen herkende
patronen**; al het andere blijft ruwe tekst zonder interpretatie:

| `promo_type` | Voorbeeldtekst | Effectieve stukprijs (bij minimale afname) |
| --- | --- | --- |
| `bundel` | "2 voor € 7,50" | 7,50 / 2 = € 3,75 |
| `gratis_erbij` | "1+1 gratis", "2+1 gratis" | prijs × n / (n + m) — 1+1: € 2,48 wordt € 1,24 |
| `tweede_halve_prijs` | "2e artikel halve prijs" | prijs × 0,75 |
| `percentage` | "-30%" (zonder was-prijs) | prijs blijft; kortingspct vastgelegd |
| *(bestaand)* | was/voor-prijs | ongewijzigd, blijft de sale_share-basis |

Vastgelegd als `promo_type` + `promo_min_qty` + `effective_price`. Geen
herkend patroon → geen effectieve prijs, nooit gokken. De bestaande
per-stuk-logica (pack_size/unit_price) blijft er los van: "€ 2,48/st" is
een notatie, geen promotie.

### Stap C — opslag, rapport en dashboard

- Migratie: `promo_text`, `promo_type`, `effective_price` op
  `staging_products`, `products`, `weekly_articles`; in `weekly_stats` één
  nieuwe kolom `multibuy_share` naast `sale_share`.
- Weekrapport: sale-druk-sectie telt voortaan óók multibuy mee en noemt de
  opvallendste acties per bron ("Action: 12 multibuy-acties, zwaartepunt
  sokken").
- Dashboard: kolom "actie" in de artikelverkenner (de ruwe promotekst met
  het herkende type); de **prijsindex blijft op kale prijzen** rekenen —
  een aparte, expliciet gelabelde weergave "effectieve actieprijs" kan
  later, pas als de dekking bewezen is.
- Probe/validatierapport: kolom "% promo herkend" per bron, zodat de
  dekking meetbaar is in plaats van beloofd.

### Volgorde en omvang

1. Stap A + probe-meting (1 bewijsprobe per DOM-bron; 0 credits behalve de
   wekelijkse HEMA-run die toch al draait) — daarna weten we per bron de
   échte dekking in plaats van de verwachting hierboven.
2. Stap B + offline tests op de gevangen echte teksten.
3. Stap C (migratie + rapport + dashboard) pas als A/B iets opleveren.

Geschatte omvang: 1 dagdeel bouwen + 1 bewijsronde; €0 extra kosten.

## 4. Wat bewust buiten scope blijft

- **Folder- en winkelacties** die niet online staan (Zeeman volledig;
  Action deels): niet scrapebaar — winkel/folder blijft daarvoor het
  kanaal. De dekking per bron wordt daarom altijd expliciet gerapporteerd.
- **Kassakoppelingen** ("2e artikel aan de kassa"): alleen als de site het
  toont.
- **Historie**: promoteksten zijn niet met terugwerkende kracht te
  herstellen — er is geen opgeslagen HTML van eerdere weken. De meting
  begint bij de eerste week na invoering.

## 5. Besluit aan de eigenaar

Akkoord op stap A (vangen + meten)? Dan volgt de bewijsprobe en daarna pas
het besluit over parser, migratie en dashboardweergave op basis van echte
dekkingscijfers.
