"""Exits, sessions and vantages declared in Python give what the TypeScript vocabulary's JSX gives (infra.ts in the
CommandAGI repository): what the file does not say stays absent, and what does not read is refused with why.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.infra import (INFRA, exit, exit_with_defaults, session, session_with_defaults, uses, vantage,
                                     vantage_with_defaults)

EXIT = dict(name="fsn-1", provider="hetzner", region="fsn1", country="DE", size="cax11", image="debian-12")


class ExitTests(unittest.TestCase):
    def test_an_exit_is_what_it_says(self):
        d = declare_document(exit(continent="EU", max_monthly_usd=6.99, **EXIT))
        self.assertEqual(d["format"], "exit")
        self.assertEqual(d["document"], {**EXIT, "continent": "EU", "maxMonthlyUsd": 6.99})
        self.assertEqual(INFRA["exit"].from_tree(INFRA["exit"].to_tree(d["document"])), d["document"])
        self.assertEqual(exit_with_defaults(declare_document(exit(**EXIT))["document"]), {
            **EXIT, "continent": None, "protocol": "wireguard", "enabled": True, "price": None, "maxMonthlyUsd": None})
        self.assertIs(exit_with_defaults(declare_document(exit(enabled=False, **EXIT))["document"])["enabled"], False)

    def test_a_bad_exit_is_refused(self):
        for over, why in [
            ({"name": "Fsn 1"}, "name is lower-case letters"), ({"name": "x\n"}, "name is lower-case letters"),
            ({"provider": "linode"}, 'provider is "hetzner", "vultr", not "linode"'),
            ({"country": "de"}, "country is an ISO 3166 code in capitals"), ({"continent": "Europe"}, 'continent is "AF"'),
            ({"protocol": "openvpn"}, 'protocol is "wireguard"'), ({"enabled": "yes"}, "enabled is true or false"),
            ({"max_monthly_usd": "6.99"}, "maxMonthlyUsd is a price in USD"), ({"max_monthly_usd": True}, "maxMonthlyUsd is a price in USD"),
            ({"ip": "1.2.3.4"}, "ip is not read"),
        ]:
            with self.subTest(why=why), self.assertRaisesRegex(ValueError, why):
                declare_document(exit(**{**EXIT, **over}))
        missing = {k: v for k, v in EXIT.items() if k != "name"}
        with self.assertRaisesRegex(ValueError, "<exit> needs name"):
            declare_document(exit(**missing))

    def test_a_python_file_declares_it(self):
        out = run_module('from commandagi.design.infra import exit\nresult = exit(name="fsn-1", provider="hetzner", region="fsn1", country="DE", size="cax11", image="debian-12")\n', "infra/vpn/fsn-1/exit.py")
        self.assertEqual(out["document"]["format"], "exit")


class VantageTests(unittest.TestCase):
    def test_a_vantage_is_a_device_a_place_and_a_session(self):
        loc = {"city": "Falkenstein", "region": "DE-SN", "country": "DE", "precision": "city"}
        d = declare_document(vantage(name="fsn-1", path="worker", exit="fsn-1", location=loc, locale="de-DE", timezone="Europe/Berlin"))
        self.assertEqual(d["format"], "vantage")
        self.assertEqual(INFRA["vantage"].from_tree(INFRA["vantage"].to_tree(d["document"])), d["document"])
        self.assertEqual(vantage_with_defaults(d["document"]), {
            "name": "fsn-1", "path": "worker", "host": None, "unit": None, "snapshot": None, "exit": "fsn-1", "location": loc,
            "locale": "de-DE", "timezone": "Europe/Berlin", "session": None, "device": None, "clock": None, "enabled": True})

    def test_it_has_no_words_for_a_person(self):
        for k in ("displayName", "birthday", "gender", "persona", "profile", "history", "age", "email"):
            with self.subTest(k=k), self.assertRaisesRegex(ValueError, f"{k} is not read"):
                declare_document(vantage(name="v-1", path="host", **{k.replace("displayName", "display_name"): "x"}))

    def test_a_bad_vantage_is_refused(self):
        host = dict(name="v-1", path="host", host="laptop-linux")
        for over, why in [
            ({"device": {"kind": "desktop", "owner": "Jane"}}, "device.owner is not read"),
            ({"location": {"street": "1 Main St"}}, "location.street is not read"),
            ({"name": "Jane Doe"}, "name is the folder's word"), ({"path": "satellite"}, 'path is "browser"'),
            ({"unit": "x#y"}, 'for path="phone" only'), ({"snapshot": "s"}, "snapshot is for a VM"),
            ({"exit": "Germany"}, "exit is an exit's name"), ({"exit": "ab"}, "exit is an exit's name"),
            ({"locale": "English"}, "locale is a BCP 47 tag"), ({"timezone": "CST 6"}, "timezone is an IANA zone"),
            ({"location": {"lat": 120}}, "location.lat is a number from -90 to 90"),
            ({"location": {"lon": True}}, "location.lon is a number from -180 to 180"),
            ({"location": {"country": "us"}}, "location.country is an ISO 3166 code"),
            ({"clock": 50}, r"clock is \{ sd \} in ms"),
            ({"clock": {"sd": -1}}, r"clock is \{ sd \} in ms"), ({"enabled": 1}, "enabled is true or false"),
        ]:
            with self.subTest(why=why), self.assertRaisesRegex(ValueError, why):
                declare_document(vantage(**{**host, **over}))
        with self.assertRaisesRegex(ValueError, "a browser is driven by a host"):
            declare_document(vantage(name="b-1", path="browser"))
        with self.assertRaisesRegex(ValueError, "the worker's path has no host"):
            declare_document(vantage(name="w-1", path="worker", host="x"))


class SessionTests(unittest.TestCase):
    def test_a_session_names_its_monitors_and_holds_no_credential(self):
        d = declare_document(session(uses(monitor="../../../social/x/nvidia"), name="x-web", site="https://x.com", kind="browser-profile", profile="x-web", refreshed="2026-10-12"))
        self.assertEqual(d["document"], {"name": "x-web", "site": "https://x.com", "kind": "browser-profile", "profile": "x-web", "refreshed": "2026-10-12", "uses": [{"monitor": "../../../social/x/nvidia"}]})
        self.assertEqual(INFRA["session"].from_tree(INFRA["session"].to_tree(d["document"])), d["document"])
        self.assertEqual(session_with_defaults(d["document"]), {
            "name": "x-web", "site": "https://x.com", "kind": "browser-profile", "host": None, "profile": "x-web", "snapshot": None,
            "refreshed": "2026-10-12", "note": None, "uses": ["../../../social/x/nvidia"]})

    def test_a_bad_session_is_refused(self):
        web = dict(name="x-web", site="https://x.com", kind="browser-profile", profile="x-web")
        for over, why in [
            ({"password": "hunter2"}, "password is not read"), ({"site": "http://x.com"}, "site is an https address"),
            ({"site": "https://x.com/a b"}, "site is an https address"), ({"kind": "cookie"}, 'kind is "browser-profile"'),
            ({"profile": "X Web"}, "profile is lower-case"), ({"snapshot": "s"}, "a browser-profile has a profile, not a snapshot"),
            ({"refreshed": "2026-13-01"}, "refreshed is a day"), ({"note": ""}, "note is a word"),
        ]:
            with self.subTest(why=why), self.assertRaisesRegex(ValueError, why):
                declare_document(session(**{**web, **over}))
        with self.assertRaisesRegex(ValueError, "a vm-snapshot names its snapshot"):
            declare_document(session(name="vm", site="https://x.com", kind="vm-snapshot"))
        with self.assertRaisesRegex(ValueError, "a vm-snapshot has a snapshot, not a profile"):
            declare_document(session(name="vm", site="https://x.com", kind="vm-snapshot", snapshot="s", profile="p"))
        with self.assertRaisesRegex(ValueError, 'two <uses> in <session> have monitor "a"'):
            declare_document(session(uses(monitor="a"), uses(monitor="a"), **web))


if __name__ == "__main__":
    unittest.main()
