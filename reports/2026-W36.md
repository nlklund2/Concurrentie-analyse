# Weekrapport concurrentiemonitor — week 36, 2026

*Peildatum: maandag 31-08-2026. Cijfers betreffen het online assortiment (trend-indicatie, geen winkeltelling).*

*Scope: ondergoedmode — ondergoed, nachtmode, sokken & panty's.*

## 1. Gezondheid van de bronnen

| Bron | Strategie | Deze run | In database | t.o.v. vorige week | Status |
|---|---|---:|---:|---:|---|
| Action | render | 24 | 24 | +0% | 🟢 ok — {"new": 0, "back": 0, "gone": 0, "price_up": 0, "products": 24, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| C&A | render | 607 | 607 | +7% | 🟢 ok — {"new": 1, "back": 6, "gone": 5, "price_up": 0, "products": 607, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| HEMA | firecrawl | 137 | 137 | +2% | 🟢 ok — {"new": 0, "back": 0, "gone": 1, "price_up": 0, "products": 137, "promo_end": 0, "price_down": 0, "promo_start": 0} · 24 Firecrawl-credits |
| KiK | render | 478 | 478 | -13% | 🟢 ok — {"new": 3, "back": 5, "gone": 6, "price_up": 0, "products": 478, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| Primark | listing | 1111 | 1111 | +8% | 🟢 ok — {"new": 57, "back": 16, "gone": 48, "price_up": 0, "products": 1111, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| terStal familiemode | sitemap_pages | 443 | 443 | -42% | 🟢 ok — {"new": 0, "back": 0, "gone": 324, "price_up": 0, "products": 443, "promo_end": 0, "price_down": 16, "promo_start": 0} |
| Wibra | firecrawl | 125 | 125 | -1% | 🟢 ok — {"new": 0, "back": 0, "gone": 0, "price_up": 0, "products": 125, "promo_end": 0, "price_down": 0, "promo_start": 0} · 12 Firecrawl-credits |
| Zeeman | sitemap_pages | 15 | – | – | 🔴 fout — slechts 15 artikelen (minimum 25); bron gewijzigd? |

> 🟠/🔴: cijfers van die bron deze week niet gebruiken voor besluiten.
> *Deze run* is wat de scraper deze week ophaalde, *in database* de laatst verwerkte stand. Lopen die uiteen, dan heeft de kwaliteitspoort deze week tegengehouden en staat er nog oudere data.

## 2. Signalen van de week

- **KiK** · onbekend / ondergoed: saneert van 59 naar 0 artikelen (-100%)
- **HEMA** · jongens / nachtmode: instapniveau omhoog van €9,00 naar €14,99 (+67%)
- **terStal familiemode** · meisjes / nachtmode: saneert van 54 naar 9 artikelen (-83%)
- **terStal familiemode** · dames / nachtmode: saneert van 123 naar 29 artikelen (-76%)
- **HEMA** · heren / nachtmode: mediaanprijs omlaag van €21,99 naar €10,00 (-55%)
- **C&A** · meisjes / ondergoed: instapniveau omhoog van €7,49 naar €11,49 (+53%)
- **HEMA** · heren / nachtmode: instapniveau omlaag van €20,00 naar €10,00 (-50%)
- **KiK** · jongens / sokken & panty's: sale-druk daalt van 69% naar 10%
- **KiK** · meisjes / sokken & panty's: sale-druk daalt van 75% naar 17%
- **terStal familiemode** · dames / ondergoed: saneert van 199 naar 133 artikelen (-33%)
- **terStal familiemode** · meisjes / sokken & panty's: saneert van 62 naar 32 artikelen (-48%)
- **HEMA** · dames / ondergoed: mediaanprijs omlaag van €16,49 naar €10,64 (-35%)
- **C&A** · baby / sokken & panty's: mediaanprijs omhoog van €7,49 naar €9,99 (+33%)
- **HEMA** · meisjes / sokken & panty's: breidt uit van 10 naar 16 artikelen (+60%)
- **terStal familiemode** · onbekend / sokken & panty's: saneert van 28 naar 14 artikelen (-50%)

## 3. Grootste prijsverlagingen deze week

| Bron | Artikel | Van | Naar | Verschil |
|---|---|---:|---:|---:|
| terStal familiemode | pyjama set rib | €24,99 | €7,49 | -70% |
| terStal familiemode | pyjama set print + uni | €19,99 | €9,99 | -50% |
| terStal familiemode | pyjama set met print | €24,99 | €12,49 | -50% |
| terStal familiemode | pyjama set met print | €24,99 | €12,49 | -50% |
| terStal familiemode | pyjama set rib | €24,99 | €12,49 | -50% |
| HEMA | nijntje baby shortama  beige | €9,49 | €3,00 | -68% |
| HEMA | herenpyjama Jesse jersey strepen donkerblauw | €28,99 | €10,00 | -66% |
| HEMA | heren pyjamabroek Pepijn regular fit poplin strepen gebroken | €21,99 | €10,00 | -55% |
| HEMA | heren pyjamabroek regular fit ruit donkerblauw | €21,99 | €10,00 | -55% |
| HEMA | heren pyjamabroek Pepijn regular fit poplin middenblauw | €21,99 | €10,00 | -55% |
| Wibra | Jongens sokken 3 paar maat 19/22 – 35/38 | €3,49 | €2,25 | -36% |
| Wibra | Jog jeans grijs maat 74 t/m 86 | €11,99 | €8,00 | -33% |

## 4. Assortimentsomvang per groep (verschil t.o.v. vorige week)

| Groep | terStal familiemode | Action | C&A | HEMA | KiK | Primark | Wibra |
|---|---|---|---|---|---|---|---|
| dames / ondergoed | 133 (-66) | – | 110 (+10) | 20 (+3) | 197 (+11) | 544 (+22) | 41 (+2) |
| dames / nachtmode | 29 (-94) | – | 2 | – | 15 (-2) | 281 (+25) | 2 |
| heren / ondergoed | 41 (-19) | – | 14 (+2) | – | 58 (-1) | 55 | 8 (+1) |
| dames / sokken & panty's | 30 | – | – | 8 (+2) | – | 123 (+16) | 7 (-1) |
| heren / sokken & panty's | 31 (-17) | – | 26 (+5) | – | 45 (-4) | 35 (+1) | 1 |
| heren / nachtmode | 14 (-7) | – | 38 (+6) | 8 | 3 | 73 (+14) | – |
| meisjes / ondergoed | 31 (-13) | – | 11 | 11 | 74 (-5) | – | 9 (+1) |
| baby / nachtmode | – | – | 92 (+6) | 12 (-2) | 8 (-1) | – | 3 (-2) |
| jongens / ondergoed | 41 (-2) | – | 2 (+1) | 18 | 30 | – | 13 |
| baby / sokken & panty's | 12 (-4) | – | 29 (+1) | 18 (-1) | 4 (-1) | – | 32 (-1) |
| onbekend / ondergoed | 1 (-1) | – | 87 (-6) | – | 0 (-59) | – | – |
| jongens / nachtmode | 1 (-4) | – | 51 (+4) | 13 | 9 | – | 1 |
| kinderen / nachtmode | – | 1 | 73 (+4) | – | – | – | – |
| jongens / sokken & panty's | 22 (+2) | – | 36 (+2) | – | 10 (-3) | – | 3 |

## 5. Prijsindex t.o.v. terStal (mediaan; terStal = 100)

| Groep | Action | C&A | HEMA | KiK | Primark | Wibra |
|---|---|---|---|---|---|---|
| dames / ondergoed | – | 163 | 133 | 37 | 100 | 44 |
| dames / nachtmode | – | – | – | 50 | 114 | – |
| heren / ondergoed | – | 130 | – | 28 | 180 | 32 |
| dames / sokken & panty's | – | – | 163 | – | 75 | – |
| heren / sokken & panty's | – | 217 | – | 13 | 100 | – |
| heren / nachtmode | – | 93 | 71 | – | 114 | – |
| meisjes / ondergoed | – | 326 | 225 | 40 | – | 100 |
| jongens / ondergoed | – | – | 187 | 25 | – | 58 |
| baby / sokken & panty's | – | 250 | 133 | – | – | 94 |
| jongens / sokken & panty's | – | 133 | – | 11 | – | – |

> Index < 100: concurrent is goedkoper dan terStal. Kompas, geen rechter — kwaliteitsverschil is online onzichtbaar (PLAN.md §6.5).

### 5b. Prijsindex per stuk (multipacks omgerekend; terStal = 100)

| Groep | Action | C&A | HEMA | KiK | Primark | Wibra |
|---|---|---|---|---|---|---|
| dames / ondergoed | – | 173 | 142 | 40 | 50 | 47 |
| heren / ondergoed | – | 162 | – | 69 | 90 | 81 |
| dames / sokken & panty's | – | – | 487 | – | 100 | – |
| heren / sokken & panty's | – | 218 | – | 67 | 117 | – |
| heren / nachtmode | – | 82 | 71 | – | 114 | – |
| meisjes / ondergoed | – | 125 | 100 | 40 | – | 50 |
| jongens / ondergoed | – | – | 103 | 38 | – | 87 |
| baby / sokken & panty's | – | 83 | 125 | – | – | 187 |
| jongens / sokken & panty's | – | 115 | – | 55 | – | – |

> Prijs per stuk = prijs ÷ aantal in de verpakking, afgeleid uit de artikelnaam (3-pack, 5 paar). Alleen groepen waarin minstens één bron ≥10% multipacks voert. Aandeel multipacks in die groepen: terStal familiemode 52%, Action 0%, C&A 61%, HEMA 37%, KiK 0%, Primark 68%, Wibra 43%.
> Wijkt deze index sterk af van §5, dan zit het prijsverschil in de verpakkingsgrootte en niet in de prijs per stuk.

## 6. Sale-druk per bron

| Bron | % afgeprijsd | t.o.v. vorige week |
|---|---:|---:|
| terStal familiemode | 0% | +0 pt |
| Action | 0% | +0 pt |
| C&A | 18% | +3 pt |
| HEMA | 0% | +0 pt |
| KiK | 30% | -12 pt |
| Primark | 0% | +0 pt |
| Wibra | 8% | +1 pt |

## 7. Vernieuwingstempo per bron

| Bron | Omvang | Instroom deze week | Uitstroom deze week |
|---|---:|---:|---:|
| terStal familiemode | 443 | 6 (1%) | 577 (130%) |
| Action | 24 | 9 (38%) | 9 (38%) |
| C&A | 607 | 39 (6%) | 46 (8%) |
| HEMA | 137 | 10 (7%) | 11 (8%) |
| KiK | 478 | 28 (6%) | 118 (25%) |
| Primark | 1111 | 287 (26%) | 275 (25%) |
| Wibra | 125 | 9 (7%) | 10 (8%) |

> Instroom en uitstroom als aandeel van het eigen assortiment: wie hoog zit speelt op snelheid en nieuwheid, wie laag zit zit op voorraad. Ontbreekt de vorige week (eerste meting of tegengehouden door de kwaliteitspoort), dan zegt het percentage niets en blijft het leeg.


---
*Automatisch gegenereerd. Dashboard: zie Netlify-site. Ruwe data: Actions-artifact van deze run.*