# Validatiedossier — beslissende metingen, reproduceerbaar vastgelegd

Elke bron-beslissing in dit project (een route aanzetten, een bron rood
verklaren) rust op een live meting via de "Validatie bronnen"-workflow op
GitHub Actions. Deze map legt de **beslissende** metingen vast: wat is
gemeten, wanneer, met welke run, wat kwam eruit, en — bij een rood oordeel —
wat het oordeel zou omkeren.

Waarom dit bestaat: conclusies als "Zeeman serveert ons uitgeklede pagina's"
zijn alleen wat waard als een ander ze kan narekenen — en die conclusie bleek
op 04-09 inderdaad onjuist (zie het dossier van die datum). Een externe review
(19-08-2026) wees er terecht op dat de bewijsvoering tot dan toe alleen in
gespreksverslagen leefde. Vanaf nu geldt: **een bron-eindoordeel krijgt een
bestand in deze map**, met run-id's die naar de ruwe logs op GitHub Actions
verwijzen.

## Herhalen van een meting

Alle metingen lopen via `workflow_dispatch` op `validatie.yml`
("Validatie bronnen"), omdat het netwerk naar de retailers vanuit
ontwikkelomgevingen dicht is. Twee invoervelden doen het werk:

- **retailer + limiet** → draait `python -m scraper probe` (bewijsprobe met
  dekkingstabel);
- **diagnose_urls** → draait `python -m scraper diagnose` per URL
  (kale HTML + gerenderde pagina + onderschepte API's); met `fc:`-prefix
  loopt de opvraging via Firecrawl.

Run-id's hieronder zijn te openen als
`https://github.com/nlklund2/Concurrentie-analyse/actions/runs/<id>`.

## Inhoud

| Datum | Bestand | Besluit |
|---|---|---|
| 10-08-2026 | `2026-08-10-wibra-store-api.md` | Wibra groen via WooCommerce Store-API |
| 10-08-2026 | `2026-08-10-hema-escaped-attrs.md` | HEMA groen via escaped-attrs-tegel-JSON |
| 18-08-2026 | `2026-08-18-zeeman-eindoordeel.md` | Zeeman rood: uitgeklede serving op elke laag — **herroepen 04-09** |
| 19-08-2026 | `2026-08-19-zeeman-paginering.md` | `?page=`-route (externe suggestie) gemeten en verworpen — **herroepen 04-09**; de groencriteria blijven gelden |
| 04-09-2026 | `2026-09-04-zeeman-flight-payload.md` | Zeeman groen: producten zaten al die tijd in de Next.js-flight-payload; de extractie las het formaat niet |
