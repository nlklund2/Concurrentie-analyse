"""Planningspoort van de weekrun: moet deze geplande run nog meten?

  python -m scraper.planning

GitHub voert geplande runs 'best effort' uit: op 14-09-2026 en 21-09-2026
startte de cron van 01:07 UTC pas vijf uur later, en de weekmail kwam dus te
laat. De workflow heeft daarom meerdere cron-slots in de maandagnacht; de
eerste die echt start doet de meting, de rest moet zichzelf overslaan. Dat
beslist deze poort, alleen bij event 'schedule' (handmatig starten meet altijd):

1. loopt er al een eerder gestarte run van deze workflow → overslaan;
2. heeft elke actieve bron deze week al een regel in scrape_runs, waarvan
   minstens één 'ok' → de week is gemeten, overslaan;
3. anders: meten.

Bij twijfel (GitHub-API of Supabase onbereikbaar) draait de run gewoon:
een dubbele meting is veilig (process_staging is idempotent per bron en
week), stilte op maandag niet (PLAN.md §9).
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import requests

from .config import load_retailers, week_monday

# Een run in een van deze toestanden is nog bezig of wacht op zijn beurt.
ACTIEF = {"in_progress", "queued", "pending", "waiting", "requested"}


def eerder_actief(gh_runs: list[dict], eigen_id: int) -> dict | None:
    """De oudste andere run van deze workflow die nog bezig is en vóór ons is
    aangemaakt. Alleen 'eerder' telt: starten twee vertraagde slots tegelijk,
    dan wijkt de jongste en blijft er altijd precies één over."""
    eerder = [r for r in gh_runs
              if r.get("status") in ACTIEF and int(r["id"]) < eigen_id]
    return min(eerder, key=lambda r: int(r["id"])) if eerder else None


def week_gemeten(runs: list[dict], verwacht: list[str]) -> bool:
    """Is de week al gemeten? Elke actieve bron heeft een run-regel (welke
    status ook: een bron die 'fout' of 'afwijkend' gaf is wél geprobeerd, en
    opnieuw meten levert vooral een tweede weekmail op) en minstens één bron
    is 'ok' — hetzelfde criterium waarmee `scrape` zelf slaagt. Een afgebroken
    run (niet alle bronnen) of een run waarin niets lukte wordt dus herkanst."""
    if not verwacht:
        return False
    gezien = {r["retailer_id"] for r in runs}
    return set(verwacht) <= gezien and any(r.get("status") == "ok" for r in runs)


def besluit(event: str, gh_runs: list[dict] | None, eigen_id: int,
            runs: list[dict] | None, verwacht: list[str]) -> tuple[bool, str]:
    """(meten?, reden). `None` voor gh_runs of runs = bron onbereikbaar."""
    if event != "schedule":
        return True, f"gestart via '{event}' — de poort geldt alleen voor geplande runs"
    if gh_runs is not None:
        ander = eerder_actief(gh_runs, eigen_id)
        if ander:
            return False, (f"run {ander['id']} ({ander.get('event', '?')}, "
                           f"{ander.get('status')}) is eerder gestart en nog bezig")
    if runs is not None and week_gemeten(runs, verwacht):
        return False, "deze week is al gemeten (elke actieve bron heeft een run, minstens één ok)"
    if gh_runs is None or runs is None:
        return True, "controle onvolledig (GitHub-API of Supabase onbereikbaar) — voor de zekerheid meten"
    return True, "nog geen meting voor deze week"


def _gh_runs(week: date) -> list[dict]:
    repo = os.environ["GITHUB_REPOSITORY"]
    workflow = os.environ.get("PLANNING_WORKFLOW", "wekelijkse-scrape.yml")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    # ruim vóór maandag 00:00 NL beginnen; het filter is alleen een begrenzing
    sinds = (week - timedelta(days=1)).isoformat()
    resp = requests.get(
        f"{api}/repos/{repo}/actions/workflows/{workflow}/runs",
        params={"created": f">={sinds}", "per_page": "50"},
        headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                 "Accept": "application/vnd.github+json"},
        timeout=30)
    resp.raise_for_status()
    return resp.json()["workflow_runs"]


def main() -> int:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    eigen_id = int(os.environ.get("GITHUB_RUN_ID", "0"))
    week = week_monday()
    gh_runs = runs = None
    verwacht: list[str] = []
    if event == "schedule":
        try:
            gh_runs = _gh_runs(week)
        except Exception as e:
            print(f"! GitHub-API niet bereikbaar: {e}", file=sys.stderr)
        try:
            from .db import Db
            verwacht = [c.id for c in load_retailers()]
            runs = Db().runs(week)
        except Exception as e:
            print(f"! Supabase niet bereikbaar: {e}", file=sys.stderr)

    meten, reden = besluit(event, gh_runs, eigen_id, runs, verwacht)
    regel = f"Planningspoort week {week.isoformat()}: {'meten' if meten else 'overslaan'} — {reden}"
    print(regel)
    for var, tekst in (("GITHUB_OUTPUT", f"meten={'true' if meten else 'false'}\n"),
                       ("GITHUB_STEP_SUMMARY", regel + "\n")):
        if os.environ.get(var):
            with open(os.environ[var], "a", encoding="utf-8") as f:
                f.write(tekst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
