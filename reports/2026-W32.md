# Weekrapport concurrentiemonitor — week 32, 2026

*Peildatum: maandag 03-08-2026. Cijfers betreffen het online assortiment (trend-indicatie, geen winkeltelling).*

*Scope: ondergoedmode — ondergoed, nachtmode, sokken & panty's.*

## 1. Gezondheid van de bronnen

| Bron | Strategie | Deze run | In database | t.o.v. vorige week | Status |
|---|---|---:|---:|---:|---|
| Action | render | 24 | 51 | – | 🟢 ok — {"new": 24, "back": 0, "gone": 0, "price_up": 0, "products": 24, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| C&A | render | 615 | 615 | – | 🟢 ok — {"new": 615, "back": 0, "gone": 0, "price_up": 0, "products": 615, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| HEMA | firecrawl | 26 | – | – | 🔴 fout — slechts 26 artikelen (minimum 60); bron gewijzigd? |
| KiK | render | 610 | 648 | – | 🟢 ok — {"new": 445, "back": 0, "gone": 0, "price_up": 0, "products": 610, "promo_end": 0, "price_down": 59, "promo_start": 49} |
| Primark | listing | 979 | 1025 | – | 🟢 ok — {"new": 42, "back": 0, "gone": 0, "price_up": 0, "products": 979, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| terStal familiemode | sitemap_pages | 716 | 716 | – | 🟢 ok — {"new": 0, "back": 0, "gone": 0, "price_up": 0, "products": 716, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| Wibra | firecrawl | 0 | – | – | 🔴 fout — Firecrawl leverde HTML maar geen producten — extractie nalopen |
| Zeeman | render | 6 | – | – | 🔴 fout — slechts 6 artikelen (minimum 25); bron gewijzigd? |

> 🟠/🔴: cijfers van die bron deze week niet gebruiken voor besluiten.
> *Deze run* is wat de scraper deze week ophaalde, *in database* de laatst verwerkte stand. Lopen die uiteen, dan heeft de kwaliteitspoort deze week tegengehouden en staat er nog oudere data.

## 2. Signalen van de week

- Eerste meting: signalen verschijnen vanaf volgende week (er is nog geen vergelijkingsweek).

## 3. Grootste prijsverlagingen deze week

| Bron | Artikel | Van | Naar | Verschil |
|---|---|---:|---:|---:|
| KiK | Hipster met hartjes | €4,99 | €1,00 | -80% |
| KiK | String met kanten tailleband | €4,99 | €1,00 | -80% |
| KiK | Slips | €4,99 | €1,00 | -80% |
| KiK | String met kant | €4,99 | €1,00 | -80% |
| KiK | Strings | €4,99 | €1,00 | -80% |

## 4. Assortimentsomvang per groep (verschil t.o.v. vorige week)

| Groep | terStal familiemode | Action | C&A | KiK | Primark |
|---|---|---|---|---|---|
| dames / ondergoed | 194 | 2 | 117 | 254 | 510 |
| dames / nachtmode | 123 | – | 2 | 21 | 285 |
| heren / ondergoed | 60 | 1 | 12 | 62 | 54 |
| onbekend / ondergoed | 2 | 24 | 86 | 64 | 2 |
| heren / sokken & panty's | 48 | – | 21 | 48 | 27 |
| meisjes / ondergoed | 44 | – | 13 | 85 | – |
| dames / sokken & panty's | 30 | – | – | – | 94 |
| heren / nachtmode | 21 | – | 42 | 4 | 50 |
| baby / nachtmode | – | – | 89 | 10 | – |
| kinderen / nachtmode | – | – | 87 | – | – |
| meisjes / sokken & panty's | 62 | – | – | 24 | – |
| jongens / ondergoed | 43 | – | 1 | 32 | – |
| jongens / nachtmode | 5 | – | 55 | 10 | – |
| jongens / sokken & panty's | 17 | – | 33 | 14 | – |

## 5. Prijsindex t.o.v. terStal (mediaan; terStal = 100)

| Groep | Action | C&A | KiK | Primark |
|---|---|---|---|---|
| dames / ondergoed | – | 163 | 62 | 100 |
| dames / nachtmode | – | – | 50 | 114 |
| heren / ondergoed | – | 144 | 22 | 200 |
| heren / sokken & panty's | – | 217 | 13 | 100 |
| meisjes / ondergoed | – | 326 | 38 | – |
| dames / sokken & panty's | – | – | – | 75 |
| heren / nachtmode | – | 93 | – | 114 |
| meisjes / sokken & panty's | – | – | 17 | – |
| jongens / ondergoed | – | – | 38 | – |
| jongens / sokken & panty's | – | 133 | 11 | – |

> Index < 100: concurrent is goedkoper dan terStal. Kompas, geen rechter — kwaliteitsverschil is online onzichtbaar (PLAN.md §6.5).

## 6. Sale-druk per bron

| Bron | % afgeprijsd | t.o.v. vorige week |
|---|---:|---:|
| terStal familiemode | 0% | – |
| Action | 6% | – |
| C&A | 22% | – |
| KiK | 45% | – |
| Primark | 0% | – |

---
*Automatisch gegenereerd. Dashboard: zie Netlify-site. Ruwe data: Actions-artifact van deze run.*