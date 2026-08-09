# Werkafspraken voor Claude in deze repo

- Communiceer in het Nederlands.
- **Tijden altijd in Nederlandse tijd (CET/CEST) weergeven**, nooit kaal UTC.
  Interne zaken (cron-expressies, GitHub-logs) blijven UTC; reken ze om in
  elke boodschap aan de gebruiker. De weekcron `30 4 * * 1` = maandag
  06:30 NL-zomertijd / 05:30 NL-wintertijd.
- Weekcijfers zijn heilig: nooit staging of weekverwerking draaien buiten de
  kwaliteitspoort om (zie `_beoordeel` in `scraper/__main__.py`).
- Livevalidatie kan alleen op GitHub Actions ("Validatie bronnen"-workflow);
  vanuit de ontwikkelomgeving is het netwerk naar de retailers dicht.
- Secrets (Supabase, Firecrawl) horen alleen in GitHub Secrets — nooit in de
  repo, het dashboard of de chat.
