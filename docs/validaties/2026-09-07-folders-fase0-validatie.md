# Foldermonitor fase 0 — validatie folderbronnen en mailbox (07-09-2026)

*Hoort bij [docs/foldermonitor-fase0.md](../foldermonitor-fase0.md) (checklist E) en plan §4.4. Drie runs van de workflow "Validatie folders", alle op 07-09 tussen 10:25 en 10:34 NL-tijd.*

| Run | Code | Bronnen | Wat het opleverde |
|---|---|---|---|
| [34100477338](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/34100477338) | `main` b5a9c8a (PR #37) | alle | eerste beeld; Zeeman-URL fout, Action zonder link, KiK's `embed.js` als "viewer" |
| [34100906220](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/34100906220) | branch 97f10bf | zeeman, action, kik, terstal | JSON-URL's en kandidaat-URL's: KiK's Publitas-account gevonden; Zeeman's "pdf" bleek een kwaliteitsrapport |
| [34101189860](https://github.com/nlklund2/Concurrentie-analyse/actions/runs/34101189860) | branch 7bb28ec | alle | folder-pdf-kenmerk, folderlinks één stap gevolgd, beste kandidaat gekozen — **eindbeeld hieronder** |

## Eindoordeel per bron (run 34101189860)

| Bron | Folderpagina | Uitkomst | Capture-route fase 1 | Status |
|---|---|---|---|---|
| terStal | terstal.nl/folder | 200; ook `/uit-de-folder/…` (3 ontdekt): nergens pdf, viewer of paginabeelden; de viewer wordt door JS opgebouwd | **render** (headless browser); alternatief: viewer-URL uit de nieuwsbrief seeden | 🟠 |
| Zeeman | zeeman.com/nl-nl/over-zeeman/folder | `/nl-nl/folder` bestaat niet; `/nl-nl/aanbiedingen` antwoordt (2 pdf's zonder folderkenmerk, o.a. een kwaliteitsrapport) en linkt naar `/nl-nl/over-zeeman/folder`, dat ook antwoordt — beide zonder herkenbare viewer | **render**; `folder_url` is nu `over-zeeman/folder`, `aanbiedingen` blijft kandidaat | 🟠 |
| Wibra | wibra.nl/folder | HTTP 403 (datacenter-IP geweerd, zoals de monitor sinds 07-08) | viewer-URL uit de nieuwsbrief (ander domein); anders Firecrawl of upload | 🔴 |
| HEMA | hema.nl/folder | HTTP 403, idem | idem | 🔴 |
| Action | action.com/nl-nl/folder/ | 200; "publitas" komt voor in de pagina, maar geen enkele Publitas-URL, ook niet JSON-escaped: de viewer-URL wordt door de pagina-JS opgehaald | **render** die de Publitas-URL uit de pagina-JS/het netwerk haalt; alternatief: seed uit de nieuwsbrief | 🟠 |
| KiK | kik.nl/Online-folder | 200; Publitas-account `view.publitas.com/kik-textilien-und-non-food-gmbh` bereikbaar (199 KB) | **publitas**: laatste publicatie uit de accountpagina, daarna paginabeelden | 🟢 |
| Primark, C&A | mail-only | geen folder te capturen | sweep registreert de mailing (kalendersignaal) | ⚪ |
| Lidl, Aldi | uit | pas bij activering (fase 2) | — | ⚪ |

**Gevolg voor fase 1:** de render-route (headless browser) is niet de uitzondering maar de hoofdroute — drie van de zes webbronnen hebben hem nodig (terStal, Zeeman, Action). Bouwvolgorde: KiK via Publitas (goedkoop, bewezen bereikbaar) → render-capture voor terStal/Zeeman/Action → Wibra/HEMA via de viewer-URL's uit de nieuwsbrief zodra die binnenkomen. Playwright staat al in `foldermonitor-preview.yml`.

## Mailboxcontrole (alle drie de runs)

- IMAP-login op `imap.gmail.com` geslaagd met de secrets uit Environment `preview` → checklist A.2/A.3 en B zijn bewezen.
- 9 berichten in de inbox, allemaal Google-systeemmail (accounts.google.com / google.com); nog geen retailer herkend.
- Volgende stap: inschrijven per bron met plus-alias (checklist A.4). De eerstvolgende validatierun laat per afzenderdomein zien welke bron binnenkomt.

## Wat de runs aan de detectie veranderden (PR #38)

- Kale en JSON-escaped viewer-/pdf-URL's uit script-blokken worden gelezen; `embed.js` en andere scripts tellen niet als folderlink.
- Alleen pdf's met een folderkenmerk in het pad (`folder`, `brochure`, `week`, `aanbieding`, …) gelden als folder.
- `folder_url_kandidaten` per bron; `validate_one` probeert `folder_url`, de kandidaten en de folderlinks die een pagina zelf noemt (max. 3, één stap diep), scoort elke pagina en kiest de beste. Requests per bron: 1–8, met 1 s tussenruimte.
