# Foldermonitor — fase 0: logboek en eigenaarschecklist

*Stand: 7 september 2026 (logboek 06-09 en 07-09 hieronder). Hoort bij [foldermonitor-plan.md](foldermonitor-plan.md) (§9.5 preview naast productie, §13 roadmap).*

## Besluiten van de eigenaar (05-09)

| # | Besluit | Uitkomst |
|---|---|---|
| 1 | Mailbox | **neutraal adres op een eigen Google Workspace-domein van de eigenaar** (aangeleverd 06-09). Zelfde mechaniek als Gmail: IMAP `imap.gmail.com`, app-wachtwoord, plus-aliassen per bron. Het adres staat alleen in het secret `FOLDER_IMAP_USER` — nergens in deze publieke repo |
| 2 | Opslagpad | **Supabase Storage** in het preview-project; besluit R2 (€0) of Pro (€25) rond maand 3 |
| 3 | Extractie | **vision-model akkoord** (Haiku 4.5 classificatie, Opus 5 extractie, via Batch API) |
| — | Werkwijze | **eerst apart en zichtbaar naast productie**; go-live is een bewuste handeling (feature-vlag) |

## Wat er staat (gebouwd 05-09)

| Laag | Wat | Waar |
|---|---|---|
| Supabase preview | project **`concurrentiemonitor-preview`** (ref `kptmymvxqhrfmnzmurbk`, eu-central-1, gratis tier); migratie `folders_init` toegepast (= `sql/migratie_folders.sql`): tabellen `folders`, `folder_pages`, `folder_offers`, `folder_weekly_stats`, `folder_runs`; views `v_folders`, `v_folder_aanbiedingen`, `v_retailkalender`; functie `process_folder_week`; RLS; buckets `folders` en `folders-inbox`; 10 retailers geseed | https://kptmymvxqhrfmnzmurbk.supabase.co |
| Code | pakket `folders/`: `bronnen.yml` (8 bronnen + Lidl/Aldi uit), `config.py`, `viewer.py` (viewerdetectie + geldigheidsdatums), `validate.py`, CLI `python -m folders validate \| bronnen`; 25 tests | deze repo |
| Workflows | `validatie-folders.yml` (handmatig; environment `preview`; code van `ref`/`FOLDERS_REF`) en `foldermonitor-preview.yml` (cron ma–za 05:23 NL-zomertijd; **inert** tot de variabele `FOLDERS_REF` gezet is) | `.github/workflows/` |
| Netlify | variabelen `PREVIEW_SUPABASE_URL` en `PREVIEW_SUPABASE_ANON_KEY` (context all); `dashboard/build.sh` kiest het preview-project zodra Netlify's `CONTEXT` ≠ `production` (deploy previews en branch deploys). Productievariabelen niet aangeraakt. Dashboard toont een PREVIEW-badge. | site `concurrentiemonitor-terstal` |
| Weekrapport / scraper | **ongewijzigd** | — |

Mechanismekeuze Netlify: geen branch-scoped waarden op de bestaande `SUPABASE_*`-variabelen (risico op een productiebuild zonder waarde), maar een expliciete schakeling in `build.sh` op de deploy-context. Gevolg: **geen enkele deploy preview leest nog productie**; tot fase 1 toont een preview dus een leeg dashboard achter de login van het preview-project.

## Logboek 07-09 — PR #37 gemerged, mailbox en secrets bewezen, bronnen gevalideerd

- **Eigenaar:** mailbox ingericht (2-staps-verificatie, app-wachtwoord; IMAP staat in Gmail tegenwoordig altijd aan) en Environment `preview` met de drie secrets gevuld. Checklist A.1–A.3 en B zijn daarmee af.
- **PR #37** gemerged naar `main` (b5a9c8a, 10:24 NL-tijd). Productie ongewijzigd; de weekscrape van die ochtend was door GitHub overgeslagen en is om 10:24 handmatig gestart (zelfde route en poort als op 04-09).
- **Validatie folders**: drie runs, eindoordeel per bron in [docs/validaties/2026-09-07-folders-fase0-validatie.md](validaties/2026-09-07-folders-fase0-validatie.md). Kort: KiK 🟢 (Publitas), terStal/Zeeman/Action 🟠 (render-route), Wibra/HEMA 🔴 (403, viewer-URL uit de nieuwsbrief), vier bronnen mail-only. De render-route wordt daarmee de hoofdroute van fase 1.
- **Mailboxcontrole** in elke run: login geslaagd, 9 Google-systeemmails, nog geen retailer. Open: inschrijven per bron (A.4) en de Auth-instellingen op het preview-project (C).
- **Detectie verbeterd** (PR #38): JSON-URL's, embed-scripts, folder-pdf-kenmerk, kandidaat-URL's en folderlinks één stap diep; Zeeman's `folder_url` staat nu op `/nl-nl/over-zeeman/folder`.

## Logboek 06-09 — mailbox gekozen; B en C blijven eigenaarsklikken

- **Mailbox (A) is gekozen.** Het domein draait op Google Workspace (MX `smtp.google.com`, SPF `_spf.google.com`): IMAP op `imap.gmail.com`, app-wachtwoord na 2-staps-verificatie en plus-aliassen werken precies als bij Gmail, dus plan §4.1 blijft staan. Het adres stuurt niet door naar een persoonlijke mailbox (gecontroleerd). Omdat deze repo **publiek** is, komt het adres nergens in code, docs, workflows, PR-tekst of Actions-logs — alleen in het secret.
- **GitHub-secrets (B): niet vanuit deze sessie te zetten.** De API-paden voor environments en secrets zijn hier geblokkeerd (proxy: *"Access to this GitHub API path is not permitted"*) en de GitHub-koppeling heeft er geen tool voor. Wat wél kon om handelingen te schrappen: `FOLDERS_SUPABASE_URL` heeft een terugval in de workflow (de preview-URL is al openbaar) en de IMAP-host een standaard in de code. Er blijven **drie** secrets over (tabel B).
- **Supabase-auth (C): niet vanuit deze sessie te zetten.** De Supabase-koppeling biedt SQL en migraties, maar geen auth-instellingen (Site URL, redirects, signups) en geen uitnodigingen — die vragen het dashboard. Wat wél kon: één redirect-patroon dat álle deploy previews en branch deploys dekt, zodat C.2 eenmalig is; en de drie genodigden staan klaar in het productieproject (Authentication → Users).
- **Nieuw: `python -m folders mailbox`** — alleen-lezen IMAP-controle (login, aantal berichten, bronherkenning van de laatste 10 mails; geen adres en geen onderwerpen in de uitvoer). De workflow "Validatie folders" draait hem automatisch zodra de IMAP-secrets bestaan: daarmee zijn A en B in één run bewezen.

Live-test van de weeklogica op het preview-project (testdata daarna verwijderd): een Action-folder wo 02-09 t/m di 08-09 telt alleen in week 37 (maandag 07-09), een Wibra-folder 31-08 t/m 13-09 in week 36 én 37; `process_folder_week` levert per groep aantal, mediaan, prijs per stuk en multibuy-aandeel.

## Eigenaarsacties (checklist, ±30 minuten totaal)

### A. Mailbox (±20 min) — Google Workspace-gebruiker
1. Het adres is een **eigen Workspace-gebruiker**, geen alias van een persoonlijke mailbox: het app-wachtwoord geeft de sweep toegang tot de héle mailbox waar het aan hangt.
2. Voor die gebruiker: Google-account → Beveiliging → **2-staps-verificatie aan** → daarna **App-wachtwoorden** → naam "foldermonitor" → het 16-tekenwachtwoord wordt `FOLDER_IMAP_PASSWORD`. (Beheerconsole, alleen als de knop ontbreekt: Apps → Google Workspace → Gmail → Toegang voor eindgebruikers → IMAP toestaan; staat standaard aan.)
3. Gmail van die gebruiker → Instellingen → Doorsturen en POP/IMAP → **IMAP inschakelen**.
4. Inschrijven op de nieuwsbrief per bron met plus-alias `<lokaal>+<alias>@<domein>` (weigert een formulier de `+`, gebruik dan het kale adres — de sweep herkent de bron ook aan het afzenderdomein):

| Bron | Alias | Waar inschrijven |
|---|---|---|
| terStal | `+terstal` | terstal.nl, nieuwsbrief (onderaan de site) |
| Zeeman | `+zeeman` | zeeman.com/nl-nl, nieuwsbrief |
| Wibra | `+wibra` | wibra.nl, nieuwsbrief/folder |
| Action | `+action` | action.com/nl-nl, nieuwsbrief |
| HEMA | `+hema` | hema.nl, nieuwsbrief |
| KiK | `+kik` | kik.nl, nieuwsbrief |
| C&A | `+c-and-a` | c-and-a.com/nl, nieuwsbrief |
| Primark | `+primark` | primark.com/nl-nl, nieuwsbrief |
| Lidl / Aldi (fase 2) | `+lidl` / `+aldi` | pas bij activering |

5. Niets verder doen: de mails blijven staan; de sweep (fase 1) leest ze en verwijdert nooit. De bevestigingsmails ("bevestig je inschrijving") wél even aanklikken.

### B. GitHub (±5 min) — Settings → Environments → **New environment** → naam `preview` → *Add environment secret*

| Secret | Waarde | Nodig vanaf |
|---|---|---|
| `FOLDER_IMAP_USER` | het neutrale adres (A) | nu — mailboxcontrole |
| `FOLDER_IMAP_PASSWORD` | het app-wachtwoord uit A.2 | nu — mailboxcontrole |
| `FOLDERS_SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → project **concurrentiemonitor-preview** → Project Settings → API Keys → *service_role* (geheim; alleen hier plakken) | fase 1 — de sweep schrijft |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API keys | fase 2 — extractie |

Niet meer nodig: `FOLDERS_SUPABASE_URL` (de workflow valt terug op de preview-URL) en `FOLDER_IMAP_HOST` (standaard `imap.gmail.com`; alleen als variabele zetten als de host ooit afwijkt).

Repository-variabele `FOLDERS_REF`: **nog niet zetten** — pas bij fase 1, als de integratiebranch `foldermonitor` bestaat; tot die tijd blijft de dagelijkse workflow overgeslagen.

### C. Supabase preview-project (±3 min) — Dashboard → **concurrentiemonitor-preview** → Authentication
1. Sign In / Providers → **Email**: aan; *Allow new users to sign up*: **uit** (het dashboard logt in met een magic link en maakt zelf nooit accounts aan).
2. URL Configuration → **Site URL**: `https://deploy-preview-37--concurrentiemonitor-terstal.netlify.app` (vanaf fase 1: `https://foldermonitor--concurrentiemonitor-terstal.netlify.app`). **Redirect URLs**: één patroon toevoegen: `https://*--concurrentiemonitor-terstal.netlify.app/**` — dekt elke deploy preview én branch deploy, hoeft nooit opnieuw.
3. Users → **Invite user**: dezelfde drie accounts als in productie (productieproject → Authentication → Users). De uitnodigingsmail linkt naar de Site URL uit stap 2 — dus eerst 2, dan 3.

### D. Netlify (±2 min, pas bij fase 1)
Site configuration → Build & deploy → Branches and deploy contexts → branch deploys: branch `foldermonitor` toevoegen zodra die bestaat. Deploy previews staan al aan.

### E. Validatie draaien — **gedaan 07-09** (drie runs; opnieuw draaien na het inschrijven, dan toont de mailboxcontrole de bronnen)
Actions → **"Validatie folders"** → Run workflow (velden leeg laten). Het rapport in de job-samenvatting geeft per bron de viewer en de capture-route, en — zodra de IMAP-secrets uit B bestaan — de mailboxcontrole (login geslaagd, aantal mails, herkende bronnen); leg het eindoordeel per bron vast in `docs/validaties/` met het run-id. Verzamel daarnaast handmatig **drie folder-PDF's** (om het even welke bron) in één map — de eerste testset voor fase 2.

## Volgende stap: fase 1 (archief)
- Integratiebranch `foldermonitor` aftakken van `main` zodra PR #37 gemerged is; `FOLDERS_REF=foldermonitor` zetten; branch deploy aanzetten (D).
- Bouwen: IMAP-sweep (`python -m folders sweep`), capture per viewer-route op basis van het validatierapport, registratie in `folders` + Storage, upload-vangnet, dashboardpagina `folders.html` met viewer en aanwezigheidskalender.
- Klaar als: maandag ligt van elke kernbron de folder van die week in het preview-archief.

## Aannames en risico's in fase 0
- De `folder_url`'s in `bronnen.yml` zijn startaannames; de validatierun bewijst ze. Wibra/HEMA weren datacenter-IP's op hun eigen domein — daar verwachten we rood op de folderpagina en hopen we op groen op het viewerdomein.
- Plus-aliassen worden niet door elk inschrijfformulier geaccepteerd; de bronherkenning valt dan terug op het afzenderdomein (`mail_from`).
- Google kan app-wachtwoorden voor Workspace-accounts beperken (beheerdersbeleid). Werkt de IMAP-login niet, dan is het alternatief uit plan §4.1 de Gmail API met OAuth — zelfde resultaat, meer inrichting. De mailboxcontrole in "Validatie folders" laat dit direct zien.
- De mailboxcontrole en de sweep gebruiken het app-wachtwoord van één Workspace-gebruiker; die gebruiker mag daarom niets anders bevatten dan retailmail.
- Het preview-project pauzeert na 7 dagen zonder activiteit (gratis tier); de dagelijkse sweep houdt het wakker vanaf fase 1. Tot die tijd: bij een gepauzeerd project in het Supabase-dashboard op *Restore* klikken.
