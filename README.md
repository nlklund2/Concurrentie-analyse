# Concurrentiemonitor terStal

Wekelijkse monitoring van **assortiment en prijsvorming** bij de concurrenten van
terStal familiemode, met **focus op ondergoedmode** (ondergoed, nachtmode, sokken &
panty's) bij terStal, Wibra, Zeeman, Primark, Action, HEMA en C&A. Elke
maandagochtend liggen er automatisch klaar:

1. een **weekrapport** (markdown, in [`reports/`](reports/), in de job-samenvatting op
   GitHub en optioneel per e-mail) met bron-gezondheid, signalen, prijsverlagingen,
   assortimentstabellen en de prijsindex t.o.v. terStal;
2. een bijgewerkt **dashboard** (Netlify) met trends per productgroep.

**Lees eerst [PLAN.md](PLAN.md)** — het strategische plan met de KPI-definities, de
kritische vragen aan de business en het maandagritueel. Dit README is de technische kant.

Kosten: **€0/maand** (GitHub Actions + Supabase free tier + Netlify free tier).

## Hoe het werkt

```
GitHub Actions (cron, ma ±06:30 NL)      Supabase (Postgres)
┌─────────────────────────────┐          ┌──────────────────────────────┐
│ scraper (Python)            │─ REST ──►│ staging → process_staging()  │
│  Shopify-JSON /             │          │ products, price_events,      │
│  lijstpagina's / sitemap    │          │ weekly_stats, scrape_runs    │
│ weekrapport + e-mail        │          └───────────┬──────────────────┘
└─────────────────────────────┘                      │ RLS: alleen ingelogd lezen
        ruwe dumps → artifact                        ▼
                                         Netlify: dashboard/index.html
```

- Alleen **mutaties** worden opgeslagen (nieuw/prijswijziging/promo/verdwenen) plus
  weekaggregaten — de database blijft jaren klein.
- Een **kwaliteitspoort** voorkomt vervuiling: levert een bron minder dan 50% van de
  vorige week, dan wordt die week niet verwerkt en kleurt de bron oranje in het rapport.
- Bronnen en strategieën staan in [`scraper/retailers.yml`](scraper/retailers.yml);
  de categoriemapping in [`scraper/mapping.yml`](scraper/mapping.yml).

## Installatie (eenmalig, ±30 minuten)

### 1. Supabase (database + login)
1. ~~Maak een gratis project~~ ✅ **Al gebeurd:** project **`concurrentiemonitor-terstal`**
   bestaat (regio eu-central-1, gratis tier), met het schema uit
   [`sql/schema.sql`](sql/schema.sql) toegepast én drie weken demo-data geladen
   (zie kopje *Demo-data* hieronder).
2. ~~Schema uitvoeren~~ ✅ Al gebeurd (als migratie `init_schema`).
3. Noteer uit **Project Settings → API**: de *Project URL*, de *anon public* key en de
   *service_role* key (geheim!).
4. **Authentication → Providers → Email**: laat *Email* aan; zet na het uitnodigen van
   het team *Allow new users to sign up* **uit** (alleen genodigden kunnen dan inloggen).
5. **Authentication → URL Configuration**: zet de Netlify-URL (stap 3) als *Site URL*.
6. Nodig dashboardgebruikers uit via **Authentication → Users → Invite user**.

### 2. GitHub (de wekelijkse motor)
1. Zet in de repo **Settings → Secrets and variables → Actions**:
   - `SUPABASE_URL` — de Project URL
   - `SUPABASE_SERVICE_ROLE_KEY` — de service_role key
   - optioneel voor e-mail: `RESEND_API_KEY`, `REPORT_EMAIL_TO` (kommagescheiden),
     `REPORT_EMAIL_FROM` (geverifieerd afzenderadres bij [resend.com](https://resend.com))
2. Draai **Actions → "Validatie bronnen" → Run workflow**. Dit test alle bronnen met een
   proefscrape (±40 artikelen per bron, zonder database) en zet een leesbaar rapport in de
   job-samenvatting: welke strategie werkt, prijsdekking, mappingkwaliteit en een advies
   per bron. Zet bronnen die rood blijven op `enabled: false` of voeg `seeds` toe.
3. Draai daarna **Actions → "Wekelijkse scrape" → Run workflow** voor de eerste echte meting.
   Vanaf dan loopt hij elke maandagnacht vanzelf. *(Let op: het cron-schema wordt actief
   zodra deze bestanden op de default branch staan.)*

### 3. Netlify (dashboard)
1. [Netlify](https://netlify.com) → *Add new site → Import an existing project* → kies deze repo.
   Build command en publish directory staan al in `netlify.toml`.
2. Zet bij **Site configuration → Environment variables**:
   `SUPABASE_URL` en `SUPABASE_ANON_KEY` (de *anon public* key — dit is een publieke
   client-sleutel; de databeveiliging zit in Row Level Security + login).
3. Deploy. Log in op het dashboard met een uitgenodigd e-mailadres (magic link).

## Demo-data

Het Supabase-project bevat **drie weken fictieve dummydata** (weken 30–32 van 2026) om
de werking te zien voordat de eerste echte scrape draait. Kijken: **Table Editor →
`weekly_stats`** (omvang- en prijstrends per groep), `price_events` (mutaties, o.a. de
Zeeman-prijsverlagingen), `products` (actuele artikelstand) en `scrape_runs`
(gezondheid, met een 'afwijkend'-voorbeeld bij Action). Het bijbehorende maandagrapport
staat in [`reports/voorbeeld-weekrapport.md`](reports/voorbeeld-weekrapport.md).

- Demo opnieuw laden: [`sql/demo_seed.sql`](sql/demo_seed.sql) in de SQL-editor (herdraaibaar).
- **Vóór de echte eerste meting:** [`sql/demo_wissen.sql`](sql/demo_wissen.sql) uitvoeren,
  zodat de trends schoon beginnen.

## Wekelijks gebruik

- **Maandag 09:00**: rapport staat in `reports/` (nieuwste = `reports/latest.md`), in de
  Actions-samenvatting en eventueel in de mail. Dashboard voor de verdieping.
- **Maandag 09:15**: 15 minuten overleg, maximaal 3 acties (zie PLAN.md §1).
- Bron rood/oranje? Draai "Validatie bronnen" voor die bron en kijk naar het advies.

## CLI (lokaal of in Actions)

```bash
pip install -r requirements.txt

python -m scraper probe --retailer zeeman --limit 40   # bron valideren, zonder database
python -m scraper scrape --dry-run --limit 100         # scrapen zonder te schrijven
python -m scraper scrape                               # volledige weekrun (secrets nodig)
python -m scraper report                               # weekrapport uit de database
```

Omgevingsvariabelen voor database/rapport: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
optioneel `RESEND_API_KEY`, `REPORT_EMAIL_TO`, `REPORT_EMAIL_FROM`.

## Beheer

| Taak | Hoe |
|---|---|
| Bron toevoegen | Blok in `scraper/retailers.yml` + "Validatie bronnen" draaien |
| Bron uit de grafiekset | `enabled: false`; historie blijft bewaard |
| Focus verbreden (bv. badmode of alles) | `focus_categories` / `focus_product_types` in de defaults van `retailers.yml` (leeg = volledig assortiment) |
| Mapping verbeteren | Regels in `scraper/mapping.yml` (volgorde telt); test in `tests/` |
| Grafiekkleur | `color_slot` (1–8) in `retailers.yml` én de `SLOTS`-map in `dashboard/index.html` — kleur volgt de bron, hergebruik een slot nooit voor een andere bron |
| Signaaldrempels rapport | Constantes bovenin `scraper/report.py` |
| Ruwe data terugkijken | Actions-run → artifact `ruwe-data-…` (60 dagen bewaard) |

## Structuur

```
PLAN.md                     strategisch plan, KPI's, kritische vragen (eerst lezen)
scraper/                    Python-pakket (scrapen, normaliseren, rapporteren)
  retailers.yml             bronnen + strategie per bron
  mapping.yml               uniforme taxonomie (regexregels)
  strategies/               shopify / listing_crawl / sitemap_pages (+ autodetectie)
sql/schema.sql              Supabase-schema incl. verwerkingsfunctie en RLS
dashboard/                  statisch dashboard (Netlify), login via Supabase Auth
.github/workflows/          wekelijkse scrape · validatie bronnen · CI
reports/                    gegenereerde weekrapporten (gecommit door de bot)
```
