"""Configuratie van de foldermonitor: bronnen.yml + omgevingsvariabelen."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PKG_DIR = Path(__file__).parent
BRONNEN_FILE = PKG_DIR / "bronnen.yml"


@dataclass
class BronCfg:
    id: str
    name: str
    segment: str = "kern"
    enabled: bool = True
    mail_from: list[str] = field(default_factory=list)  # afzenderdomeinen
    mail_alias: str = ""                                 # plus-alias; leeg = id
    folder_url: str = ""                                 # web-fallback; leeg = mail-only
    viewer: str = "auto"                                 # auto | pdf | publitas | ipaper | pages | render
    cadence_days: int = 7
    min_delay: float = 1.0
    respect_robots: bool = True
    notes: str = ""

    @property
    def alias(self) -> str:
        return self.mail_alias or self.id

    @property
    def mail_only(self) -> bool:
        return not self.folder_url


def load_bronnen(only: list[str] | None = None, include_disabled: bool = False) -> list[BronCfg]:
    raw = yaml.safe_load(BRONNEN_FILE.read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    out: list[BronCfg] = []
    for bid, cfg in raw["bronnen"].items():
        merged = {**defaults, **(cfg or {})}
        bc = BronCfg(id=bid, **merged)
        if only and bid not in only:
            continue
        if not bc.enabled and not include_disabled and not only:
            continue
        out.append(bc)
    if only:
        missing = set(only) - {b.id for b in out}
        if missing:
            raise SystemExit(f"Onbekende bron(nen): {', '.join(sorted(missing))}")
    return out


def folders_enabled() -> bool:
    """Feature-vlag (plan §9.5): zonder FOLDERS_ENABLED blijft productie ongewijzigd."""
    return os.environ.get("FOLDERS_ENABLED", "").strip().lower() in {"1", "true", "ja", "yes"}


def db_env() -> tuple[str, str]:
    """Alleen de FOLDERS_*-sleutels. De SUPABASE_*-sleutels van de scraper
    worden bewust níet als terugval gelezen: zolang de foldermonitor in
    preview draait, mag hij fysiek niet bij productie kunnen (plan §9.5)."""
    url = os.environ.get("FOLDERS_SUPABASE_URL", "").strip()
    key = os.environ.get("FOLDERS_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise SystemExit("FOLDERS_SUPABASE_URL en/of FOLDERS_SUPABASE_SERVICE_ROLE_KEY ontbreken "
                         "(GitHub Environment 'preview', zie docs/foldermonitor-fase0.md).")
    return url.rstrip("/"), key
