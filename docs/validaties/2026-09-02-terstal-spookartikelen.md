# terStal-spookartikelen: historische weekfoto's geschoond (2026-09-02)

## Wat er speelde

De eigenaar stelde vast dat terStal-artikelen zonder prijs zonder uitzondering
niet meer actief op de site staan. Livediagnose (run 33625676924) bevestigde het
mechanisme: terstal.nl (Magento) laat verlopen artikelen als pagina in de
sitemap staan met `availability: OutOfStock` en `price: 0.00`. De scraper telt
zulke pagina's sinds PR #25 niet meer mee, en week 2026-08-31 is herverwerkt
(443 actieve artikelen, 100% prijsdekking).

Voor de weken 2026-08-03 t/m 2026-08-24 kon dat niet opnieuw gemeten worden:
het voorraadsignaal werd toen nog niet gelezen én de oude site (vóór de
vernieuwing) bestaat niet meer. Op verzoek van de eigenaar zijn die weken
daarom geschoond op basis van het best beschikbare criterium.

## Criterium

Een artikel geldt als spookartikel als het in **geen enkele** van de vijf
weekfoto's ooit een prijs droeg. Onderbouwing: op de vernieuwde site (week
2026-08-31) is elke actieve terStal-pagina 100% prijsleesbaar, dus een artikel
dat ook dáár nooit met prijs verscheen, was de hele periode al verlopen.
Artikelen die óóit een prijs droegen blijven staan — ook in weken waarin hun
prijs onleesbaar was (op de oude site was "geen prijs" niet hetzelfde als
"niet te koop"; bewezen met de boxershorts-diagnose van 09-08).

Dit is de best mogelijke benadering, geen meting: een artikel dat actief was
op de oude site met onleesbare prijs én vóór de sitevernieuwing uit het
assortiment ging, is met dit criterium niet te onderscheiden van een spook.

## Ingreep (2026-09-02, rechtstreeks in Supabase)

- `weekly_articles`: 1.034 regels verwijderd (281 unieke artikelen):
  251 (wk 2026-08-03), 251 (08-10), 251 (08-17), 281 (08-24).
  Geen van deze regels droeg een prijs of van-prijs.
- `weekly_stats` (terstal, die vier weken): 64 groepsregels herberekend uit de
  geschoonde weekfoto's, 4 groepen leeggemaakt (bestonden alleen uit spoken).
  De herberekeningsformules zijn vooraf geverifieerd tegen week 2026-08-31:
  16 groepen, 0 afwijkingen op alle 14 kolommen. `gone_count` en
  `price_events` zijn bewust niet aangeraakt (mutatiehistorie = zoals gemeten).

## Effect

terStal actief per week: 716 / 716 / 723 / 759 / 443 → **465 / 465 / 472 / 478 / 443**.
Dames/ondergoed bijvoorbeeld: 142 / 142 / 149 / 147 / 133 (was 201-199 met spoken).
Prijs-, sale- en per-stuk-cijfers waren al zuiver (die rekenen alleen over
artikelen mét prijs) en zijn niet wezenlijk veranderd.

## Omkeerbaarheid

Alle verwijderde regels staan integraal in
[`2026-09-02-terstal-spookartikelen.csv`](2026-09-02-terstal-spookartikelen.csv)
(alle kolommen van `weekly_articles`). Terugzetten = de CSV importeren en de
statistiekherberekening uit dit dossier herhalen zonder het spookfilter.
De ruwe metingen van elke run blijven daarnaast 60 dagen beschikbaar als
GitHub Actions-artifact.

## Definitieve route

Een export uit terStal's eigen PIM/kassasysteem (artikelnummer + actief-periode)
blijft de enige manier om de historie exact te maken — en maakt de eigen
referentielijn structureel onafhankelijk van site-eigenaardigheden.
