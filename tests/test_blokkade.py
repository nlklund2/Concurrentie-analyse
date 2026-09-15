"""Blokkade-signatuur: uit status, headers en body de poortwachter herkennen.

Zeeman 14-09-2026: 'HTTP 403 (bot-bescherming?)' in het weekrapport zei niets
over de route. De signatuur moet dat wél zeggen — en robuust zijn voor
headers in willekeurige hoofdletters en lege bodies."""
from scraper import blokkade


def test_cloudflare_challenge_uit_header_en_body():
    sig = blokkade.signatuur(403, {"CF-RAY": "8f1-AMS", "cf-mitigated": "challenge",
                                   "Server": "cloudflare"},
                             "<html><title>Just a moment...</title>")
    assert sig.startswith("Cloudflare-challenge")
    assert blokkade.kort(sig).startswith("Cloudflare-challenge (JavaScript-uitdaging") \
        and len(blokkade.kort(sig)) <= 70


def test_cloudflare_waf_zonder_challenge():
    sig = blokkade.signatuur(403, {"cf-ray": "x", "server": "cloudflare"}, "<h1>error 1020</h1>")
    assert sig.startswith("Cloudflare-WAF/Bot Fight Mode (HTTP 403")


def test_akamai_reference_nummer():
    body = ("<HTML><HEAD><TITLE>Access Denied</TITLE></HEAD><BODY>You don't have permission "
            "to access the page. Reference&#32;#18.4f2d1602.1726300000.1a2b3c</BODY></HTML>")
    sig = blokkade.signatuur(403, {"Server": "AkamaiGHost"}, body)
    assert sig.startswith("Akamai Bot Manager (Reference #18.4f2d1602")
    assert "residentieel" in sig


def test_vercel_firewall_alleen_bij_weigering():
    # x-vercel-id staat op élk antwoord van een Vercel-site; pas bij 403 zegt het iets
    assert blokkade.signatuur(200, {"x-vercel-id": "ams1::abc"}, "<html>ok").startswith("onbekende")
    sig = blokkade.signatuur(403, {"x-vercel-id": "ams1::abc", "x-vercel-mitigated": "challenge"}, "")
    assert sig.startswith("Vercel-firewall/bot-bescherming (HTTP 403, challenge)")


def test_overige_poortwachters():
    assert blokkade.signatuur(403, {"x-amzn-waf-action": "challenge"}, "").startswith("AWS WAF (challenge)")
    assert blokkade.signatuur(403, {"X-Iinfo": "1-2"}, "").startswith("Imperva/Incapsula")
    assert blokkade.signatuur(403, {"x-datadome": "protected"}, "").startswith("DataDome")
    assert blokkade.signatuur(403, {}, "<script>window._pxAppId='PX1'; px-captcha</script>").startswith("PerimeterX")


def test_onbekende_weigering_noemt_server_omvang_en_titel():
    sig = blokkade.signatuur(403, {"server": "nginx"}, "<html><title>403 Forbidden</title>" + "x" * 1200)
    assert sig == "onbekende weigering (HTTP 403, server: nginx, 1.2k tekens, titel '403 Forbidden')"
    assert blokkade.signatuur(429, None, "") == "onbekende weigering (HTTP 429, server: ?, 0.0k tekens)"


def test_weigerpagina_zonder_leverancier():
    sig = blokkade.signatuur(403, {"server": "Apache"}, "<h1>Access Denied</h1> request blocked")
    assert sig.startswith("weigerpagina zonder herkenbare leverancier (HTTP 403, server: Apache)")


def test_is_challenge_kijkt_alleen_naar_de_kop_en_niet_naar_productpaginas():
    assert blokkade.is_challenge("<html><title>Just a moment...</title><body>Checking your browser")
    assert blokkade.is_challenge("<html><body>Verify you are human</body>")
    # een echte lijstpagina die het woord 'captcha' ergens in een script noemt is geen challenge
    lijst = "<html><head><title>Dames ondergoed | Zeeman</title></head><body>" \
            "<div class='product'>Slip</div><script>recaptcha</script>"
    assert not blokkade.is_challenge(lijst)
    assert not blokkade.is_challenge("")


def test_titel_normaliseert_witruimte():
    assert blokkade.titel("<title>\n  Access\n Denied </title>") == "Access Denied"
    assert blokkade.titel("<html>zonder titel") == ""
