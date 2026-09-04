# Herverwerking KiK week 2026-08-31 na herstel van de prijsleesfout

*Datum ingreep: 4 september 2026 · uitgevoerd door Claude na akkoord van de
eigenaar ("akkoord op optie 1, herverwerk W36 voor KiK").*

## Aanleiding

KiK rendert de prijs op de kaart als `€` + `8` + `<sup>99</sup>`; de
tekstlezer van de scraper plakte dat aaneen tot "€899". Gevolgen tot en
met de weekrun van maandag 31-08 (runs 97 en 106):

- multipacks kregen de omgerekende stukprijs uit "(0,66 € / Stuk)" als
  prijs — W36 telde 60 KiK-artikelen onder €1 en 196 onder €2;
- losse artikelen zonder stukprijsregel ("Hemdje … €499") vielen op het
  >200-filter weg en stonden helemaal niet in de weekfoto;
- "€199" gold als honderdnegenennegentig euro (vangrail van PR #23 hield
  dat sinds 26-08 uit de was-prijs).

Sinds PR #32 (3-09, commit 5edbd4f) leest de scraper drie of vier cijfers
direct achter het €-teken als euro's + centen. Diagnose 33776551152:
144 van 144 kaarten gelezen (was 44), probe 33776939676: 0% verdacht lage
prijzen.

Zonder herverwerking zou de correctie maandag 8-09 in W37 landen als een
golf `price_up`-events (0,66 → 1,99) en zou W36→W37 appels met peren
vergelijken. Daarom is W36 voor KiK opnieuw gemeten via de reguliere
weekworkflow (kwaliteitspoort `_beoordeel` inbegrepen), en zijn de
events die die hermeting tegen de oude lezing logde als leescorrectie
verwijderd.

## Stand vóór de herverwerking (vastgelegd 4-09, 09:15 NL)

- `weekly_articles` KiK 2026-08-31: 478 regels, 60 met prijs < €1,
  196 < €2, 144 met was-prijs. Integrale kopie:
  [`2026-09-03-kik-w36-weekfoto-voor-herverwerking.csv`](2026-09-03-kik-w36-weekfoto-voor-herverwerking.csv).
- `price_events` KiK 2026-08-31 (maandag, runs 97 en 106): new 30,
  back 15, gone 118, promo_start 9, promo_end 55 — hoogste event-id vóór
  de herverwerking: 7595. Deze events blijven staan.
- `weekly_stats` KiK 2026-08-31 (selectie):

| doelgroep | producttype | actief | mediaan | sale-aandeel | mediaan/stuk |
|---|---|---:|---:|---:|---:|
| dames | ondergoed | 197 | 2,99 | 36% | 2,99 |
| heren | ondergoed | 58 | 2,75 | 29% | 2,75 |
| heren | sokken & panty's | 45 | 0,80 | 22% | 0,80 |
| meisjes | ondergoed | 74 | 1,58 | 26% | 1,58 |
| meisjes | sokken & panty's | 18 | 0,88 | 17% | 0,88 |
| jongens | ondergoed | 30 | 1,50 | 27% | 1,50 |
| jongens | sokken & panty's | 10 | 0,66 | 10% | 0,66 |
| dames | nachtmode | 15 | 6,99 | 47% | 6,99 |
| baby | sokken & panty's | 4 | 0,66 | 0% | 0,66 |
