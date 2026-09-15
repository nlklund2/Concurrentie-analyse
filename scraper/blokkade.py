"""Blokkade-signatuur: wélke poortwachter zegt nee, en hoe?

Een kale "HTTP 403 (bot-bescherming?)" in het weekrapport is geen diagnose.
Zeeman 14-09-2026: de bron die op 07-09 nog byte voor byte dezelfde pagina
als een browser leverde, weigerde een week later élke request vanaf GitHub
Actions — en uit de foutregel viel niet op te maken of dat Cloudflare,
Akamai, Vercel of een eigen regel was. Dat verschil bepaalt de route:

  * TLS-/header-fingerprint (Cloudflare Bot Fight Mode, Vercel-firewall):
    een browseridentieke client (curl_cffi-impersonatie) komt er meestal
    langs, een echte browser zeker;
  * JavaScript-challenge ("Just a moment…"): alleen een echte browser;
  * IP-reputatie (datacenter geweerd, Akamai/DataDome): alleen een
    residentieel IP — Firecrawl.

Deze module leest de handtekening uit status, headers en de eerste
kilobytes van het antwoord; scraper/fetch.py gebruikt haar om te kiezen
welke trede van de toegangsladder de moeite waard is, en de diagnose om
het te kunnen vastleggen.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

# Kenmerkende tekst van challenge-/weigerpagina's, per poortwachter.
_AWSWAF_BODY = re.compile(r"awswaf|challenge\.js.*aws|aws-waf", re.I)
_IMPERVA_BODY = re.compile(r"incapsula|imperva|_incap_", re.I)
_DATADOME_BODY = re.compile(r"datadome", re.I)
_PX_BODY = re.compile(r"_pxhc|px-captcha|perimeterx|human\s*security", re.I)
_DENIED_BODY = re.compile(r"access denied|request blocked|are you human|captcha|"
                          r"pardon our interruption|verify you are human", re.I)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)

# Zo ziet een challenge- of weigerpagina eruit in de eerste kilobytes:
# dit is de poort die scraper/fetch.py en de render-strategie hanteren om een
# HTTP 200 mét challenge-inhoud tóch als blokkade te tellen.
CHALLENGE_RE = re.compile(r"just a moment|verify you are human|security checkpoint|"
                          r"access denied|request blocked|are you human|captcha|"
                          r"pardon our interruption|challenge-platform|_vercel/challenge|"
                          r"awswaf|datadome|px-captcha", re.I)


def _lower(headers: Mapping | None) -> dict[str, str]:
    uit: dict[str, str] = {}
    for k, v in (headers or {}).items():
        try:
            uit[str(k).lower()] = str(v)
        except Exception:
            continue
    return uit


def titel(body: str) -> str:
    m = _TITLE_RE.search(body or "")
    return " ".join(m.group(1).split())[:80] if m else ""


def is_challenge(body: str) -> bool:
    """Challenge-/weigerpagina, óók als hij met HTTP 200 binnenkomt. Kijkt
    alleen naar de kop van de pagina: een productlijst noemt 'captcha' hooguit
    ergens diep in een script."""
    kop = (body or "")[:4000]
    return bool(CHALLENGE_RE.search(kop)) and "product" not in kop.lower()


def signatuur(status: int, headers: Mapping | None = None, body: str = "") -> str:
    """Korte, leesbare handtekening van een weigering: poortwachter + soort.

    Voorbeelden: 'Cloudflare-challenge (cf-mitigated: challenge)',
    'Akamai Bot Manager (Reference #18.abc)', 'Vercel-firewall',
    'onbekende weigering (server: nginx, 1.2k tekens, titel "403 Forbidden")'.
    """
    h = _lower(headers)
    server = h.get("server", "")
    kop = (body or "")[:6000]
    lower_kop = kop.lower()

    # Cloudflare: herkenbaar aan cf-ray/cf-mitigated ongeacht de inhoud.
    if "cf-mitigated" in h or "cf-ray" in h or server.lower() == "cloudflare" or "cf-chl" in lower_kop:
        soort = h.get("cf-mitigated", "")
        if soort == "challenge" or "just a moment" in lower_kop:
            return ("Cloudflare-challenge (JavaScript-uitdaging; alleen een echte browser of "
                    "residentieel IP komt erlangs)")
        if status in (403, 429):
            return f"Cloudflare-WAF/Bot Fight Mode (HTTP {status}, cf-mitigated: {soort or 'geen'})"
        return f"Cloudflare (HTTP {status})"
    if "x-vercel-mitigated" in h or ("x-vercel-id" in h and status in (403, 429)) \
            or "vercel security checkpoint" in lower_kop or "_vercel/challenge" in lower_kop:
        soort = h.get("x-vercel-mitigated", "")
        return f"Vercel-firewall/bot-bescherming (HTTP {status}" + (f", {soort}" if soort else "") + ")"
    # Akamai schrijft 'Reference&#32;#18.…' — de spatie als HTML-entiteit
    m = re.search(r"reference(?:\s|&#32;|&nbsp;)*#\s*(\d+\.[0-9a-f.]+)", kop, re.I)
    if m or "akamaighost" in server.lower() or "errors.edgesuite.net" in lower_kop:
        return "Akamai Bot Manager" + (f" (Reference #{m.group(1)[:24]})" if m else "") + \
               " — weert het datacenter-IP; alleen een residentieel IP komt erlangs"
    if "x-amzn-waf-action" in h or _AWSWAF_BODY.search(kop):
        return f"AWS WAF ({h.get('x-amzn-waf-action') or 'challenge/block'})"
    if "x-iinfo" in h or "incapsula" in h.get("x-cdn", "").lower() or _IMPERVA_BODY.search(kop):
        return "Imperva/Incapsula — weert het datacenter-IP"
    if "x-datadome" in h or "x-datadome-cid" in h or _DATADOME_BODY.search(kop):
        return "DataDome — IP-reputatie + fingerprint; alleen residentieel IP"
    if _PX_BODY.search(kop) or any(k.startswith("x-px") for k in h):
        return "PerimeterX/HUMAN — fingerprint + gedrag; alleen echte browser via residentieel IP"
    if _DENIED_BODY.search(kop):
        return f"weigerpagina zonder herkenbare leverancier (HTTP {status}, server: {server or '?'})"
    t = titel(kop)
    return (f"onbekende weigering (HTTP {status}, server: {server or '?'}, "
            f"{len(body or '') / 1000:.1f}k tekens" + (f", titel {t!r}" if t else "") + ")")


def kort(sig: str, n: int = 70) -> str:
    """Voor de statuskolom van het weekrapport: alleen het eerste deel."""
    return sig.split(" — ")[0][:n]
