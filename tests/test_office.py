"""Office documents declare the editors' own documents, as the TypeScript SDK's office JSX does (the same shapes as
sdk/typescript/src/design/office.test.ts), and say where each part was written. Run: python -m unittest discover -s tests"""
import textwrap
import unittest

from commandagi.design import run_module
from commandagi.design.office import (a, b, cell, column, deck, divider, h1, p, page, pre, read_deck, read_page, read_workbook, shape,
                                      sheet, slide, text, todo, workbook)


def run(src, path):
    return run_module(textwrap.dedent(src), path)


class WorkbookTests(unittest.TestCase):
    def test_a_workbook_declares_the_workbook_json(self):
        doc = read_workbook(workbook(sheet(column(at="B", width=120), cell(at="a1", value="Item", bold=True), cell(at="B2", formula="=1+1"),
                                           name="Q1", frozen_rows=1), title="Budget"))
        self.assertEqual(doc["document"], {
            "format": "workbook", "version": 1,
            "sheets": [{"id": "sheet-1", "name": "Q1", "kind": "grid", "rows": 200, "cols": 26,
                        "cells": {"A1": {"v": "Item", "fmt": {"bold": True}}, "B2": {"f": "=1+1"}},
                        "colWidths": {1: 120}, "frozen": {"rows": 1, "cols": 0}}],
            "meta": {"title": "Budget"},
        })
        with self.assertRaisesRegex(ValueError, "a formula starts with ="):
            read_workbook(workbook(sheet(cell(at="A1", formula="SUM(B1)"))))
        with self.assertRaisesRegex(TypeError, "<cell> holds nothing"):
            cell("Item", at="A1")

    def test_each_part_of_a_workbook_names_the_call_it_came_from(self):
        out = run("""\
            from commandagi.design.office import cell, column, sheet, workbook
            result = workbook(
                sheet(
                    column(at="A", width=90),
                    cell(at="A1", value=3),
                    name="S",
                ),
            )
            """, "Budget.sheet.py")
        self.assertEqual(out["graph"]["id"], "Budget")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["document"]["sheets"][0]["cells"], {"A1": {"v": 3}})
        src = out["document"]["sources"]
        self.assertEqual({k: (v["tag"], v["line"]) for k, v in src.items()},
                         {"workbook": ("workbook", 2), "sheet:sheet-1": ("sheet", 3), "column:sheet-1!A": ("column", 4), "cell:sheet-1!A1": ("cell", 5)})
        self.assertEqual(src["cell:sheet-1!A1"]["props"]["value"]["value"], 3)
        self.assertIn("sourceMap", out["graph"]["meta"])


class PageTests(unittest.TestCase):
    def test_a_page_declares_blocks_with_marks_as_inline_html(self):
        doc = read_page(page(h1("Notes"), p("One < two & ", b("bold"), " ", a("link", href="https://x.test")), todo("done", checked=True),
                             pre("a { }", lang="ts"), divider(), title="Notes"))
        self.assertEqual(doc["document"]["blocks"], [
            {"id": "block-1", "type": "h1", "html": "Notes"},
            {"id": "block-2", "type": "p", "html": 'One &lt; two &amp; <b>bold</b> <a href="https://x.test">link</a>'},
            {"id": "block-3", "type": "todo", "html": "done", "checked": True},
            {"id": "block-4", "type": "code", "html": "a { }", "lang": "ts"},
            {"id": "block-5", "type": "divider", "html": ""},
        ])

    def test_each_block_names_the_call_it_came_from(self):
        out = run("""\
            from commandagi.design.office import h1, p, page
            result = page(
                h1("Notes"),
                p("Text"),
            )
            """, "Notes.page.py")
        src = out["document"]["sources"]
        self.assertEqual({k: (v["tag"], v["line"]) for k, v in src.items()},
                         {"page": ("page", 2), "block:block-1": ("h1", 3), "block:block-2": ("p", 4)})


class DeckTests(unittest.TestCase):
    def test_a_deck_declares_the_decks_own_graph(self):
        g = read_deck(deck(slide(text("Hello ", b("world"), placeholder="title"), layout="Title"),
                           slide(shape(shape="ellipse", x=1, y=2, w=3, h=4), layout="Blank"), name="Pitch"))
        self.assertEqual(g["nodes"]["doc"]["inputs"], {"name": "Pitch", "width": 1280, "height": 720,
                                                       "slides.1": {"wire": {"node": "slide-1", "port": "out"}},
                                                       "slides.2": {"wire": {"node": "slide-2", "port": "out"}}})
        self.assertEqual(g["nodes"]["slide-1"]["inputs"], {"layout": "Title", "elements.1": {"wire": {"node": "slide-1.1", "port": "out"}}})
        self.assertEqual(g["nodes"]["slide-1.1"]["inputs"], {"placeholder": "title",
                                                             "text": {"paragraphs": [{"runs": [{"text": "Hello "}, {"text": "world", "bold": True}]}]}})
        self.assertEqual(g["nodes"]["slide-2.1"]["inputs"], {"box": {"x": 1, "y": 2, "w": 3, "h": 4}, "shape": "ellipse"})
        with self.assertRaisesRegex(ValueError, "needs x, y, w and h"):
            read_deck(deck(slide(shape(x=1))))

    def test_each_deck_node_names_the_call_it_came_from(self):
        out = run("""\
            from commandagi.design.office import deck, slide, text
            result = deck(
                slide(
                    text("Hi", placeholder="title", font_size=40),
                ),
            )
            """, "Pitch.deck.py")
        nodes = out["graph"]["nodes"]
        self.assertEqual({k: (n["meta"]["source"]["tag"], n["meta"]["source"]["line"]) for k, n in nodes.items()},
                         {"doc": ("deck", 2), "slide-1": ("slide", 3), "slide-1.1": ("text", 4)})
        self.assertEqual(nodes["slide-1.1"]["inputs"]["fontSizePx"], 40)
        self.assertEqual(nodes["slide-1.1"]["meta"]["source"]["props"]["font_size"]["value"], 40)


if __name__ == "__main__":
    unittest.main()
