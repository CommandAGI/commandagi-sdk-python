"""A PDF declared in Python gives what the TypeScript SDK's JSX gives (pdf.test.ts there): pages by ref and blank,
marks with replies, fills, nested bookmarks, labels and attachments, and what the vocabulary has no words for refused
by name. Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design.documents import declare_document
from commandagi.design.pdf import attach, bookmark, field, fill, highlight, label, note, page, pdf, redact, reply, signature, stamp


class PdfTests(unittest.TestCase):
    def test_a_pdf_is_its_pages_marks_and_structure(self):
        d = declare_document(pdf(
            page(src="Contract.pdf", n=1),
            page(
                highlight(rects=[[72, 700, 300, 712]], author="Ada", text="Check"),
                note(reply(text="Because.", author="Bob"), at=[500, 700], text="Why?"),
                redact(rect=[72, 500, 300, 520]),
                field(kind="text", name="Name", rect=[72, 100, 300, 120]),
                src="Contract.pdf", n=3, rotate=90,
            ),
            page(size="a4"),
            fill(name="Name", value="Ada Lovelace"),
            bookmark(bookmark(title="Payment", page=2, top=500), title="Terms", page=2),
            label(from_=1, style="r"),
            attach(src="data.csv"),
            title="Signed", author="Ada",
        ))
        self.assertEqual(d["format"], "pdf")
        self.assertEqual(d["document"], {
            "title": "Signed", "author": "Ada",
            "pages": [
                {"src": "Contract.pdf", "n": 1},
                {"src": "Contract.pdf", "n": 3, "rotate": 90, "marks": [
                    {"type": "highlight", "rects": [[72, 700, 300, 712]], "author": "Ada", "text": "Check"},
                    {"type": "note", "at": [500, 700], "text": "Why?", "replies": [{"text": "Because.", "author": "Bob"}]},
                    {"type": "redact", "rect": [72, 500, 300, 520]},
                    {"type": "field", "kind": "text", "name": "Name", "rect": [72, 100, 300, 120]},
                ]},
                {"size": "a4"},
            ],
            "fill": [{"name": "Name", "value": "Ada Lovelace"}],
            "bookmarks": [{"title": "Terms", "page": 2, "children": [{"title": "Payment", "page": 2, "top": 500}]}],
            "labels": [{"from": 1, "style": "r"}],
            "attachments": [{"src": "data.csv"}],
        })

    def test_what_it_cannot_say_is_refused(self):
        with self.assertRaisesRegex(ValueError, "n is the page's number"):
            declare_document(pdf(page(src="a.pdf")))
        with self.assertRaisesRegex(ValueError, "blank page"):
            declare_document(pdf(page()))
        with self.assertRaisesRegex(ValueError, "<stamp> has a name"):
            declare_document(pdf(page(stamp(rect=[0, 0, 10, 10]), size="a4")))
        with self.assertRaisesRegex(ValueError, "one of typed, image or strokes"):
            declare_document(pdf(page(signature(rect=[0, 0, 10, 10], typed="A", image="s.png"), size="a4")))


if __name__ == "__main__":
    unittest.main()
