# Weekrapport concurrentiemonitor — week 46, 2026

*Peildatum: maandag 09-11-2026. Cijfers betreffen het online assortiment (trend-indicatie, geen winkeltelling).*

*Scope: ondergoedmode — ondergoed, nachtmode, sokken & panty's.*

## 1. Gezondheid van de bronnen

| Bron | Strategie | Deze run | In database | t.o.v. vorige week | Status |
|---|---|---:|---:|---:|---|
| Action | render | 212 | 212 | -1% | 🟢 ok — {"new": 1, "back": 8, "gone": 11, "price_up": 18, "products": 212, "promo_end": 0, "price_down": 10, "promo_start": 0} |
| C&A | render | 887 | 887 | -2% | 🟢 ok — {"new": 28, "back": 24, "gone": 67, "price_up": 0, "products": 887, "promo_end": 0, "price_down": 101, "promo_start": 101} |
| HEMA | firecrawl | 130 | 130 | -2% | 🟢 ok — {"new": 13, "back": 4, "gone": 19, "price_up": 3, "products": 130, "promo_end": 0, "price_down": 2, "promo_start": 0} · 24 Firecrawl-credits |
| KiK | render | 0 | – | – | 🔴 fout — geen categorie-URLs gevonden (ook niet via de browser) |
| Primark | listing | 1111 | 1111 | +0% | 🟢 ok — {"new": 187, "back": 74, "gone": 256, "price_up": 0, "products": 1111, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| terStal familiemode | sitemap_pages | 433 | 433 | +6% | 🟢 ok — {"new": 24, "back": 6, "gone": 5, "price_up": 0, "products": 433, "promo_end": 0, "price_down": 47, "promo_start": 0} |
| Wibra | firecrawl | 110 | 110 | -3% | 🟢 ok — {"new": 2, "back": 0, "gone": 5, "price_up": 0, "products": 110, "promo_end": 0, "price_down": 2, "promo_start": 2} · 12 Firecrawl-credits |
| Zeeman | listing+firecrawl | 923 | 923 | +0% | 🟢 ok — {"new": 71, "back": 26, "gone": 94, "price_up": 0, "products": 923, "promo_end": 0, "price_down": 0, "promo_start": 0} · 44 Firecrawl-credits |

> 🟠/🔴: cijfers van die bron deze week niet gebruiken voor besluiten.
> *Deze run* is wat de scraper deze week ophaalde, *in database* de laatst verwerkte stand. Lopen die uiteen, dan heeft de kwaliteitspoort deze week tegengehouden en staat er nog oudere data.

## 2. Signalen van de week

- **HEMA** · meisjes / sokken & panty's: mediaanprijs omlaag van €8,69 naar €4,99 (-43%)
- **HEMA** · meisjes / sokken & panty's: instapniveau omlaag van €7,99 naar €4,99 (-38%)
- **terStal familiemode** · meisjes / nachtmode: mediaanprijs omlaag van €19,99 naar €13,99 (-30%)
- **terStal familiemode** · heren / nachtmode: mediaanprijs omlaag van €19,99 naar €13,99 (-30%)
- **terStal familiemode** · dames / nachtmode: mediaanprijs omlaag van €19,99 naar €13,99 (-30%)
- **C&A** · onbekend / ondergoed: mediaanprijs omlaag van €12,99 naar €9,99 (-23%)
- **terStal familiemode** · heren / nachtmode: instapniveau omlaag van €18,12 naar €13,99 (-23%)
- **HEMA** · dames / sokken & panty's: saneert van 19 naar 12 artikelen (-37%)
- **Zeeman** · heren / ondergoed: instapniveau omlaag van €5,99 naar €4,69 (-22%)
- **terStal familiemode** · meisjes / sokken & panty's: breidt uit van 36 naar 47 artikelen (+31%)
- **terStal familiemode** · heren / sokken & panty's: mediaanprijs omhoog van €4,99 naar €5,99 (+20%)
- **C&A** · jongens / sokken & panty's: mediaanprijs omlaag van €9,99 naar €7,99 (-20%)
- **C&A** · onbekend / ondergoed: saneert van 85 naar 67 artikelen (-21%)
- **HEMA** · meisjes / ondergoed: breidt uit van 16 naar 21 artikelen (+31%)
- **Zeeman** · dames / nachtmode: mediaanprijs omhoog van €8,49 naar €9,99 (+18%)

## 3. Grootste prijsverlagingen deze week

| Bron | Artikel | Van | Naar | Verschil |
|---|---|---:|---:|---:|
| Wibra | Singlet bliss | €5,99 | €3,00 | -50% |
| Wibra | Singlet spaghetti | €3,99 | €2,00 | -50% |
| HEMA | kinderboxers - 3 stuks groen | €8,00 | €5,00 | -38% |
| C&A | wit | €12,99 | €8,99 | -31% |
| C&A | Set 5 paar - sneakersokken | €12,99 | €8,99 | -31% |
| C&A | donkerblauw | €7,99 | €5,99 | -25% |
| C&A | Set 7 paar - monstertruck en dinosaurus - sokken met motief | €7,99 | €5,99 | -25% |
| C&A | wit | €7,99 | €5,99 | -25% |
| terStal familiemode | pyjama set met print | €12,99 | €9,09 | -30% |
| terStal familiemode | pyjama set met print | €12,99 | €9,09 | -30% |
| terStal familiemode | pyjama set met print | €12,99 | €9,09 | -30% |
| terStal familiemode | pyjama set met print | €12,99 | €9,09 | -30% |
| terStal familiemode | pyjama set met print | €12,99 | €9,09 | -30% |

## 4. Assortimentsomvang per groep (verschil t.o.v. vorige week)

| Groep | terStal familiemode | Action | C&A | HEMA | Primark | Wibra | Zeeman |
|---|---|---|---|---|---|---|---|
| dames / ondergoed | 120 (+2) | 2 (-1) | 247 | 1 | 565 (+14) | 45 (-2) | 267 (-25) |
| dames / nachtmode | 38 | 2 | 10 | – | 238 (-13) | 1 | 31 (-1) |
| dames / sokken & panty's | 34 (+1) | 2 | – | 12 (-7) | 135 (+4) | 7 (-1) | 99 (-1) |
| kinderen / ondergoed | – | 1 | – | – | – | – | 219 (+11) |
| kinderen / nachtmode | – | 1 (-1) | 108 | – | – | – | 89 (+11) |
| heren / ondergoed | 45 (+5) | 3 (+1) | 13 | – | 53 | 7 (-1) | 65 (-1) |
| onbekend / ondergoed | – | 99 | 67 (-18) | – | – | – | – |
| baby / nachtmode | – | – | 130 (+7) | 8 | – | 4 (+2) | 21 (+1) |
| heren / nachtmode | 10 | 3 (-1) | 22 | 9 | 88 (+1) | – | 12 (+2) |
| baby / sokken & panty's | 10 | – | 51 | 15 | – | 28 (-1) | 23 (+5) |
| heren / sokken & panty's | 24 (+4) | 2 | 34 (-1) | 0 (-4) | 32 (-1) | – | 34 (+3) |
| onbekend / sokken & panty's | 17 | 65 | 31 (+2) | – | – | – | – |
| jongens / nachtmode | 3 | 2 | 62 (-3) | 17 | – | 2 | – |
| onbekend / nachtmode | – | 28 (+1) | 53 | – | – | – | – |

## 5. Prijsindex t.o.v. terStal (mediaan; terStal = 100)

| Groep | Action | C&A | HEMA | Primark | Wibra | Zeeman |
|---|---|---|---|---|---|---|
| dames / ondergoed | – | 163 | – | 113 | 75 | 59 |
| dames / nachtmode | – | 214 | – | 122 | – | 71 |
| dames / sokken & panty's | – | – | 120 | 90 | – | 70 |
| heren / ondergoed | – | 144 | – | 200 | – | 67 |
| heren / nachtmode | – | 93 | 264 | 122 | – | 79 |
| baby / sokken & panty's | – | 175 | 175 | – | 138 | 87 |
| heren / sokken & panty's | – | 217 | – | 100 | – | 67 |
| onbekend / sokken & panty's | 56 | 120 | – | – | – | – |

> Index < 100: concurrent is goedkoper dan terStal. Kompas, geen rechter — kwaliteitsverschil is online onzichtbaar (PLAN.md §6.5).

### 5b. Prijsindex per stuk (multipacks omgerekend; terStal = 100)

| Groep | Action | C&A | HEMA | Primark | Wibra | Zeeman |
|---|---|---|---|---|---|---|
| dames / ondergoed | – | 163 | – | 67 | 63 | 34 |
| dames / sokken & panty's | – | – | 370 | 127 | – | 111 |
| heren / ondergoed | – | 162 | – | 90 | – | 75 |
| heren / nachtmode | – | 25 | 264 | 122 | – | 79 |
| baby / sokken & panty's | – | 83 | 140 | – | 274 | 35 |
| heren / sokken & panty's | – | 278 | – | 100 | – | 83 |
| onbekend / sokken & panty's | 223 | 160 | – | – | – | – |

> Prijs per stuk = prijs ÷ aantal in de verpakking, afgeleid uit de artikelnaam (3-pack, 5 paar) of uit de stukprijs op de kaart (KiK '0,66 € / Stuk', Action '€ 2,48/st'). Alleen groepen waarin minstens één bron ≥10% multipacks voert. Aandeel multipacks in die groepen: terStal familiemode 60%, Action 0%, C&A 61%, HEMA 16%, Primark 66%, Wibra 14%, Zeeman 50%.
> Wijkt deze index sterk af van §5, dan zit het prijsverschil in de verpakkingsgrootte en niet in de prijs per stuk.

## 6. Sale-druk per bron

| Bron | % afgeprijsd | t.o.v. vorige week |
|---|---:|---:|
| terStal familiemode | 0% | +0 pt |
| Action | 0% | +0 pt |
| C&A | 21% | +11 pt |
| HEMA | 0% | +0 pt |
| Primark | 0% | +0 pt |
| Wibra | 5% | +1 pt |
| Zeeman | 0% | +0 pt |

## 7. Vernieuwingstempo per bron

| Bron | Omvang | Instroom deze week | Uitstroom deze week |
|---|---:|---:|---:|
| terStal familiemode | 433 | 24 (6%) | 5 (1%) |
| Action | 212 | 1 (0%) | 11 (5%) |
| C&A | 887 | 28 (3%) | 67 (8%) |
| HEMA | 130 | 13 (10%) | 19 (15%) |
| Primark | 1111 | 187 (17%) | 256 (23%) |
| Wibra | 110 | 2 (2%) | 5 (5%) |
| Zeeman | 923 | 71 (8%) | 94 (10%) |

> Instroom en uitstroom als aandeel van het eigen assortiment: wie hoog zit speelt op snelheid en nieuwheid, wie laag zit zit op voorraad. Ontbreekt de vorige week (eerste meting of tegengehouden door de kwaliteitspoort), dan zegt het percentage niets en blijft het leeg.


---
*Automatisch gegenereerd. Dashboard: zie Netlify-site. Ruwe data: Actions-artifact van deze run.*