"""Mailboxcontrole — zonder netwerk: een nep-IMAP levert koppen; niets wordt gewijzigd."""
from folders.config import BronCfg, load_bronnen
from folders.mail import bron_van_mail, mailbox_check, mailbox_report


class _Imap:
    """Minimale IMAP4-dubbelganger; registreert dat er alleen gelezen wordt."""
    instances = []

    def __init__(self, host):
        self.host, self.calls, self.logged_out = host, [], False
        self.msgs = {
            b"1": b"From: Zeeman <nieuwsbrief@mail.zeeman.com>\r\nTo: folders+zeeman@voorbeeld.nl\r\n\r\n",
            b"2": b"From: newsletter@m.terstal.nl\r\nTo: folders@voorbeeld.nl\r\n\r\n",
            b"3": b"From: info@onbekend.example\r\nTo: folders@voorbeeld.nl\r\n\r\n",
        }
        _Imap.instances.append(self)

    def login(self, user, password):
        self.calls.append(("login", user))
        return "OK", [b"ok"]

    def select(self, box, readonly=False):
        self.calls.append(("select", box, readonly))
        return "OK", [str(len(self.msgs)).encode()]

    def search(self, charset, crit):
        self.calls.append(("search", crit))
        if crit == "UNSEEN":
            return "OK", [b"2 3"]
        return "OK", [b" ".join(sorted(self.msgs))]

    def fetch(self, mid, what):
        self.calls.append(("fetch", mid, what))
        assert "BODY.PEEK" in what, "fetch moet PEEK zijn (niet als gelezen markeren)"
        return "OK", [(b"1 (BODY[HEADER] {0}", self.msgs[mid]), b")"]

    def logout(self):
        self.logged_out = True
        return "BYE", [b""]


def test_bron_van_mail_alias_wint_van_afzender():
    bronnen = [BronCfg(id="zeeman", name="Zeeman", mail_from=["zeeman.com"]),
               BronCfg(id="wibra", name="Wibra", mail_from=["wibra.nl"])]
    assert bron_van_mail(["folders+wibra@voorbeeld.nl"], "nieuws@mail.zeeman.com", bronnen) == "wibra"
    assert bron_van_mail(["folders@voorbeeld.nl"], "nieuws@mail.zeeman.com", bronnen) == "zeeman"
    assert bron_van_mail(["folders@voorbeeld.nl"], "x@zeeman.com.evil.example", bronnen) is None
    assert bron_van_mail([], "", bronnen) is None


def test_mailbox_check_leest_alleen_en_herkent_bronnen():
    bronnen = load_bronnen()
    st = mailbox_check("imap.test", "folders@voorbeeld.nl", "pw", bronnen, imap_factory=_Imap, limit=10)
    imap = _Imap.instances[-1]
    assert ("select", "INBOX", True) in imap.calls and imap.logged_out
    assert st.totaal == 3 and st.ongelezen == 2
    assert st.recent == [("onbekend.example", "?"), ("m.terstal.nl", "terstal"), ("mail.zeeman.com", "zeeman")]
    md = mailbox_report(st, bronnen)
    assert "login geslaagd" in md and "terstal, zeeman" in md and "wibra" in md
    assert "voorbeeld.nl" not in md and "folders@" not in md   # geen adres in openbare logs
