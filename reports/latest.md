# Weekrapport concurrentiemonitor — week 33, 2026

*Peildatum: maandag 10-08-2026. Cijfers betreffen het online assortiment (trend-indicatie, geen winkeltelling).*

*Scope: ondergoedmode — ondergoed, nachtmode, sokken & panty's.*

## 1. Gezondheid van de bronnen

| Bron | Strategie | Deze run | In database | t.o.v. vorige week | Status |
|---|---|---:|---:|---:|---|
| Action | render | 24 | 24 | -53% | 🟢 ok — {"new": 4, "back": 0, "gone": 31, "price_up": 0, "products": 24, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| C&A | render | 589 | 638 | +4% | 🟢 ok — {"new": 29, "back": 4, "gone": 0, "price_up": 0, "products": 589, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| HEMA | firecrawl | 158 | 158 | – | 🟢 ok — {"new": 158, "back": 0, "gone": 0, "price_up": 0, "products": 158, "promo_end": 0, "price_down": 0, "promo_start": 0} · 24 Firecrawl-credits |
| KiK | render | 603 | 625 | -4% | 🟢 ok — {"new": 16, "back": 0, "gone": 0, "price_up": 0, "products": 603, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| Primark | listing | 1002 | 1040 | +1% | 🟢 ok — {"new": 57, "back": 7, "gone": 0, "price_up": 0, "products": 1002, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| terStal familiemode | sitemap_pages | 716 | 716 | +0% | 🟢 ok — {"new": 0, "back": 0, "gone": 0, "price_up": 0, "products": 716, "promo_end": 0, "price_down": 0, "promo_start": 0} |
| Wibra | firecrawl | 129 | 129 | – | 🟢 ok — {"new": 129, "back": 0, "gone": 0, "price_up": 0, "products": 129, "promo_end": 0, "price_down": 0, "promo_start": 0} · 12 Firecrawl-credits |
| Zeeman | render | 6 | – | – | 🔴 fout — slechts 6 artikelen (minimum 25); bron gewijzigd? |

> 🟠/🔴: cijfers van die bron deze week niet gebruiken voor besluiten.
> *Deze run* is wat de scraper deze week ophaalde, *in database* de laatst verwerkte stand. Lopen die uiteen, dan heeft de kwaliteitspoort deze week tegengehouden en staat er nog oudere data.

## 2. Signalen van de week

- **C&A** · meisjes / ondergoed: instapniveau omhoog van €4,99 naar €8,74 (+75%)
- **Action** · onbekend / ondergoed: saneert van 24 naar 0 artikelen (-100%)
- **KiK** · dames / ondergoed: mediaanprijs omlaag van €4,99 naar €3,00 (-40%)
- **C&A** · heren / nachtmode: mediaanprijs omlaag van €12,99 naar €9,99 (-23%)
- **KiK** · baby / nachtmode: mediaanprijs omhoog van €3,00 naar €3,50 (+17%)
- **Action** · onbekend / nachtmode: mediaanprijs omhoog van €5,97 naar €6,95 (+16%)
- **KiK** · dames / ondergoed: instapniveau omlaag van €2,33 naar €2,00 (-14%)
- **C&A** · jongens / sokken & panty's: instapniveau omhoog van €5,39 naar €5,84 (+8%)

## 3. Grootste prijsverlagingen deze week

| Bron | Artikel | Van | Naar | Verschil |
|---|---|---:|---:|---:|
| C&A | Terug naar de bovenliggende pagina | €19,99 | €12,99 | -35% |

## 4. Assortimentsomvang per groep (verschil t.o.v. vorige week)

| Groep | terStal familiemode | Action | C&A | HEMA | KiK | Primark | Wibra |
|---|---|---|---|---|---|---|---|
| dames / ondergoed | 194 | 0 (-2) | 119 (+2) | 17 | 219 (-35) | 522 (+12) | 40 |
| dames / nachtmode | 123 | – | 2 | – | 23 (+2) | 284 (-1) | 2 |
| heren / ondergoed | 60 | 0 (-1) | 12 | – | 62 | 54 | 5 |
| meisjes / ondergoed | 44 | – | 12 (-1) | 16 | 88 (+3) | – | 8 |
| onbekend / ondergoed | 2 | 0 (-24) | 91 (+5) | – | 67 (+3) | 0 (-2) | – |
| heren / sokken & panty's | 48 | – | 21 | – | 49 (+1) | 28 (+1) | 1 |
| dames / sokken & panty's | 30 | – | – | 6 | – | 96 (+2) | 8 |
| heren / nachtmode | 21 | – | 47 (+5) | 9 | 4 | 56 (+6) | – |
| baby / nachtmode | – | – | 97 (+8) | 16 | 11 (+1) | – | 6 |
| jongens / ondergoed | 43 | – | 1 | 18 | 33 (+1) | – | 14 |
| meisjes / sokken & panty's | 62 | – | – | 16 | 25 (+1) | – | 3 |
| baby / sokken & panty's | 16 | – | 24 | 19 | 8 | – | 34 |
| jongens / nachtmode | 5 | – | 56 (+1) | 18 | 10 | – | 1 |
| kinderen / nachtmode | – | – | 90 (+3) | – | – | – | – |

## 5. Prijsindex t.o.v. terStal (mediaan; terStal = 100)

| Groep | Action | C&A | HEMA | KiK | Primark | Wibra |
|---|---|---|---|---|---|---|
| dames / ondergoed | – | 163 | 109 | 38 | 100 | 44 |
| dames / nachtmode | – | – | – | 50 | 114 | – |
| heren / ondergoed | – | 144 | – | 22 | 200 | – |
| meisjes / ondergoed | – | 326 | 213 | 38 | – | 100 |
| heren / sokken & panty's | – | 217 | – | 13 | 100 | – |
| dames / sokken & panty's | – | – | – | – | 75 | 37 |
| heren / nachtmode | – | 71 | 157 | – | 114 | – |
| jongens / ondergoed | – | – | 307 | 38 | – | 87 |
| meisjes / sokken & panty's | – | – | 83 | 17 | – | – |
| baby / sokken & panty's | – | 188 | 140 | 17 | – | 100 |

> Index < 100: concurrent is goedkoper dan terStal. Kompas, geen rechter — kwaliteitsverschil is online onzichtbaar (PLAN.md §6.5).

## 6. Sale-druk per bron

| Bron | % afgeprijsd | t.o.v. vorige week |
|---|---:|---:|
| terStal familiemode | 0% | +0 pt |
| Action | 0% | -6 pt |
| C&A | 21% | -0 pt |
| HEMA | 0% | – |
| KiK | 46% | +1 pt |
| Primark | 0% | +0 pt |
| Wibra | 9% | – |

---
*Automatisch gegenereerd. Dashboard: zie Netlify-site. Ruwe data: Actions-artifact van deze run.*