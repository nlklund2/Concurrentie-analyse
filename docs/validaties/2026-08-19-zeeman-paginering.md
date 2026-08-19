# Zeeman — `?page=`-paginering getoetst en verworpen

**Datum:** 19-08-2026 · **Run:** [32237551323](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/32237551323) (11:27 NL, diagnose op main; een eerdere poging, run 32235948614, is geannuleerd wegens een hangende Playwright-download)
**Besluit:** paginering via `?page=` is géén route om Zeeman-data binnen te halen; het eindoordeel van 18-08 blijft staan.

## Aanleiding

Een externe review (Codex, 19-08) beoordeelde de categoriepagina's-met-
`?page=`-route als kansrijk (7,5/10), met als redenering dat de paginering
niet in robots.txt verboden is en mogelijk een andere servering krijgt dan de
kale categoriepagina. Dat is een meetbare claim, dus gemeten.

## Meting

Diagnose van twee gepagineerde categoriepagina's, kaal én gerenderd
(echte browser, cookiemuur automatisch weggeklikt):

### `https://www.zeeman.com/nl-nl/dames/ondergoed?page=2`

- Kale HTML: HTTP 200, 690.115 tekens, **0 €-tekens**, 40 prijsachtige
  getallen, **0 producten** via de extractieroutes. De "prijsachtige"
  contexten: een css-chunk ("10.39iq") en de Trusted-Shops-widget
  («4.44» = shopwaardering 4,44/5,00).
- Gerenderd: titel "Goedkoop dames ondergoed kopen? | Zeeman", 9.034 tekens
  zichtbare tekst, 120 links, **0× €**, **0 producten**; het eerste
  prijsachtige getal zit in de Trusted-Shops-badge (geen omsluitende link).
- Onderschepte JSON tijdens het laden: alleen sentry, consentcdn.cookiebot,
  convertexperiments, `zeeman.com/api/language` (country/locale) en
  ppcprotect — **geen enkele product-API**.

### `https://www.zeeman.com/nl-nl/heren/ondergoed?page=1`

- Kale HTML: HTTP 200, 643.936 tekens, **0 €-tekens**, 47 prijsachtige
  getallen, **0 producten**.
- Gerenderd: titel "Goedkoop heren ondergoed kopen | Zeeman", 4.629 tekens
  tekst, 121 links, **0 producten**; zelfde JSON-antwoorden, geen product-API.

## Conclusie

`?page=`-pagina's krijgen exact dezelfde uitgeklede serving als alle andere
lagen: het productraster hydrateert niet voor geautomatiseerde bezoekers, ook
niet in een echte browser na de cookieklik. De paginering staat inderdaad
niet in robots.txt — maar dat is irrelevant zolang de server ons de producten
simpelweg niet stuurt. De claim is voor onze toegangspositie weerlegd.

Voor de volledigheid: een gewone bezoeker ziet deze pagina's mét producten.
Het verschil zit in hoe Zeeman datacenter-/geautomatiseerd verkeer bedient,
niet in onze techniek. De enige realistische structurele route is de
officiële **TradeTracker-productfeed** (affiliateprogramma) — een
eigenaarsactie: aanvraag plus schriftelijke toestemming voor gebruik in
concurrentieonderzoek.

## Groencriteria — wat Zeeman weer groen zou maken

Overgenomen uit de externe review als acceptatie-eis voor élke toekomstige
Zeeman-route (feed, gewijzigde serving, wat dan ook). Pas als **drie
opeenvolgende weekruns** aan alle vier voldoen, mag de bron groen:

1. ≥90% prijsdekking op de opgehaalde artikelen;
2. ≥95% unieke artikelsleutels (geen gedeeld-sjabloon-herhaling);
3. artikelaantal binnen ±5% van de paginatelling van de bron zelf;
4. 0 badge-records (Trusted-Shops/Cookiebot-artefacten) in de oogst.

De kwaliteitspoort (`_beoordeel` in `scraper/__main__.py`) blijft daarnaast
gewoon van kracht.
