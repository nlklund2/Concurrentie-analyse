"""Mailbox van de foldermonitor — fase 0: alleen-lezen controle.

Google Workspace/Gmail via IMAP (imaplib, standaardbibliotheek). Het adres en
het app-wachtwoord komen uitsluitend uit GitHub Secrets; de host is een
variabele met imap.gmail.com als standaard (config.imap_env).

De controle logt in, telt, en kijkt naar de koppen van de laatste mails
(BODY.PEEK, postvak readonly): niets wordt gelezen gemarkeerd of gewijzigd.
Het rapport noemt het mailadres nergens — Actions-logs van een publieke repo
zijn openbaar. De sweep zelf (lezen, folderlinks, registreren) is fase 1.
"""
from __future__ import annotations

import email
import email.utils
import imaplib
from dataclasses import dataclass, field

from .config import BronCfg, alias_uit_adres


@dataclass
class MailboxStatus:
    host: str
    totaal: int
    ongelezen: int
    recent: list[tuple[str, str]] = field(default_factory=list)  # (afzenderdomein, bron-id of '?')


def domein(adres: str) -> str:
    return adres.rsplit("@", 1)[-1].strip().lower() if "@" in adres else ""


def bron_van_mail(ontvangers: list[str], afzender: str, bronnen: list[BronCfg]) -> str | None:
    """Bron bepalen: eerst het plus-alias in een ontvangstadres (deterministisch),
    anders het afzenderdomein (mail_from; matcht ook subdomeinen zoals m.terstal.nl)."""
    for adres in ontvangers:
        alias = alias_uit_adres(adres)
        if alias:
            for b in bronnen:
                if b.alias == alias:
                    return b.id
    dom = domein(afzender)
    if dom:
        for b in bronnen:
            if any(dom == d or dom.endswith("." + d) for d in b.mail_from):
                return b.id
    return None


def _adressen(msg, *koppen: str) -> list[str]:
    out = []
    for kop in koppen:
        for waarde in msg.get_all(kop, []):
            out.extend(a for _, a in email.utils.getaddresses([waarde]) if a)
    return out


def mailbox_check(host: str, user: str, password: str, bronnen: list[BronCfg],
                  imap_factory=imaplib.IMAP4_SSL, limit: int = 10) -> MailboxStatus:
    conn = imap_factory(host)
    try:
        conn.login(user, password)
        _, data = conn.select("INBOX", readonly=True)
        totaal = int(data[0])
        _, data = conn.search(None, "UNSEEN")
        ongelezen = len(data[0].split())
        _, data = conn.search(None, "ALL")
        ids = data[0].split()[-limit:]
        recent: list[tuple[str, str]] = []
        for mid in reversed(ids):
            _, delen = conn.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM TO DELIVERED-TO)])")
            raw = next((d[1] for d in delen if isinstance(d, tuple) and len(d) > 1), b"")
            msg = email.message_from_bytes(raw)
            afzender = next(iter(_adressen(msg, "From")), "")
            ontvangers = _adressen(msg, "To", "Delivered-To")
            recent.append((domein(afzender) or "?", bron_van_mail(ontvangers, afzender, bronnen) or "?"))
        return MailboxStatus(host=host, totaal=totaal, ongelezen=ongelezen, recent=recent)
    finally:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001 — logout mag nooit de uitkomst verbergen
            pass


def mailbox_report(st: MailboxStatus, bronnen: list[BronCfg]) -> str:
    """Markdown voor de job-samenvatting. Geen adres, geen onderwerpen."""
    herkend = {b for _, b in st.recent if b != "?"}
    lines = ["## Mailboxcontrole (alleen-lezen)", "",
             f"- Host: `{st.host}` — login geslaagd",
             f"- Berichten in INBOX: {st.totaal} (ongelezen: {st.ongelezen})",
             f"- Bronnen herkend in de laatste {len(st.recent)} mails: "
             + (", ".join(sorted(herkend)) if herkend else "nog geen"), ""]
    if st.recent:
        lines += ["| # | Afzenderdomein | Bron |", "|---|---|---|"]
        lines += [f"| {i} | {dom} | {bron} |" for i, (dom, bron) in enumerate(st.recent, 1)]
        lines.append("")
    ontbreekt = sorted(b.id for b in bronnen if b.enabled and b.id not in herkend)
    if ontbreekt:
        lines.append("Nog geen mail van: " + ", ".join(ontbreekt)
                     + " — inschrijven (checklist A) of wachten op de eerste nieuwsbrief.")
    return "\n".join(lines) + "\n"
