# Zeeman — eindoordeel rood: uitgeklede serving op elke laag

**Datum:** 18-08-2026 · **Runs:** [32154461637](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/32154461637) (17:27 NL, sitemap-diagnose + bewijsprobe limiet 40) en [32155622653](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/32155622653) (17:38 NL, render-diagnose productpagina's)
**Besluit:** Zeeman blijft rood; de sitemap_pages-route draait door als gratis wekelijkse hertest met de kwaliteitspoort dicht.

## Aanleiding

Een eerdere diagnose (18-08, ochtend) leek een doorbraak: in de kale HTML van
een productpagina was één product leesbaar. Vóór die claim de config in mocht,
is een bewijsprobe over 40 gespreide pagina's gedraaid — en die ontkrachtte
hem. Dit bestand legt beide metingen vast.

## Meting 1 — de juiste sitemap gevonden

- Route: `robots.txt` → `/sitemap/index.xml` → `nl-nl/sitemap/products.xml`.
- Resultaat: **24.833 canonieke `/nl-nl/product/`-URL's** — echte artikelen.
- Gevonden configfout in de eerdere metingen: `url_filter: "/nl"` matchte ook
  `nl-be`, waardoor de helft van de steekproef door de *Belgische* sitemap
  liep. Gecorrigeerd naar `url_filter: "/nl-nl/product/"` (PR #16).

## Meting 2 — bewijsprobe over 40 gespreide productpagina's

Probe met limiet 40, gelijkmatig over de 24.833 URL's bemonsterd:

- **34 van de 40 pagina's leverden hetzelfde setje van 5 artikelsleutels op.**
  Wat er leesbaar in de kale HTML staat is een klein gedeeld sjabloonblok
  (aanraders), niet het eigen artikel van de pagina.
- Zo'n oogst haalt de kwaliteitspoort (min. 25 producten, ≥50% van de vorige
  goedgekeurde meting) terecht niet.

## Meting 3 — render-diagnose van productpagina's

Voorbeeldpagina "Handdoek Lichtbruin" (run 32155622653):

- Kale HTML: 185.441 tekens, **0 €-tekens**, 14 prijsachtige getallen
  (css/versienummers en de Trusted-Shops-widget).
- Gerenderd in echte browser, cookiemuur weggeklikt: 1.778 tekens zichtbare
  tekst, 90 links, **0× €, 0× "EUR"**; het eerste prijsachtige getal is
  «4.44» in de Trusted-Shops-badge (shopwaardering 4,44/5,00, geen prijs).
- JSON-scripts: alleen kleine `application/ld+json`-blokjes (330–599 tekens,
  geen prijsdata); "producten" uit de gerenderde HTML: 1–2 — wéér het
  gedeelde sjabloonsetje.
- **Geen product-API's onderschept** tijdens het laden.

## De complete meetbalans

| Laag | Uitkomst |
|---|---|
| Categoriepagina's | raster laadt niet, ook niet in echte browser met cookieklik en scrollen |
| API (`/api/*`) | verboden per robots.txt — respecteren we principieel |
| Productpagina's, kale HTML | alleen gedeeld sjabloonsetje (34/40 zelfde 5 sleutels) |
| Productpagina's, gerenderd | eigen prijs verschijnt niet (0 eurotekens) |
| Sitemap | wél volledig en juist (24.833 nl-nl-artikelen) |

**Conclusie:** Zeeman serveert geautomatiseerde bezoekers op elke laag
uitgeklede pagina's. Dat is hun goed recht; binnen onze spelregels (robots.txt
respecteren, €0) is er geen scraper-route. Folder en winkelbezoek zijn het
kanaal voor Zeeman-prijspeiling; de wekelijkse gratis hertest signaleert het
vanzelf als de serving ooit verandert.

## Wat dit oordeel zou omkeren

Zie de groencriteria in `2026-08-19-zeeman-paginering.md` — die gelden voor
élke toekomstige Zeeman-route.
