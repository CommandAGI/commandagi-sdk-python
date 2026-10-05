"""Office documents declare the editors' own documents, as the TypeScript SDK's office JSX does (the same shapes as
sdk/typescript/src/design/office.test.ts). Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import a, b, cell, column, deck, divider, h1, p, page, pre, run_module, shape, sheet, slide, text, todo, workbook


class WorkbookTests(unittest.TestCase):
    def test_a_workbook_declares_the_workbook_json(self):
        doc = workbook(sheet("Q1", column("B", 120), cell("a1", "Item", bold=True), cell("B2", formula="=1+1"), frozen_rows=1), title="Budget")
        self.assertEqual(doc.document, {
            "format": "sheetx", "version": 1,
            "sheets": [{"id": "sheet-1", "name": "Q1", "kind": "grid", "rows": 200, "cols": 26,
                        "cells": {"A1": {"v": "Item", "fmt": {"bold": True}}, "B2": {"f": "=1+1"}},
                        "colWidths": {1: 120}, "frozen": {"rows": 1, "cols": 0}}],
            "meta": {"title": "Budget"},
        })
        with self.assertRaisesRegex(ValueError, "a formula starts with ="):
            workbook(sheet("S", cell("A1", formula="SUM(B1)")))

    def test_run_module_hands_a_workbook_back_as_its_document(self):
        out = run_module('from commandagi.design import workbook, sheet, cell\nresult = workbook(sheet("S", cell("A1", 3)))', "Budget.sheet.py")
        self.assertEqual(out["graph"], {"id": "Budget", "nodes": {}})
        self.assertEqual(out["document"]["format"], "sheetx")
        self.assertEqual(out["document"]["document"]["sheets"][0]["cells"], {"A1": {"v": 3}})


class PageTests(unittest.TestCase):
    def test_a_page_declares_blocks_with_marks_as_inline_html(self):
        doc = page(h1("Notes"), p("One < two & ", b("bold"), " ", a("https://x.test", "link")), todo("done", checked=True), pre("a { }", lang="ts"), divider(), title="Notes")
        self.assertEqual(doc.document["blocks"], [
            {"id": "block-1", "type": "h1", "html": "Notes"},
            {"id": "block-2", "type": "p", "html": 'One &lt; two &amp; <b>bold</b> <a href="https://x.test">link</a>'},
            {"id": "block-3", "type": "todo", "html": "done", "checked": True},
            {"id": "block-4", "type": "code", "html": "a { }", "lang": "ts"},
            {"id": "block-5", "type": "divider", "html": ""},
        ])


class DeckTests(unittest.TestCase):
    def test_a_deck_declares_the_decks_own_graph(self):
        g = deck(slide(text("Hello ", b("world"), placeholder="title"), layout="Title"), slide(shape("ellipse", x=1, y=2, w=3, h=4), layout="Blank"), name="Pitch")
        self.assertEqual(g["nodes"]["doc"]["inputs"], {"name": "Pitch", "width": 1280, "height": 720,
                                                       "slides.1": {"wire": {"node": "slide-1", "port": "out"}}, "slides.2": {"wire": {"node": "slide-2", "port": "out"}}})
        self.assertEqual(g["nodes"]["slide-1"]["inputs"], {"layout": "Title", "elements.1": {"wire": {"node": "slide-1.1", "port": "out"}}})
        self.assertEqual(g["nodes"]["slide-1.1"]["inputs"], {"placeholder": "title", "text": {"paragraphs": [{"runs": [{"text": "Hello "}, {"text": "world", "bold": True}]}]}})
        self.assertEqual(g["nodes"]["slide-2.1"]["inputs"], {"box": {"x": 1, "y": 2, "w": 3, "h": 4}, "shape": "ellipse"})
        with self.assertRaisesRegex(ValueError, "needs x, y, w and h"):
            deck(slide(shape(x=1)))


if __name__ == "__main__":
    unittest.main()
