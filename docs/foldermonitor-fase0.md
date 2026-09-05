# Foldermonitor — fase 0: logboek en eigenaarschecklist

*Stand: 5 september 2026. Hoort bij [foldermonitor-plan.md](foldermonitor-plan.md) (§9.5 preview naast productie, §13 roadmap).*

## Besluiten van de eigenaar (05-09)

| # | Besluit | Uitkomst |
|---|---|---|
| 1 | Mailbox | **nieuw neutraal Gmail-adres** met plus-aliassen per bron |
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

Live-test van de weeklogica op het preview-project (testdata daarna verwijderd): een Action-folder wo 02-09 t/m di 08-09 telt alleen in week 37 (maandag 07-09), een Wibra-folder 31-08 t/m 13-09 in week 36 én 37; `process_folder_week` levert per groep aantal, mediaan, prijs per stuk en multibuy-aandeel.

## Eigenaarsacties (checklist, ±50 minuten totaal)

### A. Mailbox (±30 min)
1. Nieuw Gmail-account met neutrale naam (niet naar terStal herleidbaar). **2-staps-verificatie aan.**
2. Google-account → Beveiliging → **App-wachtwoorden** → wachtwoord voor "Mail" aanmaken (dit wordt `FOLDER_IMAP_PASSWORD`).
3. Gmail → Instellingen → Doorsturen en POP/IMAP → **IMAP inschakelen**.
4. Inschrijven op de nieuwsbrief per bron, met plus-alias (weigert een formulier de `+`, gebruik dan het kale adres — de sweep herkent de bron ook aan het afzenderdomein):

| Bron | Adres | Waar inschrijven |
|---|---|---|
| terStal | `<adres>+terstal@gmail.com` | terstal.nl, nieuwsbrief (onderaan de site) |
| Zeeman | `<adres>+zeeman@gmail.com` | zeeman.com/nl-nl, nieuwsbrief |
| Wibra | `<adres>+wibra@gmail.com` | wibra.nl, nieuwsbrief/folder |
| Action | `<adres>+action@gmail.com` | action.com/nl-nl, nieuwsbrief |
| HEMA | `<adres>+hema@gmail.com` | hema.nl, nieuwsbrief |
| KiK | `<adres>+kik@gmail.com` | kik.nl, nieuwsbrief |
| C&A | `<adres>+c-and-a@gmail.com` | c-and-a.com/nl, nieuwsbrief |
| Primark | `<adres>+primark@gmail.com` | primark.com/nl-nl, nieuwsbrief |
| Lidl / Aldi (fase 2) | `+lidl` / `+aldi` | pas bij activering |

5. Niets verder doen: de mails blijven staan; de sweep (fase 1) leest ze en verwijdert nooit.

### B. GitHub (±10 min) — Settings → Secrets and variables → Actions
Environment **`preview`** (wordt ook automatisch aangemaakt bij de eerste run van een workflow die ernaar verwijst):

| Secret | Waarde |
|---|---|
| `FOLDERS_SUPABASE_URL` | `https://kptmymvxqhrfmnzmurbk.supabase.co` |
| `FOLDERS_SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard → project **concurrentiemonitor-preview** → Project Settings → API → *service_role* (geheim; alleen hier) |
| `FOLDER_IMAP_USER` | het nieuwe Gmail-adres |
| `FOLDER_IMAP_PASSWORD` | het app-wachtwoord uit A.2 |
| `ANTHROPIC_API_KEY` | pas nodig in fase 2 |

Repository-variabele `FOLDERS_REF`: **nog niet zetten** — pas bij fase 1, als de integratiebranch `foldermonitor` bestaat; tot die tijd blijft de dagelijkse workflow overgeslagen.

### C. Supabase preview-project (±5 min)
1. Authentication → Providers → Email: aan; *Allow new users to sign up* uit.
2. Authentication → URL Configuration → Site URL: de preview-URL van het dashboard (nu `https://deploy-preview-37--concurrentiemonitor-terstal.netlify.app`; vanaf fase 1 de branch-URL `https://foldermonitor--concurrentiemonitor-terstal.netlify.app`). Voeg beide toe als redirect-URL.
3. Authentication → Users → Invite user: dezelfde genodigden als in productie.

### D. Netlify (±2 min, pas bij fase 1)
Site configuration → Build & deploy → Branches and deploy contexts → branch deploys: branch `foldermonitor` toevoegen zodra die bestaat. Deploy previews staan al aan.

### E. Validatie draaien (zodra PR #37 op `main` staat)
Actions → **"Validatie folders"** → Run workflow (velden leeg laten). Het rapport in de job-samenvatting geeft per bron de viewer en de capture-route; leg het eindoordeel per bron vast in `docs/validaties/` met het run-id. Verzamel daarnaast handmatig **drie folder-PDF's** (om het even welke bron) in één map — de eerste testset voor fase 2.

## Volgende stap: fase 1 (archief)
- Integratiebranch `foldermonitor` aftakken van `main` zodra PR #37 gemerged is; `FOLDERS_REF=foldermonitor` zetten; branch deploy aanzetten (D).
- Bouwen: IMAP-sweep (`python -m folders sweep`), capture per viewer-route op basis van het validatierapport, registratie in `folders` + Storage, upload-vangnet, dashboardpagina `folders.html` met viewer en aanwezigheidskalender.
- Klaar als: maandag ligt van elke kernbron de folder van die week in het preview-archief.

## Aannames en risico's in fase 0
- De `folder_url`'s in `bronnen.yml` zijn startaannames; de validatierun bewijst ze. Wibra/HEMA weren datacenter-IP's op hun eigen domein — daar verwachten we rood op de folderpagina en hopen we op groen op het viewerdomein.
- Gmail's plus-aliassen worden niet door elk inschrijfformulier geaccepteerd; de bronherkenning valt dan terug op het afzenderdomein (`mail_from`).
- Het preview-project pauzeert na 7 dagen zonder activiteit (gratis tier); de dagelijkse sweep houdt het wakker vanaf fase 1. Tot die tijd: bij een gepauzeerd project in het Supabase-dashboard op *Restore* klikken.
