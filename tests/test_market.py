"""A market recording declared in Python gives what the TypeScript SDK's JSX gives (market.test.ts there): one record
per element, in order, and a number where decimal text belongs refused by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.market import MARKET_VOCABULARY, account, bid, book, cancel, fill, holding, market, order, order_update, quote, trade

# A copy of seed/user-commandagi/examples/market/code/Paper.market.py in the CommandAGI repository: the golden all
# three SDKs declare alike.
PAPER = """\
# Paper: a market recording in code. The market view shows it, and the host writes each order, outcome and
# read-back into it as one element before the closing tag. Its TSX twin is `Paper.market.tsx`, its Rust twin
# `Paper.market.rs`.
#
# One element per record, in time order. Prices and quantities are decimal text ("185.09"), never numbers. The data
# is made up: a fictional instrument and a paper account that never existed. Not a market, not advice.
from commandagi.design.market import *

result = market(
    note(t="2026-10-01T13:30:00.000Z", text="Example data: a fictional instrument and a paper account. Not a market, not advice."),
    quote(t="2026-10-01T13:30:00.000Z", sym="NRTH", last="185.09", bid="185.05", ask="185.13", vol="400"),
    book(
        bid(price="185.05", qty="300"),
        bid(price="185.00", qty="120"),
        ask(price="185.13", qty="200"),
        t="2026-10-01T13:30:01.000Z",
        sym="NRTH",
    ),
    trade(t="2026-10-01T13:30:02.000Z", sym="NRTH", price="185.10", qty="25", side="buy"),
    news(t="2026-10-01T13:30:03.000Z", sym="NRTH", headline="Northwind opens a second plant", tone="good"),
    position(t="2026-10-01T13:30:04.000Z", sym="NRTH", qty="120", avg="181.5"),
    order(t="2026-10-01T13:31:00.000Z", id="o-a1b2c3d4e5f6", sym="NRTH", side="buy", qty="10", type="limit", limit="184.50", tif="day", venue="alpaca-paper", mode="paper", by="person:ada", grant="g-paper", connection="conn-1"),
    order_update(t="2026-10-01T13:31:01.000Z", order="o-a1b2c3d4e5f6", state="accepted", mode="paper", ref="alp-1001"),
    amend(t="2026-10-01T13:32:00.000Z", id="m-a1b2c3d4e5f6", order="o-a1b2c3d4e5f6", sym="NRTH", side="buy", qty="10", type="limit", limit="184.80", tif="day", venue="alpaca-paper", mode="paper", ref="alp-1001", by="person:ada", grant="g-paper", connection="conn-1"),
    amend_update(t="2026-10-01T13:32:01.000Z", amend="m-a1b2c3d4e5f6", state="requested", mode="paper", ref="alp-1002"),
    fill(t="2026-10-01T13:33:00.000Z", sym="NRTH", side="buy", price="184.80", qty="4", by="person:ada", order="o-a1b2c3d4e5f6", mode="paper", ref="fill-1", at="2026-10-01T13:32:40.000Z"),
    order_update(t="2026-10-01T13:33:00.000Z", order="o-a1b2c3d4e5f6", state="partial", mode="paper", ref="alp-1002", filled="4", avg="184.80", src="venue"),
    account(
        holding(sym="NRTH", side="long", qty="4", avg="184.80", price="185.10", value="740.40", pl="1.20", pl_pct="0.0016"),
        open_order(ref="alp-1002", client="o-a1b2c3d4e5f6", order="o-a1b2c3d4e5f6", sym="NRTH", side="buy", type="limit", tif="day", status="partially_filled", state="partial", qty="10", filled="4", avg_price="184.80", limit="184.80"),
        problem(text="Example: one page of executions was read."),
        t="2026-10-01T13:33:00.000Z",
        venue="alpaca-paper",
        mode="paper",
        connection="conn-1",
        currency="USD",
        status="ACTIVE",
        value="100739.20",
        buying_power="198521.60",
        cash="99260.80",
        day_change="-12.40",
        day_change_pct="-0.000123",
    ),
    cancel(t="2026-10-01T13:34:00.000Z", id="x-a1b2c3d4e5f6", venue="alpaca-paper", mode="paper", ref="alp-1002", order="o-a1b2c3d4e5f6", connection="conn-1", by="person:ada", grant="g-paper"),
    cancel_update(t="2026-10-01T13:34:01.000Z", cancel="x-a1b2c3d4e5f6", state="requested", mode="paper"),
    order_update(t="2026-10-01T13:35:00.000Z", order="o-a1b2c3d4e5f6", state="cancelled", mode="paper", ref="alp-1002", filled="4", avg="184.80", src="venue"),
    order(t="2026-10-01T13:36:00.000Z", id="o-0f1e2d3c4b5a", sym="NRTH", side="sell", qty="2", type="market", tif="ioc", venue="sim", mode="sim", by="agent:trader", grant="g-sim"),
    fill(t="2026-10-01T13:36:00.000Z", sym="NRTH", side="sell", price="185.05", qty="2", by="agent:trader", order="o-0f1e2d3c4b5a", mode="sim"),
    order_update(t="2026-10-01T13:36:00.000Z", order="o-0f1e2d3c4b5a", state="filled", mode="sim"),
)
"""

PAPER_RECORDS = [
    {"kind": "note", "t": "2026-10-01T13:30:00.000Z", "text": "Example data: a fictional instrument and a paper account. Not a market, not advice."},
    {"kind": "quote", "t": "2026-10-01T13:30:00.000Z", "sym": "NRTH", "last": "185.09", "bid": "185.05", "ask": "185.13", "vol": "400"},
    {"kind": "book", "t": "2026-10-01T13:30:01.000Z", "sym": "NRTH", "bids": [["185.05", "300"], ["185.00", "120"]], "asks": [["185.13", "200"]]},
    {"kind": "trade", "t": "2026-10-01T13:30:02.000Z", "sym": "NRTH", "price": "185.10", "qty": "25", "side": "buy"},
    {"kind": "news", "t": "2026-10-01T13:30:03.000Z", "sym": "NRTH", "headline": "Northwind opens a second plant", "tone": "good"},
    {"kind": "position", "t": "2026-10-01T13:30:04.000Z", "sym": "NRTH", "qty": "120", "avg": "181.5"},
    {"kind": "order", "t": "2026-10-01T13:31:00.000Z", "id": "o-a1b2c3d4e5f6", "sym": "NRTH", "side": "buy", "qty": "10", "type": "limit", "limit": "184.50", "tif": "day", "venue": "alpaca-paper", "mode": "paper", "by": "person:ada", "grant": "g-paper", "connection": "conn-1"},
    {"kind": "order-update", "t": "2026-10-01T13:31:01.000Z", "order": "o-a1b2c3d4e5f6", "state": "accepted", "mode": "paper", "ref": "alp-1001"},
    {"kind": "amend", "t": "2026-10-01T13:32:00.000Z", "id": "m-a1b2c3d4e5f6", "order": "o-a1b2c3d4e5f6", "sym": "NRTH", "side": "buy", "qty": "10", "type": "limit", "limit": "184.80", "tif": "day", "venue": "alpaca-paper", "mode": "paper", "ref": "alp-1001", "by": "person:ada", "grant": "g-paper", "connection": "conn-1"},
    {"kind": "amend-update", "t": "2026-10-01T13:32:01.000Z", "amend": "m-a1b2c3d4e5f6", "state": "requested", "mode": "paper", "ref": "alp-1002"},
    {"kind": "fill", "t": "2026-10-01T13:33:00.000Z", "sym": "NRTH", "side": "buy", "price": "184.80", "qty": "4", "by": "person:ada", "order": "o-a1b2c3d4e5f6", "mode": "paper", "ref": "fill-1", "at": "2026-10-01T13:32:40.000Z"},
    {"kind": "order-update", "t": "2026-10-01T13:33:00.000Z", "order": "o-a1b2c3d4e5f6", "state": "partial", "mode": "paper", "ref": "alp-1002", "filled": "4", "avg": "184.80", "src": "venue"},
    {"kind": "account", "t": "2026-10-01T13:33:00.000Z", "venue": "alpaca-paper", "mode": "paper", "connection": "conn-1", "currency": "USD", "status": "ACTIVE", "value": "100739.20", "buyingPower": "198521.60", "cash": "99260.80", "dayChange": "-12.40", "dayChangePct": "-0.000123", "positions": [{"sym": "NRTH", "side": "long", "qty": "4", "avg": "184.80", "price": "185.10", "value": "740.40", "pl": "1.20", "plPct": "0.0016"}], "open": [{"ref": "alp-1002", "client": "o-a1b2c3d4e5f6", "order": "o-a1b2c3d4e5f6", "sym": "NRTH", "side": "buy", "type": "limit", "tif": "day", "status": "partially_filled", "state": "partial", "qty": "10", "filled": "4", "avgPrice": "184.80", "limit": "184.80"}], "problems": ["Example: one page of executions was read."]},
    {"kind": "cancel", "t": "2026-10-01T13:34:00.000Z", "id": "x-a1b2c3d4e5f6", "venue": "alpaca-paper", "mode": "paper", "ref": "alp-1002", "order": "o-a1b2c3d4e5f6", "connection": "conn-1", "by": "person:ada", "grant": "g-paper"},
    {"kind": "cancel-update", "t": "2026-10-01T13:34:01.000Z", "cancel": "x-a1b2c3d4e5f6", "state": "requested", "mode": "paper"},
    {"kind": "order-update", "t": "2026-10-01T13:35:00.000Z", "order": "o-a1b2c3d4e5f6", "state": "cancelled", "mode": "paper", "ref": "alp-1002", "filled": "4", "avg": "184.80", "src": "venue"},
    {"kind": "order", "t": "2026-10-01T13:36:00.000Z", "id": "o-0f1e2d3c4b5a", "sym": "NRTH", "side": "sell", "qty": "2", "type": "market", "tif": "ioc", "venue": "sim", "mode": "sim", "by": "agent:trader", "grant": "g-sim"},
    {"kind": "fill", "t": "2026-10-01T13:36:00.000Z", "sym": "NRTH", "side": "sell", "price": "185.05", "qty": "2", "by": "agent:trader", "order": "o-0f1e2d3c4b5a", "mode": "sim"},
    {"kind": "order-update", "t": "2026-10-01T13:36:00.000Z", "order": "o-0f1e2d3c4b5a", "state": "filled", "mode": "sim"},
]

T = "2026-10-01T13:30:00.000Z"


class MarketTests(unittest.TestCase):
    def test_the_paper_recording_declares_the_golden_document(self):
        out = run_module(PAPER, "Paper.market.py")
        self.assertEqual(out["document"]["format"], "market")
        self.assertEqual(out["document"]["document"], {"records": PAPER_RECORDS})

    def test_an_empty_recording_declares_no_records(self):
        self.assertEqual(declare_document(market())["document"], {"records": []})
        self.assertEqual(MARKET_VOCABULARY.empty("Paper"), {"records": []})

    def test_a_number_where_text_belongs_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, r'<quote> last is decimal text \("185.09"\), not a number'):
            declare_document(market(quote(t=T, sym="NRTH", last=185.09)))
        with self.assertRaisesRegex(ValueError, r'<trade> qty is decimal text \("185.09"\), not a number'):
            declare_document(market(trade(t=T, sym="NRTH", price="185.10", qty=25)))
        with self.assertRaisesRegex(ValueError, r'<bid> price is decimal text \("185.09"\), not a number'):
            declare_document(market(book(bid(price=185.05, qty="300"), t=T, sym="NRTH")))
        with self.assertRaisesRegex(ValueError, r'<trade> price is decimal text \("185.09"\), not "1e3"'):
            declare_document(market(trade(t=T, sym="NRTH", price="1e3", qty="1")))
        with self.assertRaisesRegex(ValueError, "<quote> sym is text, not a number"):
            declare_document(market(quote(t=T, sym=7)))
        with self.assertRaisesRegex(ValueError, r'<quote> t is an ISO time .*, not "yesterday"'):
            declare_document(market(quote(t="yesterday", sym="NRTH")))

    def test_a_bracket_is_an_order_with_two_exits_each_outcome_naming_its_leg(self):
        o = dict(t=T, id="o-a1b2c3d4e5f6", sym="NRTH", side="buy", qty="10", type="limit", limit="184.50", take_profit="190.25",
                 stop_loss="180", tif="gtc", venue="alpaca-paper", mode="paper", by="person:ada", grant="g-paper")
        u = dict(t=T, order="o-a1b2c3d4e5f6", leg="stop-loss", state="cancelled", mode="paper", ref="alp-1004", src="venue")
        f = dict(t=T, sym="NRTH", side="sell", price="190.25", qty="10", order="o-a1b2c3d4e5f6", leg="take-profit", mode="paper", ref="fill-2")
        doc = declare_document(market(order(**o), order_update(**u), fill(**f)))["document"]
        self.assertEqual(doc, {"records": [{"kind": "order", **{("takeProfit" if k == "take_profit" else "stopLoss" if k == "stop_loss" else k): v for k, v in o.items()}}, {"kind": "order-update", **u}, {"kind": "fill", **f}]})
        c = dict(t=T, id="x-a1b2c3d4e5f6", venue="alpaca-paper", mode="paper", ref="alp-1004", order="o-a1b2c3d4e5f6", leg="stop-loss", by="person:ada", grant="g-paper")
        self.assertEqual(declare_document(market(cancel(**c)))["document"], {"records": [{"kind": "cancel", **c}]})
        with self.assertRaisesRegex(ValueError, r'<order> stopLoss is decimal text \("185.09"\), not a number'):
            declare_document(market(order(**{**o, "stop_loss": 180})))

    def test_what_the_vocabulary_has_no_words_for_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, r"<quote>: price is not read \(t, sym, last, bid, ask, vol\)"):
            declare_document(market(quote(t=T, sym="NRTH", price="1")))
        with self.assertRaisesRegex(ValueError, "<trade> needs price"):
            declare_document(market(trade(t=T, sym="NRTH", qty="1")))
        with self.assertRaisesRegex(ValueError, "<holding> stands in <account>, not in <book>"):
            declare_document(market(book(holding(sym="NRTH", qty="1"), t=T, sym="NRTH")))
        with self.assertRaisesRegex(ValueError, "<bid> stands in <book>, not in <market>"):
            declare_document(market(bid(price="1", qty="1")))
        with self.assertRaisesRegex(ValueError, "<market>: venue is not read"):
            declare_document(market(venue="sim"))

    def test_an_account_says_only_the_lists_it_has(self):
        d = declare_document(market(account(t=T, venue="sim", mode="sim")))
        self.assertEqual(d["document"]["records"], [{"kind": "account", "t": T, "venue": "sim", "mode": "sim"}])


if __name__ == "__main__":
    unittest.main()
