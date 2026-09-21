# Weekmail voor de inkoopmanager — voorstel

*Status: 14 september 2026 — akkoord van de opdrachtgever (mail rond 07:00; weekrun vervroegd naar 03:07 NL-tijd). Versie 1 gebouwd op branch `weekmail`: `scraper/signals.py`, `scraper/weekmail.py`, dashboardpaneel en deep links, `sql/migratie_weekmail.sql`. Opsteller: Jurjen. Lezers: de inkoopmanager (eigenaar van het maandagritueel, PLAN.md §6.1) en de opdrachtgever.*

**In één zin:** elke maandag rond 07:00 één automatische mail van drie minuten, die eerst het oordeel geeft (drie zinnen), daarna per concurrent de hoofdlijn, dan de prijspositie en de trend van de afgelopen zes weken, en eindigt in maximaal drie agendapunten voor het overleg van 09:15.

Het weekrapport in `reports/` blijft bestaan als naslag. De mail is de **voorkant**: wat de inkoopmanager op de telefoon leest voordat het overleg begint.

---

## 0. Samenvatting voor de beslisser

**Wat er nu is.** De weekrun mailt het complete markdown-rapport als monospace-tekst (`send_email` in `scraper/report.py`). Dat is ±120 regels tabel, ongesorteerd, zonder trend, alleen leesbaar op een groot scherm. Het beantwoordt niet de vraag "wat moet ik maandag weten?".

**Wat het wordt.** Een mail met zes vaste blokken, van oordeel naar detail:

| # | Blok | Beantwoordt | Doorklik naar dashboardsectie |
|---|---|---|---|
| 1 | **In drie zinnen** | Wat is er deze week écht gebeurd, en houdt het aan? | Signalen van de week |
| 2 | **Concurrentenkaart** | Per concurrent één hoofdlijn plus zes weken sale-druk en omvang | Assortimentsomvang per week · Gezondheid van de bronnen |
| 3 | **Prijspositie per stuk** | Waar staat terStal per groep, en wat verschoof in vier weken? | Prijsindex per groep (per stuk) |
| 4 | **Trendlijnen** | Drie reeksen over zes weken: prijsverlagingen, sale-druk, eigen omvang | Mediaanprijs per week · Grootste prijsverlagingen |
| 5 | **Spiegel** | Wat veranderde er bij terStal zelf (bewust of per ongeluk)? | Artikel-explorer, gefilterd op terStal |
| 6 | **Voor maandag 09:15** | Maximaal drie agendapunten; antwoord met 1, 2 of 3 | — (besluitenlog in de repo) |

**Uitgangspunt: de mail is de maandagsamenvatting van het dashboard** (§2). Zelfde Supabase-views, zelfde definities, zelfde bronkleuren; elk blok linkt naar zijn dashboardsectie met de week voorgeselecteerd, en de laatst verstuurde mail staat als paneel in het dashboard zelf.

**Wat het slim maakt** (uitgewerkt in §4): signalen worden gerangschikt op omvang × verandering × **persistentie** (nieuw / houdt aan / trend); kleine groepen en rode bronnen komen nooit in de top-3; een prijssprong die alleen in de artikelprijs zit en niet in de prijs per stuk wordt herkend als **verpakkingswissel** (KiK, week 36); nieuwe artikeltitels leveren **trendwoorden** (deze week: thermoshirt bij drie bronnen, kerstpyjama bij twee); elke mail kijkt terug op de signalen van vorige week (bevestigd / teruggedraaid); een week zonder signalen levert een mail van vijf regels.

**Verzending.** Afzender: het adres van de opsteller (extern domein, geverifieerd bij Resend). Ontvangers: de inkoopmanager en één collega, uitsluitend in het GitHub-secret `REPORT_EMAIL_TO` — nooit in deze publieke repo. Antwoorden komen bij de opsteller terecht (reply-to) en voeden de actieteller.

**Bouw en planning.** Twee dagdelen voor versie 1, één dagdeel voor versie 1.1. Proefmail donderdag 17-09 naar de opsteller; eerste echte mail maandag 21-09 (week 39); drie weken proef; evaluatie maandag 12-10. Kosten: €0 (Resend gratis tier, 3.000 mails per maand).

**Besluiten die voorliggen:** (1) akkoord op het concept en de zes blokken; (2) de opsteller zet drie DNS-records op het afzenddomein (15 minuten); (3) ontvangers bevestigd; (4) de inkoopmanager beantwoordt de mail wekelijks met 1, 2 of 3 — dat is de actieteller uit PLAN.md §11E.

---

## 1. Waarom deze vorm

Het beslisritme uit PLAN.md §1 is leidend: rapport om 09:00, overleg om 09:15, maximaal drie acties. Een mail die daarbij past is:

- **Kort en gelaagd.** Het oordeel staat in de onderwerpregel en de eerste drie zinnen. Wie meer wil, scrolt; wie nog meer wil, klikt door naar rapport en dashboard.
- **Trend boven momentopname.** Eén week is ruis. De mail toont per signaal of het nieuw is, of het voor de tweede week aanhoudt, of dat het een trend van drie weken of langer is. Zes weken historie staat als tekst-sparkline naast elk cijfer.
- **Toegankelijk zonder plaatjes.** Geen afbeeldingen (die worden in Outlook en Gmail standaard geblokkeerd), geen grafieken die je moet kunnen zien. Sparklines zijn tekst (▁▂▃▅▇), kleur staat nooit alleen (altijd een teken of woord erbij), tabellen zijn echte tabellen, er is een platte-tekstversie, en de lay-out is één kolom van 600 px die op een telefoon werkt.
- **Eerlijk over de bron.** Een bron die rood of oranje staat, levert die week geen cijfers aan de mail; de laatste goede week wordt getoond mét label ("Zeeman: stand W37"). Nooit stilzwijgend mengen.
- **Eindigt in een besluit.** Maximaal drie agendapunten, geformuleerd als vraag. De ontvanger antwoordt met 1, 2 of 3; de opsteller legt het vast in `reports/besluiten.md`. Daarmee is de succesvraag uit PLAN.md §6.9 na acht weken te beantwoorden.

## 2. Eén bron, twee vensters — de mail volgt het dashboard

Het dashboard (`concurrentiemonitor-terstal.netlify.app`, achter de inloglink) wordt elke maandag door de weekrun bijgewerkt en leest rechtstreeks uit Supabase. De mail is geen tweede rapport ernaast, maar de **maandagsamenvatting van datzelfde dashboard**:

- **Dezelfde data.** De mail wordt gebouwd uit precies de views die het dashboard leest: `weekly_stats`, `v_retailer_week_totals`, `price_events`, `weekly_articles` en `scrape_runs`. Een cijfer in de mail is altijd terug te vinden in het dashboard, in dezelfde week en met dezelfde filters (doelgroep × producttype).
- **Dezelfde definities en kleuren.** Mediaan, instapniveau (p25), sale-druk, prijs per stuk en de prijsindex komen uit dezelfde formules als in het dashboard. Elke bron houdt zijn vaste grafiekkleur (`color_slot` in `retailers.yml`), zodat KiK in de mail dezelfde kleur draagt als in de grafieken.
- **Elk blok linkt naar zijn dashboardsectie**, met de week voorgeselecteerd: blok 1 → *Signalen van de week*; blok 2 → *Assortimentsomvang per week* en *Gezondheid van de bronnen*; blok 3 → *Prijsindex per groep* met "per stuk" aan; blok 4 → *Mediaanprijs per week* en *Grootste prijsverlagingen*; blok 5 → *Artikel-explorer* gefilterd op terStal; trendwoorden → *Nieuw deze week*. Kleine aanpassing aan het dashboard: week, sectie en filters uit de URL lezen (`?week=2026-09-14&bron=kik#prijsindex`), ook ná de inloglink.
- **De mail staat óók in het dashboard.** Een paneel *Weekmail* bovenaan toont de laatst verstuurde mail (dezelfde HTML, uit `reports/`). Wie de mail kwijt is of hem niet ontvangt, ziet in het dashboard precies hetzelfde; en de proefmail wordt eerst dáár bekeken voordat hij de deur uit gaat.
- **Eén volgorde van waarheid.** Weekrun → Supabase → dashboard én mail. De mail wordt pas gebouwd nadat de weekverwerking klaar is en leest de database, niet de tussenbestanden van de scraper. Wordt een week later geschoond en opnieuw verwerkt (zoals KiK in week 36), dan trekt één handmatige run met `alleen_rapport` mail en dashboard weer gelijk.

## 3. Anatomie van de mail

Voorbeeld met de echte cijfers van week 38 (peildatum 14-09-2026) staat in de bijgeleverde HTML-mock-up; hieronder de vaste opbouw.

### Onderwerpregel

`W38 · Winter stroomt in bij 3 concurrenten · KiK ruimt op · terStal −70 artikelen · 7/8 bronnen ok`

De onderwerpregel is de samenvatting: week, drie kernwoorden, bronstatus. In een rustige week: `W40 · Rustige week, geen signalen boven de drempel · 8/8 bronnen ok`.

### Kop

Naam, weeknummer, peildatum, leestijd, en één statusregel over de bronnen. Staat een bron rood, dan staat dat hier, niet onderaan.

### Blok 1 — In drie zinnen

De drie hoogst scorende signalen, elk als één zin met cijfers en een persistentie-tag:

- **Winter komt binnen.** Thermoshirts stromen in bij 3 concurrenten en kerstpyjama's bij 2 (12 artikelen). *nieuw*
- **KiK ruimt op.** Sale-druk daalt voor de derde week (51 → 49 → 46%), maar dames nachtmode staat al drie weken op ±80% afgeprijsd met mediaan €4,99. *trend, 3 wk*
- **terStal zelf: 70 artikelen weg, 0 nieuw.** Instap dames ondergoed van €5,00 naar €6,99 doordat de €5-artikelen verdwenen; herensokken van 31 naar 18. Bewust, of een websiteprobleem? *nieuw, eigen huis*

### Blok 2 — Concurrentenkaart

Eén rij per concurrent, kernconcurrenten eerst (Zeeman, Wibra, KiK, Primark, Action, HEMA, C&A): hoofdlijn in één zin, sinds wanneer, sale-druk over zes weken als sparkline plus huidig percentage, omvang over zes weken als sparkline plus huidig aantal. Dit is het blok "hoofdlijnen bij de concurrenten": de zinnen komen uit regels (§4.5), niet uit een taalmodel, zodat elke zin herleidbaar is naar een cijfer.

### Blok 3 — Prijspositie per stuk (terStal = 100)

Vijf kerngroepen × zes concurrenten, index op prijs per stuk (multipacks omgerekend, PLAN.md §2). Cel = index + teken: ▼ concurrent goedkoper (< 90), ● gelijk (90–110), ▲ concurrent duurder (> 110). Een pijl erachter als de index in vier weken meer dan 10 punten verschoof. Onder de tabel één zin die de tabel samenvat.

### Blok 4 — Trendlijnen (zes weken)

Drie tegels met cijfer, sparkline en duiding: prijsverlagingen per week over alle bronnen; sale-druk van de kernvechter met de grootste beweging; omvang van terStal zelf.

### Blok 5 — Spiegel: terStal zelf

Wat er in het eigen assortiment gebeurde: in- en uitstroom, instapniveaus, eigen prijsverlagingen. Met de vraag of dat klopt met de planning — de monitor ziet de website, niet het inkoopbesluit.

### Terugblik op vorige week

De drie signalen van vorige week met de uitkomst van deze week: **houdt aan**, **teruggedraaid** (ruis) of **niet meetbaar** (bron rood). Dit bouwt vertrouwen: de lezer ziet dat de mail zichzelf controleert.

### Blok 6 — Voor maandag 09:15

Maximaal drie agendapunten als vraag, afgeleid van blok 1. Daaronder: "Antwoord op deze mail met 1, 2 of 3 = het punt dat je oppakt" en de stand van de actieteller (weken op rij met ≥ 1 besluit).

### Voettekst

Links naar het volledige weekrapport (GitHub), het dashboard (Netlify, login; elk blok hierboven heeft al zijn eigen doorklik) en de CSV-export; de vaste disclaimer (online assortiment, trendindicatie, geen winkeltelling); tijdstip van samenstellen; "vragen: antwoord op deze mail".

## 4. Het slimme eronder — de regels

Alles hieronder rekent op data die er al ligt (`weekly_stats`, `v_retailer_week_totals`, `price_events`, `weekly_articles`, `scrape_runs`). Geen extra scrapes, geen taalmodel in de weekrun.

### 4.1 Signaalscore met persistentie

Elk signaal uit het weekrapport (omvang, mediaan, instapniveau, sale-druk) krijgt een score:

`score = |verandering| × log(groepsgrootte) × persistentiefactor`

- **Persistentie:** dezelfde richting in de vorige week ook → "houdt aan" (×1,5); drie weken of langer → "trend" (×2). Alleen deze week → "nieuw" (×1).
- **Ruisfilter:** groepen kleiner dan 15 artikelen en bronnen met status ≠ ok komen niet in de top-3 en niet in de onderwerpregel; ze blijven wel zichtbaar in het weekrapport. Voorbeeld: HEMA dames ondergoed (17–29 artikelen) schommelt tussen €8,99 en €16,49 — dat is geen trend, dat is een kleine groep.
- **Eigen huis apart:** terStal-signalen concurreren niet met concurrentsignalen om de drie plekken; het sterkste terStal-signaal krijgt altijd blok 5 en mag één van de drie zinnen zijn.

### 4.2 Verpakkingswissel-detectie

Stijgt `price_median` met meer dan 25% terwijl `unit_price_median` binnen 5% blijft en `multipack_share` springt, dan is het geen prijsverhoging maar een andere presentatie. Week 36 bij KiK: artikelprijs herensokken van €0,80 naar €2,99, prijs per stuk onveranderd €0,80, multipack-aandeel van 0% naar 100%. Het weekrapport meldde toen tien "prijsverhogingen" van +100% tot +274%. De mail zegt: "KiK toont sinds W36 verpakkingsprijzen; per stuk ongewijzigd."

### 4.3 Trendwoorden op instroom

Woordfrequentie op titels van artikelen die deze week voor het eerst gezien zijn (`products.first_seen = week`), geteld per bron; een woord telt als het bij ≥ 2 bronnen voorkomt. Week 38: pyjama (5 bronnen, 50 artikelen), thermoshirt (3), sportsokken (3), ribstof (3), kerstpyjama (2, 12 artikelen), naadloze (2), bralettes (2). Dit is de "trendradar" uit PLAN.md §7, en na een jaar de basis van de seizoensklok ("kerstpyjama's dit jaar in W38, vorig jaar in W40").

### 4.4 Betrouwbaarheidsregel

Per bron geldt de laatste `scrape_runs.status`. Bij `fout` of `afwijkend`: geen cijfers van die week in de mail; de laatste goede week wordt getoond met label en de bron krijgt een vaste regel in de concurrentenkaart ("geen meting; laatste beeld W37"). De statusregel in de kop telt groen/rood.

### 4.5 Concurrentenkaart uit regels

Per concurrent worden de kandidaat-zinnen uit sjablonen gevuld en op score gesorteerd; de hoogste wordt de hoofdlijn, de tweede komt erachter als bijzin. Sjablonen (eerste set):

| Regel | Voorwaarde | Zin |
|---|---|---|
| Sale-trend | sale-druk 3 wk dezelfde richting | "Sale-druk daalt voor de derde week (51 → 49 → 46%)" |
| Opruiming | groep met sale-druk ≥ 60% en mediaan gedaald | "Dames nachtmode 80% afgeprijsd, mediaan €4,99" |
| Uitbouw / sanering | omvang groep ±25% in ≤ 2 wk, groep ≥ 15 | "Bouwt dames ondergoed uit: 110 → 255 in twee weken" |
| Stille inflatie | instapniveau 3 stappen omhoog in ≤ 4 wk | "Instap dames nachtmode in vier weken van €10 naar €13" |
| Krimp | totale omvang 4+ wk dalend | "Krimpt online al vijf weken (129 → 110)" |
| Prijsvast | mediaan kerngroepen ≥ 6 wk gelijk | "Prijsvast; doorloop 13% in / 18% uit" |
| Draaideur | instroom én uitstroom ≥ 40% van de omvang | "Online is een draaideur; het verhaal zit in de folder" |
| Verpakkingswissel | §4.2 | "Toont sinds W36 verpakkingsprijzen; per stuk ongewijzigd" |
| Geen meting | status ≠ ok | "Geen meting (HTTP 403); laatste beeld W37" |

Nieuwe regels zijn een sjabloon plus een test. De set groeit met wat het overleg bruikbaar vindt.

### 4.6 Terugblik

De top-3 van vorige week wordt bewaard (JSON naast het rapport). Deze week wordt per signaal dezelfde meting herhaald: zelfde richting → "houdt aan"; tegengestelde richting → "teruggedraaid (ruis)"; bron rood → "niet meetbaar". Week 37 → 38: C&A dames ondergoed 251 → 255 houdt aan; KiK dames nachtmode €4,99 houdt aan; HEMA dames ondergoed €12,29 → €8,99 teruggedraaid.

### 4.7 Rustige-week-modus

Geen signaal boven de drempels en geen rode bron → mail van vijf regels: onderwerp "Rustige week", bronstatus, de drie trendtegels, terugblik, link. Geen lege blokken. De lezer leert dat een lange mail iets betekent.

### 4.8 Folderregel (zodra de foldermonitor draait)

De foldermonitor staat on hold (docs/foldermonitor-fase0.md). Tot die tijd staat in de concurrentenkaart bij Zeeman en Action een vaste regel: "Promotie loopt via de folder; online 0% sale" met de link naar de folderpagina. Zodra de foldermonitor live is, wordt dat de folder-KPI uit dat plan (§8).

## 5. Verzending

| Onderdeel | Keuze | Toelichting |
|---|---|---|
| Dienst | **Resend** (al voorzien in de workflow) | Gratis tot 3.000 mails/maand; HTML + platte tekst in één bericht; DKIM-ondertekend |
| Afzender | het adres van de opsteller op zijn eigen domein | Domein eenmalig verifiëren bij Resend: drie DNS-records (DKIM-TXT, SPF op een verzend-subdomein, optioneel DMARC). Omdat het domein op Google Workspace draait, raakt Resend's SPF-record de bestaande Google-SPF niet (eigen subdomein). ±15 minuten |
| Ontvangers | secret `REPORT_EMAIL_TO` | Twee adressen bij terStal, kommagescheiden. Nooit in de repo, docs, workflow-tekst of Actions-log |
| Reply-to | de opsteller | Antwoorden (1/2/3, vragen) komen op één plek; de opsteller werkt `reports/besluiten.md` bij |
| Tijdstip | mail vóór 07:00 NL | Weekrun vervroegd naar ma 03:07 NL-zomertijd (`7 1 * * 1`, UTC; 02:07 in de winter) — *sinds 21-09-2026 vijf cron-slots vanaf ma 01:07 met een planningspoort, omdat GitHub het ene slot twee weken op rij ruim vijf uur te laat startte; zie de kop van `wekelijkse-scrape.yml`*, zodat ook een trage meting van ruim twee uur ruim vóór 07:00 klaar is. De mailstap draait ook als een bron faalt (`if: !cancelled()`), met een storingsregel in de kop; voorheen sloeg een gefaalde meting rapport én mail over — het stilte-risico uit PLAN.md §9 |
| Proefmail | workflow-invoer `mail_to` | Handmatige run met afwijkende ontvanger (alleen de opsteller) zonder aan het secret te komen |
| Archief | `reports/2026-W38.html` naast de `.md` | Elke verstuurde mail blijft terugleesbaar in de repo |
| Alternatief | Gmail-SMTP met app-wachtwoord | Zelfde afzender, mail in "Verzonden" van de opsteller; kost een wachtwoord in de secrets en een lagere afleverzekerheid. Alleen als domeinverificatie niet gewenst is |

**Spamfilter bij terStal.** Eerste mail kan in quarantaine belanden (extern domein, automatisch). Vraag de ontvangers vooraf het afzendadres als veilige afzender te markeren, of laat ICT het domein whitelisten.

## 6. Bouw

Alles in de bestaande repo, naast het huidige rapport; het rapport verandert niet.

| Onderdeel | Wat | Waar |
|---|---|---|
| Datalaag | `weekly_stats` en `v_retailer_week_totals` over de laatste 7 weken in één keer ophalen; nieuwe titels van deze week | `scraper/db.py`: `weekly_stats_range()`, `week_totals_range()`, `new_titles()` |
| Signalen | score, persistentie, ruisfilter, verpakkingswissel, trendwoorden, terugblik | `scraper/signals.py` (nieuw), zuivere functies, volledig getest |
| Concurrentenkaart | sjabloonregels §4.5 | `scraper/signals.py` |
| Weergave | HTML (tabellen, inline CSS, 600 px, geen afbeeldingen, donkere modus via `prefers-color-scheme`) + platte tekst uit dezelfde data | `scraper/weekmail.py` (nieuw) |
| Verzending | `send_email(subject, html, text, reply_to)`; `REPORT_EMAIL_FROM` = geverifieerde afzender | `scraper/report.py` |
| CLI | `python -m scraper weekmail [--week] [--dry-run] [--to]` | `scraper/__main__.py` |
| Workflow | stap "Weekmail versturen" na "Weekrapport genereren", `if: always()`; invoer `mail_to` | `.github/workflows/wekelijkse-scrape.yml` |
| Dashboard | paneel *Weekmail* met de laatst verstuurde mail; week, sectie en filters uit de URL lezen (deep links uit de mail) | `dashboard/index.html` |
| Tests | snapshot van de HTML op vaste fixture-data; regels §4.1–4.7 elk met een positieve en een negatieve casus | `tests/test_weekmail.py`, `tests/test_signals.py` |
| Actieteller | `reports/besluiten.md`: week, agendapunt, antwoord, uitkomst | handmatig door de opsteller (PLAN.md §11E) |

**Inschatting.** Versie 1 (blokken 1–6, terugblik, rustige-week-modus, verzending, proefmail): **2 dagdelen**. Versie 1.1 (verpakkingswissel-detectie, trendwoorden, sjabloonset uitbreiden op basis van drie weken feedback): **1 dagdeel**. Latere versies (na de proef): KVI-koppellijst artikel-op-artikel (PLAN.md §6.3), folderregel uit de foldermonitor, jaar-op-jaar-seizoensklok na 52 weken.

## 7. Planning

| Wanneer | Wat | Wie |
|---|---|---|
| di 15-09 – wo 16-09 | Bouw versie 1, tests, DNS-records | opsteller |
| do 17-09 | Proefmail met W38-data naar de opsteller; tekst en drempels bijstellen | opsteller |
| vr 18-09 | Proefmail naar de inkoopmanager; afzender op veilige lijst | inkoopmanager |
| ma 21-09 (W39) | Eerste echte weekmail, ±07:00 | automatisch |
| ma 21-09, 28-09, 05-10 | Drie proefweken; antwoord 1/2/3 op elke mail; besluiten vastgelegd | inkoopmanager |
| week 40 | Versie 1.1 op basis van de eerste twee weken feedback | opsteller |
| ma 12-10 (W42) | Evaluatie: is de mail in 3 minuten gelezen, leverde hij elke week ≥ 1 besluit? Zo nee: herontwerpen of stoppen (PLAN.md §6.9) | beiden |

## 8. Risico's en wat we eraan doen

- **Stilte.** Een gefaalde run stuurt nu niets. De mailstap draait altijd en meldt de storing in de kop; geen mail op maandag 07:30 is dan zélf het signaal om te kijken.
- **Zeeman-blokkade (HTTP 403 sinds W38).** De mail toont Zeeman met de laatste goede week en het label; het scraperprobleem staat los van de mail.
- **Valse zekerheid.** Elke zin in blok 1 en 2 komt uit een regel met een drempel en is terug te vinden in het weekrapport. Geen tekstgeneratie zonder cijfer erachter.
- **Te veel of te weinig.** De drempels staan als constanten bovenin `scraper/signals.py`; de proefweken zijn ervoor om ze af te stellen.
- **Vertrouwelijkheid.** Ontvangers alleen in secrets; de mail bevat concurrentiecijfers, geen eigen inkoop- of margedata. Het archief in `reports/` staat, net als het weekrapport nu, in een publieke repo — als dat ongewenst is, blijft het archief als Actions-artifact (60 dagen) in plaats van in de repo.

---

*Bijlage: HTML-mock-up van de weekmail met de cijfers van week 38 (gedeeld als artifact). Technische installatie van Resend: README.md §2. Foldermonitor: docs/foldermonitor-plan.md.*
