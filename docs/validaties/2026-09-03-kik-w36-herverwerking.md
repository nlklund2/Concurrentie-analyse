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

## Hermeting (run 33848242144, 4-09 09:20–09:35 NL)

Reguliere weekworkflow met `retailers: kik` op main (commit 5edbd4f, met de
herstelde prijslezer). Kwaliteitspoort: ok — 646 artikelen (was 478; drempel
25, halveringsregel t.o.v. 478). `scrape_runs` id 111.

Weekfoto KiK 2026-08-31 ná de hermeting:

| | vóór | ná |
|---|---:|---:|
| regels | 478 | 646 |
| prijs < €1 | 60 | 0 |
| prijs < €2 | 196 | 95 |
| met was-prijs | 144 (30%) | 328 (51%) |
| met promotekst (stap A) | – | 328 |
| gemiddelde prijs | €3,05 | €4,59 |
| hoogste prijs | €12,99 | €14,99 |

De hermeting logde, vergeleken met de oude lezing van dezelfde week:
new 126, back 74, gone 32, price_up 327, price_down 117, promo_start 130,
promo_end 0 (event-id's 7616–8421). Steekproef: "Hipsters met
dierenmotieven" 1,25 → 4,99 (stukprijs → pakprijs), "Slips" 1,66 → 3,99,
"Super push-up bh + string" 5,99 → 2,99 met was 8,99 (de omnibusprijs
gold als actieprijs). Mediane factor van de price_up-events: 2,0 — het
pak van twee.

## Schoning (4-09, 09:45–10:00 NL)

Verwijderd uit `price_events` (870 regels, integraal in
[`2026-09-04-kik-w36-verwijderde-events.csv`](2026-09-04-kik-w36-verwijderde-events.csv)):

| event | aantal | waarom |
|---|---:|---|
| price_up (herdraai) | 327 | leescorrectie stukprijs → pakprijs |
| price_down (herdraai) | 117 | alle 117 met was-prijs: omnibusprijs gold als actieprijs |
| promo_start (herdraai) | 130 | de actie bestond al; de doorstreepprijs was onleesbaar |
| new (herdraai) | 126 | artikelen die al op kik.nl stonden maar tot 4-09 onleesbaar waren |
| back (herdraai) | 66 | nooit weg geweest: maandag onleesbaar, vrijdag leesbaar |
| gone (maandag, run 97/106) | 66 | de tegenhangers van die 66 'back' |
| gone (herdraai 09:34) | 32 | maandag wél, vrijdag níet op de gecrawlde pagina's: een waarneming bínnen de week, geen W35→W36-mutatie |
| gone / back / new (tweede hermeting 09:53, zie onder) | 3 / 2 / 1 | scrapevariatie tussen twee metingen twintig minuten na elkaar |

Regel: de W36-mutaties van KiK zijn "maandag t.o.v. W35"; de weekfoto en
de statistieken zijn "de stand van vrijdag". Alles wat de hermetingen
onderling of tegen de oude lezing logden valt daarbuiten. Eén uitzondering
blijft staan: 8 `back` van 09:34 waarvan de 'gone' in W35 ligt — die
historie laat ik intact. Alle overige maandag-events blijven staan (new 30,
back 15, promo_start 9, promo_end 55, gone 118 − 66 = 52). De 35
artikelen die tussen maandag en vrijdag van de gecrawlde pagina's
verdwenen staan wél op status 'gone' in `products`, zonder event.

`weekly_stats` KiK 2026-08-31 herberekend: `new_count` = actieve artikelen
met first_seen in deze week mínus de 127 nieuw-leesbare (28 → 25),
`gone_count` uit de resterende gone-events (118 → 52). Prijsstatistieken
komen uit de hermeting zelf:

| doelgroep | producttype | actief vóór → ná | mediaan vóór → ná | sale-aandeel vóór → ná |
|---|---|---:|---:|---:|
| dames | ondergoed | 197 → 257 | 2,99 → 3,99 | 36% → 54% |
| heren | ondergoed | 58 → 59 | 2,75 → 5,99 | 29% → 31% |
| heren | sokken & panty's | 45 → 45 | 0,80 → 2,99 | 22% → 51% |
| meisjes | ondergoed | 74 → 77 | 1,58 → 3,99 | 26% → 34% |
| meisjes | sokken & panty's | 18 → 20 | 0,88 → 1,99 | 17% → 70% |
| jongens | ondergoed | 30 → 28 | 1,50 → 2,99 | 27% → 57% |
| dames | nachtmode | 15 → 19 | 6,99 → 6,99 | 47% → 79% |
| onbekend | ondergoed | 0 → 88 | – → 5,99 | – → 51% |

Stand `price_events` KiK 2026-08-31 ná de schoning: new 30, back 23,
gone 52, promo_start 9, promo_end 55, price_up 0, price_down 0.

## Weekrapport opnieuw gegenereerd

De hermeting van 09:20 committeerde een rapport mét de 840 herdraai-events
(6df1913). Een tweede KiK-run om het rapport na de schoning te
regenereren (run 33849661542, 09:38–09:53) logde zelf weer 6
variatie-events (1 new, 2 back, 3 gone; ook geschoond, zie tabel). Een
poging met `retailers: zeeman` (run 33851032536) bewees dat een meting die
alléén mislukt de hele job laat falen, inclusief de rapportstap. Daarom
heeft de weekworkflow nu een invoer `alleen_rapport`: geen meting, alleen
het rapport opnieuw uit de database — run 33851695953 (10:05 NL), rapport
gecommit als `reports/2026-W36.md` in deze PR.

Het regenereerde rapport (en het dashboard) vergelijkt W36 met W35 — en W35
is nog met de oude lezer gemeten. Voor KiK staan er daardoor in
"signalen van de week" sprongen als "heren / sokken & panty's: mediaan van
€0,80 naar €2,99 (+274%)" en "meisjes / ondergoed: instap van €1,50 naar
€2,99". Dat zijn leescorrecties (stukprijs → pakprijs), geen
prijsbewegingen bij KiK. Eerdere weken zijn niet te herverwerken (er zijn
geen ruwe pagina's bewaard); vanaf W37 vergelijkt de monitor twee weken
met dezelfde lezer en verdwijnen deze signalen vanzelf.

Gevolg voor de presentaties van 3-09: het inzicht "KiK saneert: kwart van
het rek eruit in vier weken" (648 → 478, sale-druk 45% → 30%) berustte op
dezelfde leesfout — naarmate de zomeruitverkoop afliep werden steeds meer
kaarten onleesbaar. Met de herstelde lezer staat KiK in W36 op 646
artikelen met 53% sale. Ook de KiK-prijsindex per stuk verandert: de oude
lezer gaf per ongeluk de stukprijs, de nieuwe de pakprijs zónder
verpakkingsgrootte (KiK zet die niet in de artikelnaam; wel op de kaart
als "(2,50 € / Stuk)" — een verbetering voor een vervolg).

## Wat dit níet onderscheidt

Echte veranderingen tussen maandag en vrijdag zitten in dezelfde events als
de leescorrecties en zijn niet uit elkaar te halen ("Balconette push-up bh
+ string" stond woensdag nog zonder actie op €8,99 en vrijdag op €4,59 met
was €8,99 — mogelijk een echte actiestart). Die zijn met de schoning mee
verwijderd; de weekfoto en de statistieken dragen de vrijdagstand wél. Dat
is dezelfde keuze als bij de Action-herverwerking van 3-09: W36 is voor
KiK "de stand van vrijdag 4-09", de mutaties zijn "maandag t.o.v. W35".

## Omkeren

1. `price_events`: de 832 regels uit de CSV opnieuw invoegen (met hun
   oorspronkelijke id's; de sequence staat erboven).
2. `weekly_articles`: de 646 regels van (kik, 2026-08-31) verwijderen en de
   478 regels uit `2026-09-03-kik-w36-weekfoto-voor-herverwerking.csv`
   invoegen.
3. `weekly_stats` en `products` (prijzen, status, first/last_seen) volgen
   dan niet vanzelf: herberekenen vereist een nieuwe verwerking — bewaar
   daarom liever de huidige stand.

## Verband

- PR #32 — prijslezer KiK (centen achter het €-teken) en stap A promotekst.
- Vergelijk `docs/validaties/2026-09-03-action-valse-prijsverlagingen.md`
  (zelfde werkwijze: herverwerken, dan de herdraai-artefacten schonen).

## Addendum 4-09, 10:17–10:35 NL: verpakkingsgrootte uit de stukprijs

Met de herstelde prijslezer droeg een KiK-kaart de pakprijs, maar zonder
verpakkingsgrootte (KiK zet die niet in de artikelnaam) stond een 3-pack
slips voor €1,99 als één stuk in de per-stuk-index. PR #34 leidt de
pack-grootte nu af uit pakprijs ÷ stukprijs op de kaart ("(0,66 € /
Stuk)"). Na akkoord van de eigenaar is KiK W36 daarom nog één keer
hermeten (run 33852684145, kwaliteitspoort ok): 643 artikelen, waarvan
368 met een pack-grootte (gemiddeld 2,7 stuks).

De hermeting logde 5 waarnemingen binnen de week (1 back, 4 gone; ook
geschoond volgens de regel hierboven, CSV nu 875 regels). Prijs- en
promo-events: 0 — de prijzen zijn identiek aan die van 09:20.
`new_count`/`gone_count` opnieuw herberekend (25 / 52). Stand
`price_events` ongewijzigd: new 30, back 23, gone 52, promo_start 9,
promo_end 55.

Controle: de per-stuk-medianen komen nu vrijwel exact uit op de
stukprijzen die de oude lezer per ongeluk las — het bewijs dat beide
correcties samen kloppen:

| doelgroep | producttype | pakprijs mediaan | per stuk nu | per stuk oude lezing (W36 vóór) | multipack-aandeel |
|---|---|---:|---:|---:|---:|
| heren | ondergoed | 5,99 | 2,50 | 2,75 | 100% |
| heren | sokken & panty's | 2,99 | 0,80 | 0,80 | 100% |
| jongens | ondergoed | 2,99 | 1,50 | 1,50 | 100% |
| jongens | sokken & panty's | 1,99 | 0,66 | 0,66 | 100% |
| meisjes | ondergoed | 3,99 | 1,58 | 1,58 | 99% |
| meisjes | sokken & panty's | 1,99 | 1,00 | 0,88 | 84% |
| dames | ondergoed | 3,99 | 2,99 | 2,99 | 43% |

Het weekrapport is opnieuw gegenereerd met `alleen_rapport` (run
33854006939 (10:33 NL)).
