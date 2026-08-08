# Weekrapport concurrentiemonitor — week 32, 2026

*Peildatum: maandag 03-08-2026. Cijfers betreffen het online assortiment (trend-indicatie, geen winkeltelling).*

*Scope: ondergoedmode — ondergoed, nachtmode, sokken & panty's.*

## 1. Gezondheid van de bronnen

| Bron | Strategie | Artikelen | t.o.v. vorige week | Status |
|---|---|---:|---:|---|
| Action | render | 27 | – | 🟢 ok — {"new": 27, "back": 0, "gone": 0, "price_up": 0, "products": 27, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| C&A | render | – | – | 🔴 fout — slechts 21 artikelen (minimum 25); bron gewijzigd? |
| HEMA | firecrawl | – | – | 🔴 fout — FIRECRAWL_API_KEY niet gezet — deze bron blijft ongescrapet. Zet de sleutel als GitHub-secret om Firecrawl te activeren (betaalde dienst, zie PLAN.md §8). |
| KiK | render | 203 | – | 🟢 ok — {"new": 203, "back": 0, "gone": 0, "price_up": 0, "products": 203, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| Primark | listing | 855 | – | 🟢 ok — {"new": 855, "back": 0, "gone": 0, "price_up": 0, "products": 855, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| terStal familiemode | sitemap_pages | 716 | – | 🟢 ok — {"new": 716, "back": 0, "gone": 0, "price_up": 0, "products": 716, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| Wibra | firecrawl | – | – | 🔴 fout — FIRECRAWL_API_KEY niet gezet — deze bron blijft ongescrapet. Zet de sleutel als GitHub-secret om Firecrawl te activeren (betaalde dienst, zie PLAN.md §8). |
| Zeeman | sitemap_pages | – | – | 🔴 fout — slechts 15 artikelen (minimum 25); bron gewijzigd? |

> 🟠/🔴: cijfers van die bron deze week niet gebruiken voor besluiten.

## 2. Signalen van de week

- Eerste meting: signalen verschijnen vanaf volgende week (er is nog geen vergelijkingsweek).

## 3. Grootste prijsverlagingen deze week

Geen prijsverlagingen geregistreerd.

## 4. Assortimentsomvang per groep (verschil t.o.v. vorige week)

| Groep | terStal familiemode | Action | KiK | Primark |
|---|---|---|---|---|
| onbekend / ondergoed | 2 | 24 | – | 489 |
| dames / ondergoed | 194 | 2 | 203 | – |
| onbekend / nachtmode | 2 | – | – | 271 |
| dames / nachtmode | 123 | – | – | – |
| onbekend / sokken & panty's | 28 | – | – | 92 |
| meisjes / sokken & panty's | 62 | – | – | 2 |
| heren / ondergoed | 60 | 1 | – | – |
| heren / sokken & panty's | 48 | – | – | – |
| meisjes / ondergoed | 44 | – | – | – |
| jongens / ondergoed | 43 | – | – | – |
| dames / sokken & panty's | 30 | – | – | – |
| heren / nachtmode | 21 | – | – | – |
| meisjes / nachtmode | 19 | – | – | – |
| jongens / sokken & panty's | 17 | – | – | – |

## 5. Prijsindex t.o.v. terStal (mediaan; terStal = 100)

| Groep | Action | KiK | Primark |
|---|---|---|---|
| dames / ondergoed | – | 75 | – |
| dames / nachtmode | – | – | – |
| onbekend / sokken & panty's | – | – | 90 |
| meisjes / sokken & panty's | – | – | – |
| heren / ondergoed | – | – | – |
| heren / sokken & panty's | – | – | – |
| meisjes / ondergoed | – | – | – |
| jongens / ondergoed | – | – | – |
| dames / sokken & panty's | – | – | – |
| heren / nachtmode | – | – | – |
| meisjes / nachtmode | – | – | – |
| jongens / sokken & panty's | – | – | – |

> Index < 100: concurrent is goedkoper dan terStal. Kompas, geen rechter — kwaliteitsverschil is online onzichtbaar (PLAN.md §6.5).

## 6. Sale-druk per bron

| Bron | % afgeprijsd | t.o.v. vorige week |
|---|---:|---:|
| terStal familiemode | 0% | – |
| Action | 11% | – |
| KiK | 27% | – |
| Primark | 0% | – |

---
*Automatisch gegenereerd. Dashboard: zie Netlify-site. Ruwe data: Actions-artifact van deze run.*