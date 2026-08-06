"""CLI van de concurrentiemonitor.

  python -m scraper scrape [--retailer id ...] [--dry-run] [--limit N]
  python -m scraper probe  [--retailer id ...] [--limit N] [--out bestand.md]
  python -m scraper report [--week JJJJ-MM-DD] [--no-email]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import date
from pathlib import Path

from . import strategies
from .config import OUT_DIR, load_retailers, week_monday
from .normalize import apply_focus, to_staging_rows


def cmd_scrape(args) -> int:
    week = week_monday()
    cfgs = load_retailers(args.retailer or None)
    db = None
    if not args.dry_run:
        from .db import Db
        db = Db()
        db.ensure_retailers(load_retailers(include_disabled=True))

    summary: list[tuple[str, str, int, str]] = []
    for cfg in cfgs:
        print(f"→ {cfg.name} ({cfg.strategy}) …", flush=True)
        res = strategies.run(cfg, limit=args.limit)
        all_rows = to_staging_rows(cfg.id, res.products)
        _dump_raw(week, cfg.id, all_rows)  # ruwe dump vóór het focusfilter
        rows = apply_focus(all_rows, cfg.focus_product_types)
        if len(rows) != len(all_rows):
            print(f"  · focus: {len(rows)} van {len(all_rows)} artikelen binnen scope")
        for note in res.notes:
            print(f"  · {note}")

        if args.dry_run:
            status = "ok" if rows else f"fout: {res.error or 'geen artikelen'}"
            summary.append((cfg.id, res.strategy, len(rows), status))
            continue

        try:
            status, note = _beoordeel(db, cfg, rows, res.error)
            if status == "ok":
                db.replace_staging(cfg.id, rows)
                stats = db.process_week(cfg.id, week)
                note = json.dumps(stats, ensure_ascii=False)
                print(f"  ✓ verwerkt: {note}")
            else:
                print(f"  ✗ niet verwerkt ({status}): {note}")
        except Exception as e:  # databaseprobleem bij één bron ≠ einde weekrun
            status, note = "fout", f"verwerking mislukt: {e}"
            print(f"  ✗ {note}")
        try:
            db.log_run(cfg.id, week, res.strategy or cfg.strategy, len(rows), status, note)
        except Exception as e:
            print(f"  ! run-log niet weggeschreven: {e}")
        summary.append((cfg.id, res.strategy, len(rows), status))

    print("\n=== Samenvatting ===")
    for rid, strat, n, status in summary:
        print(f"{rid:12s} {strat or '-':14s} {n:6d} artikelen  {status}")
    ok = [s for s in summary if s[3] == "ok"]
    if not ok:
        print("Geen enkele bron leverde bruikbare data op.", file=sys.stderr)
        return 1
    return 0


def _beoordeel(db, cfg, rows, error: str) -> tuple[str, str]:
    """Kwaliteitspoort: vervuil de trenddata niet met een halve scrape."""
    if error and not rows:
        return "fout", error
    if len(rows) < cfg.min_products_expected:
        return "fout", (f"slechts {len(rows)} artikelen "
                        f"(minimum {cfg.min_products_expected}); {error or 'bron gewijzigd?'}")
    prev = db.active_count(cfg.id)
    if prev > 0 and len(rows) < 0.5 * prev:
        return "afwijkend", (f"{len(rows)} artikelen is <50% van vorige stand ({prev}); "
                             "week niet verwerkt om de trend niet te vervuilen")
    if error:
        return "afwijkend", f"deels gelukt met fout: {error}"
    return "ok", ""


def _dump_raw(week: date, retailer_id: str, rows: list[dict]) -> None:
    raw_dir = OUT_DIR / "raw" / week.isoformat()
    raw_dir.mkdir(parents=True, exist_ok=True)
    with gzip.open(raw_dir / f"{retailer_id}.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def cmd_probe(args) -> int:
    from .probe import probe_one, probe_report
    cfgs = load_retailers(args.retailer or None, include_disabled=True)
    probes = []
    for cfg in cfgs:
        print(f"→ proef {cfg.name} …", flush=True)
        probes.append(probe_one(cfg, limit=args.limit))
    md = probe_report(probes, args.limit)
    out = Path(args.out)
    out.write_text(md, encoding="utf-8")
    print(f"\nValidatierapport: {out}")
    print(md)
    return 0


def cmd_report(args) -> int:
    from .report import write_report
    week = date.fromisoformat(args.week) if args.week else week_monday()
    write_report(week, send=not args.no_email)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="scraper", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scrape", help="wekelijkse scrape + verwerking naar Supabase")
    s.add_argument("--retailer", action="append", help="alleen deze bron(nen)")
    s.add_argument("--dry-run", action="store_true", help="niet naar de database schrijven")
    s.add_argument("--limit", type=int, help="max artikelen per bron (testen)")
    s.set_defaults(fn=cmd_scrape)

    p = sub.add_parser("probe", help="bronnen valideren zonder database")
    p.add_argument("--retailer", action="append")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--out", default="probe-rapport.md")
    p.set_defaults(fn=cmd_probe)

    r = sub.add_parser("report", help="weekrapport genereren uit de database")
    r.add_argument("--week", help="maandag van de week (JJJJ-MM-DD), standaard deze week")
    r.add_argument("--no-email", action="store_true")
    r.set_defaults(fn=cmd_report)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
