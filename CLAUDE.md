# Werkafspraken voor Claude in deze repo

- Communiceer in het Nederlands.
- **Tijden altijd in Nederlandse tijd (CET/CEST) weergeven**, nooit kaal UTC.
  Interne zaken (cron-expressies, GitHub-logs) blijven UTC; reken ze om in
  elke boodschap aan de gebruiker. De weekrun heeft vijf
  cron-slots (zo 23:07, ma 00:37, 02:07, 03:37, 05:17 UTC = ma 01:07, 02:37,
  04:07, 05:37, 07:17 NL-zomertijd; in de winter een uur vroeger — GitHub-cron
  volgt geen zomertijd); de weekmail moet om 07:00 binnen zijn (besluit
  eigenaar 14-09-2026).
- GitHub voert geplande runs *best effort* uit: bij drukte worden ze vertraagd
  of overgeslagen zónder melding. Zet cron-expressies daarom nooit op het hele
  uur, en beloof een geplande run nooit als zekerheid — controleer achteraf of
  hij echt gedraaid heeft.
- Eén meting per week: de planningspoort (`scraper/planning.py`, job `poort`)
  laat latere cron-slots overslaan als er al een run loopt of de week al in
  `scrape_runs` staat. De week begint maandag 00:00 **NL-tijd** (`week_monday()`
  in `scraper/config.py`); zet dus nooit een slot vóór zo 23:00 UTC, anders
  boekt de meting in de winter in de vorige week (`tests/test_planning.py`
  bewaakt dit).
- Weekcijfers zijn heilig: nooit staging of weekverwerking draaien buiten de
  kwaliteitspoort om (zie `_beoordeel` in `scraper/__main__.py`).
- Livevalidatie kan alleen op GitHub Actions ("Validatie bronnen"-workflow);
  vanuit de ontwikkelomgeving is het netwerk naar de retailers dicht.
- Secrets (Supabase, Firecrawl) horen alleen in GitHub Secrets — nooit in de
  repo, het dashboard of de chat.
