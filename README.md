# Concurrentiemonitor terStal

Wekelijkse monitoring van **assortiment en prijsvorming** bij de concurrenten van
terStal familiemode, met **focus op ondergoedmode** (ondergoed, nachtmode, sokken &
panty's) bij terStal, Wibra, Zeeman, Primark, Action, HEMA en C&A. Elke
maandagochtend liggen er automatisch klaar:

1. een **weekmail** voor de inkoopmanager (de maandagsamenvatting van het dashboard in zes
   blokken, HTML + platte tekst, via Resend; ontwerp in
   [`docs/weekmail-voorstel.md`](docs/weekmail-voorstel.md)) en een **weekrapport**
   (markdown, in [`reports/`](reports/) en in de job-samenvatting op
   GitHub) met bron-gezondheid, signalen, prijsverlagingen,
   assortimentstabellen, de prijsindex t.o.v. terStal (op artikelprijs én per stuk,
   zodat multipacks eerlijk meetellen) en het vernieuwingstempo per bron;
2. een bijgewerkt **dashboard** (Netlify) met trends per productgroep.

**Lees eerst [PLAN.md](PLAN.md)** — het strategische plan met de KPI-definities, de
kritische vragen aan de business en het maandagritueel. Dit README is de technische kant.
De geplande **folder-add-on** (weekfolders archiveren en uitlezen tot een retailkalender)
staat als reviewbaar voorstel in [docs/foldermonitor-plan.md](docs/foldermonitor-plan.md).

Kosten: **€0/maand** (GitHub Actions + Supabase free tier + Netlify free tier).

## Hoe het werkt

```
GitHub Actions (cron, ma ±06:07 NL)      Supabase (Postgres)
┌─────────────────────────────┐          ┌──────────────────────────────┐
│ scraper (Python)            │─ REST ──►│ staging → process_staging()  │
│  Shopify-JSON /             │          │ products, price_events,      │
│  lijstpagina's / sitemap    │          │ weekly_stats, scrape_runs    │
│ weekrapport + weekmail      │          └───────────┬──────────────────┘
└─────────────────────────────┘                      │ RLS: alleen ingelogd lezen
        ruwe dumps → artifact                        ▼
                                         Netlify: dashboard/index.html
```

- Opslag: **mutaties** (nieuw/prijswijziging/promo/verdwenen) + weekaggregaten voor de
  trends, én per artikel per week een **artikelfoto** (artnr, naam, categorieën, kleur,
  maten, van-/voor-prijs, ruwe actietekst, URL) — exporteerbaar als CSV via de view `v_artikelen_week`
  in Supabase. Ontbrekende kleur/maten worden via de productpagina aangevuld
  (gecapt, `enrich_limit`).
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
2. **Nieuw sinds de prijs-per-stuk-uitbreiding:** draai eenmalig
   [`sql/migratie_prijs_per_stuk.sql`](sql/migratie_prijs_per_stuk.sql) en voer daarna
   `sql/schema.sql` opnieuw uit (idempotent). Zonder die migratie blijven de per-stuk-
   cijfers leeg; de wekelijkse run blijft gewoon draaien en meldt het in de log.
3. ~~Schema uitvoeren~~ ✅ Al gebeurd — als migraties `init_schema` en
   `artikel_snapshots` (incl. tabel `weekly_articles`, view `v_artikelen_week` en de
   kolommen kleur/maten); de artikel-demo staat ook al live. Het bestand
   [`sql/migratie_artikelsnapshots.sql`](sql/migratie_artikelsnapshots.sql) is alleen
   nog relevant voor een eventuele nieuwe, tweede installatie.
4. Noteer uit **Project Settings → API**: de *Project URL*, de *anon public* key en de
   *service_role* key (geheim!).
5. **Authentication → Providers → Email**: laat *Email* aan; zet na het uitnodigen van
   het team *Allow new users to sign up* **uit** (alleen genodigden kunnen dan inloggen).
6. **Authentication → URL Configuration**: zet de Netlify-URL (stap 3) als *Site URL*.
7. Nodig dashboardgebruikers uit via **Authentication → Users → Invite user**.

### 2. GitHub (de wekelijkse motor)
1. Zet in de repo **Settings → Secrets and variables → Actions**:
   - `SUPABASE_URL` — de Project URL
   - `SUPABASE_SERVICE_ROLE_KEY` — de service_role key
   - voor de **weekmail** (docs/weekmail-voorstel.md): `RESEND_API_KEY`, `REPORT_EMAIL_TO`
     (ontvangers, kommagescheiden — nooit in de repo), `REPORT_EMAIL_FROM` (afzender op een
     bij [resend.com](https://resend.com) geverifieerd domein, bv. `Concurrentiemonitor terStal
     <naam@domein.nl>`), optioneel `REPORT_EMAIL_REPLY_TO` (antwoordadres). Zonder deze
     secrets wordt de weekmail wél gebouwd (reports/ en dashboard), niet verstuurd.
   - optioneel de repository-variabele `DASHBOARD_URL` als het dashboard niet op
     `concurrentiemonitor-terstal.netlify.app` staat (de doorkliklinks in de mail).
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
Zeeman-prijsverlagingen), `products` (actuele artikelstand), `weekly_articles` /
view **`v_artikelen_week`** (de artikelfoto: artnr t/m URL per artikel per week, na de
migratiestap hierboven) en `scrape_runs` (gezondheid, met een 'afwijkend'-voorbeeld
bij Action). Het bijbehorende maandagrapport staat in
[`reports/voorbeeld-weekrapport.md`](reports/voorbeeld-weekrapport.md).

- Demo opnieuw laden: [`sql/demo_seed.sql`](sql/demo_seed.sql) in de SQL-editor (herdraaibaar).
- **Vóór de echte eerste meting:** [`sql/demo_wissen.sql`](sql/demo_wissen.sql) uitvoeren,
  zodat de trends schoon beginnen.

## Wekelijks gebruik

- **Maandag ±03:07**: de weekrun start (cron `7 1 * * 1`, UTC; in de winter 02:07).
- **Maandag vóór 07:00**: de **weekmail** ligt in de mailbox van de inkoopmanager — de
  maandagsamenvatting van het dashboard in zes blokken, met per blok een doorklik
  (docs/weekmail-voorstel.md). Dezelfde mail staat in het dashboardpaneel *Weekmail* en in
  `reports/JJJJ-Www.html`.
- **Maandag 09:00**: het volledige rapport staat in `reports/` (nieuwste = `reports/latest.md`)
  en in de Actions-samenvatting. Dashboard voor de verdieping.
- **Maandag 09:15**: 15 minuten overleg, maximaal 3 acties (zie PLAN.md §1). Antwoord op de
  weekmail met 1, 2 of 3; het besluit komt in `reports/besluiten.md` (de actieteller).
- **Proefmail**: workflow "Wekelijkse scrape" → Run workflow met `alleen_rapport` aan en
  `mail_to` op je eigen adres; met `geen_mail` bouw je de mail zonder te versturen.
- Bron rood/oranje? Draai "Validatie bronnen" voor die bron en kijk naar het advies.

## CLI (lokaal of in Actions)

```bash
pip install -r requirements.txt

python -m scraper probe --retailer zeeman --limit 40   # bron valideren, zonder database
python -m scraper scrape --dry-run --limit 100         # scrapen zonder te schrijven
python -m scraper scrape                               # volledige weekrun (secrets nodig)
python -m scraper report                               # weekrapport uit de database
python -m scraper weekmail --dry-run                   # weekmail bouwen (reports/), niet versturen
python -m scraper weekmail --to naam@domein.nl         # proefmail naar één adres

python -m folders validate --bron zeeman               # foldermonitor: folderbron valideren (fase 0)
python -m folders bronnen                              # foldermonitor: bronconfiguratie tonen
python -m folders mailbox                              # foldermonitor: mailbox controleren (alleen-lezen; IMAP-secrets nodig)
```

Omgevingsvariabelen voor database/rapport: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
voor de weekmail `RESEND_API_KEY`, `REPORT_EMAIL_TO`, `REPORT_EMAIL_FROM`, optioneel
`REPORT_EMAIL_REPLY_TO` en `DASHBOARD_URL`.

## Beheer

| Taak | Hoe |
|---|---|
| Bron toevoegen | Blok in `scraper/retailers.yml` + "Validatie bronnen" draaien |
| Bron uit de grafiekset | `enabled: false`; historie blijft bewaard |
| Focus verbreden (bv. badmode of alles) | `focus_categories` / `focus_product_types` in de defaults van `retailers.yml` (leeg = volledig assortiment) |
| Artikellijst exporteren (artnr t/m URL) | Supabase → Table Editor of SQL-editor → view `v_artikelen_week` → Export CSV |
| Verrijking kleur/maten afstellen | `enrich` / `enrich_limit` in `retailers.yml` (per bron of in de defaults) |
| Geblokkeerde/client-side bron | `strategy: render` in `retailers.yml` — headless browser (Playwright) met cookiemuur-acceptatie en API-interceptie; zwaarder, dus eigen krappere caps per bron |
| Lijstbron die ineens 403 geeft (Zeeman 14-09) | `fetch_ladder: [http, chrome, browser, firecrawl]` in `retailers.yml` — de toegangsladder (`scraper/fetch.py`) klimt zelf naar een zwaardere client; de trede die werkte staat in het weekrapport (`listing+chrome`). Welke poortwachter het is: "Validatie bronnen" met een categoriepagina in `diagnose_urls` → toegangsmatrix |
| Bron die het datacenter-IP weert (Wibra, HEMA) | `strategy: firecrawl` + secret `FIRECRAWL_API_KEY` — externe scrape-dienst met residentiële proxies (**betaald**, zie PLAN.md §8); zonder sleutel blijft de bron rood |
| Mapping verbeteren | Regels in `scraper/mapping.yml` (volgorde telt); test in `tests/` |
| Multipack-herkenning bijstellen | `pack_size()` in `scraper/normalize.py` (regexes + `PACK_MAX`); test in `tests/test_pack_size.py` |
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
  fetch.py, blokkade.py     toegangsladder (http → chrome → browser → firecrawl) + handtekening van de poortwachter
  signals.py                weekmail: signaalscore, ruisfilter, sjablonen, terugblik (zuiver, getest)
  weekmail.py               weekmail: model → HTML + platte tekst, versturen, bewaren
sql/schema.sql              Supabase-schema incl. verwerkingsfunctie en RLS
dashboard/                  statisch dashboard (Netlify), login via Supabase Auth
.github/workflows/          wekelijkse scrape · validatie bronnen · toegangscheck (donderdag-kanarie) · CI · validatie folders · foldermonitor (preview)
reports/                    gegenereerde weekrapporten (gecommit door de bot)
folders/                    foldermonitor (add-on, in preview): bronnen.yml, viewerdetectie, validatie, mailboxcontrole
docs/foldermonitor-plan.md  plan voor de folder-add-on: archief + retailkalender (goedgekeurd 05-09)
docs/foldermonitor-fase0.md fase 0: wat er staat, eigenaarschecklist — ON HOLD sinds 08-09-2026, weekscrape loopt door
docs/validaties/            beslissende metingen per bron, met run-id's
```
