"""Configuratie van de foldermonitor: bronnen.yml + omgevingsvariabelen."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PKG_DIR = Path(__file__).parent
BRONNEN_FILE = PKG_DIR / "bronnen.yml"

# Mailbox (besluit 06-09): een neutraal adres op een eigen Google
# Workspace-domein. Technisch gelijk aan Gmail: IMAP op imap.gmail.com,
# app-wachtwoord (2-staps-verificatie verplicht), plus-aliassen per bron.
# Het adres zelf staat nergens in deze (publieke) repo — alleen in het
# GitHub-secret FOLDER_IMAP_USER.
IMAP_HOST_STANDAARD = "imap.gmail.com"


@dataclass
class BronCfg:
    id: str
    name: str
    segment: str = "kern"
    enabled: bool = True
    mail_from: list[str] = field(default_factory=list)  # afzenderdomeinen
    mail_alias: str = ""                                 # plus-alias; leeg = id
    folder_url: str = ""                                 # web-fallback; leeg = mail-only
    folder_url_kandidaten: list[str] = field(default_factory=list)  # geprobeerd als folder_url niet antwoordt
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


def imap_env() -> tuple[str, str, str]:
    """Host, gebruiker en wachtwoord van de foldermailbox (GitHub Environment
    'preview'). De host is een gewone variabele met Google als standaard; het
    adres en het app-wachtwoord zijn secrets en komen nooit in logs of repo."""
    host = os.environ.get("FOLDER_IMAP_HOST", "").strip() or IMAP_HOST_STANDAARD
    user = os.environ.get("FOLDER_IMAP_USER", "").strip()
    password = os.environ.get("FOLDER_IMAP_PASSWORD", "")
    if not user or not password:
        raise SystemExit("FOLDER_IMAP_USER en/of FOLDER_IMAP_PASSWORD ontbreken "
                         "(GitHub Environment 'preview', zie docs/foldermonitor-fase0.md).")
    return host, user, password


_ALIAS_RE = re.compile(r"^([^+@\s]+)\+([^@\s]+)@(\S+)$")


def alias_adres(adres: str, alias: str) -> str:
    """Inschrijfadres per bron: <lokaal>+<alias>@<domein> (plus-adressering,
    Gmail/Google Workspace). Wordt nergens opgeslagen; alleen getoond."""
    lokaal, at, domein = adres.strip().partition("@")
    if not at or not lokaal or not domein:
        raise ValueError(f"geen mailadres: {adres!r}")
    return f"{lokaal}+{alias}@{domein}"


def alias_uit_adres(adres: str) -> str:
    """Het plus-alias uit een ontvangstadres (To/Delivered-To), of '' zonder alias."""
    m = _ALIAS_RE.match(adres.strip().lower())
    return m.group(2) if m else ""
