"""CLI van de foldermonitor (fase 0).

  python -m folders validate [--bron id ...] [--out validatie-folders.md]
  python -m folders bronnen
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_bronnen


def cmd_validate(args) -> int:
    from .validate import validate_one, validate_report
    cfgs = load_bronnen(args.bron or None, include_disabled=True)
    results = []
    for cfg in cfgs:
        print(f"→ {cfg.name}: {cfg.folder_url or 'mail-only'} …", flush=True)
        results.append(validate_one(cfg))
    md = validate_report(results)
    Path(args.out).write_text(md, encoding="utf-8")
    print(md)
    print(f"\nValidatierapport: {args.out}")
    return 0


def cmd_bronnen(args) -> int:
    for b in load_bronnen(include_disabled=True):
        aan = "aan " if b.enabled else "uit "
        print(f"{aan}{b.id:10s} alias +{b.alias:10s} {b.folder_url or 'mail-only':50s} "
              f"elke {b.cadence_days} dagen")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="folders", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="folderbronnen valideren zonder database")
    v.add_argument("--bron", action="append", help="alleen deze bron(nen)")
    v.add_argument("--out", default="validatie-folders.md")
    v.set_defaults(fn=cmd_validate)

    b = sub.add_parser("bronnen", help="bronconfiguratie tonen")
    b.set_defaults(fn=cmd_bronnen)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
