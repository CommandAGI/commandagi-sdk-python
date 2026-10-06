"""Letters and postcards declared in Python give what the TypeScript SDK's JSX gives (postal.test.ts there): the
addresses, the paragraphs in order, a postcard's front image, and what the vocabulary has no words for refused by name.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.documents import declare_document
from commandagi.design.postal import from_, front, letter, paragraph, postcard, to

ADA = dict(name="Ada Lovelace", line1="12 St James's Square", city="London", postal_code="SW1Y 4JH", country="GB")
NORTHWIND = dict(name="Northwind", line1="1 Main St", city="Portland", region="OR", postal_code="97201", country="US")


class PostalTests(unittest.TestCase):
    def test_a_letter_is_its_addresses_and_paragraphs(self):
        d = declare_document(letter(to(**ADA), from_(**NORTHWIND), paragraph(text="Dear Ada,"), paragraph(text="It ships on Monday."),
                                    mail_class="first"))
        self.assertEqual(d, {"format": "letter", "sources": {}, "document": {
            "mailClass": "first",
            "to": {"name": "Ada Lovelace", "line1": "12 St James's Square", "city": "London", "postalCode": "SW1Y 4JH", "country": "GB"},
            "from": {"name": "Northwind", "line1": "1 Main St", "city": "Portland", "region": "OR", "postalCode": "97201", "country": "US"},
            "paragraphs": ["Dear Ada,", "It ships on Monday."]}})
        with self.assertRaisesRegex(ValueError, "street is not read"):
            declare_document(letter(to(street="x")))
        with self.assertRaisesRegex(ValueError, 'mailClass is "first" or "standard"'):
            declare_document(letter(mail_class="express"))
        with self.assertRaisesRegex(ValueError, "<letter> has one <to>"):
            declare_document(letter(to(), to()))
        with self.assertRaisesRegex(ValueError, "color is True or False"):
            declare_document(letter(color="yes"))
        with self.assertRaisesRegex(TypeError, "mailClass is written mail_class"):
            letter(mailClass="first")

    def test_a_postcard_has_one_front_and_no_options(self):
        d = declare_document(postcard(to(**ADA), front(image="Austin.jpg"), paragraph(text="Greetings from Austin!")))
        self.assertEqual(d["document"], {
            "to": {"name": "Ada Lovelace", "line1": "12 St James's Square", "city": "London", "postalCode": "SW1Y 4JH", "country": "GB"},
            "front": "Austin.jpg", "paragraphs": ["Greetings from Austin!"]})
        with self.assertRaisesRegex(ValueError, "needs image"):
            declare_document(postcard(front()))
        with self.assertRaisesRegex(ValueError, "color is not read"):
            declare_document(postcard(color=True))
        with self.assertRaisesRegex(ValueError, r"<front> is not a tag of a letter \(<letter>, <to>, <from>, <paragraph>\)"):
            declare_document(letter(front(image="x.jpg")))

    def test_a_run_names_each_element_by_its_call(self):
        out = run_module(
            "from commandagi.design.postal import letter, paragraph, to\n"
            "result = letter(\n"
            "    to(name=\"Ada\"),\n"
            "    paragraph(text=\"Dear Ada,\"),\n"
            "    color=False,\n"
            ")\n", "Letters/Ada.letter.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["document"], {"color": False, "to": {"name": "Ada"}, "paragraphs": ["Dear Ada,"]})
        sources = out["document"]["sources"]
        self.assertEqual(sorted(sources), ["", "paragraph@0", "to"])
        self.assertEqual((sources["to"]["tag"], sources["to"]["line"]), ("to", 3))
        self.assertEqual(sources["paragraph@0"]["props"]["text"]["value"], "Dear Ada,")


if __name__ == "__main__":
    unittest.main()
