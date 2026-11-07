"""A connector declared in Python gives what the TypeScript vocabulary's JSX gives (connectors.ts in the CommandAGI
repository): each element is its record, and a connector that does not read is refused with why.
Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.connectors import CONNECTORS_VOCABULARY, connector, credential, dir, each, file, folder, here, licence, request
from commandagi.design.documents import declare_document

EXAMPLE = {
    "name": "Poly Haven", "base": "https://api.polyhaven.com", "rate": 2, "cache": 86400,
    "home": "https://polyhaven.com", "hosts": ["dl.polyhaven.org"], "licence": "CC0-1.0", "credit": "Poly Haven",
    "credential": {"service": "data-gov", "field": "API_KEY", "query": "api_key", "optional": True},
    "licences": [{"value": "CC0", "spdx": "CC0-1.0"}],
    "folders": [
        {"path": "", "produce": [{"kind": "dir", "name": "models"}]},
        {"path": "models", "get": "/assets?type=models", "produce": [
            {"kind": "each", "in": "$", "as": "a", "produce": [
                {"kind": "dir", "name": "{a}", "title": "{a/name}", "author": "{a/authors|keys|join:, }"}]}]},
        {"path": "models/{slug}", "get": "/files/{slug}",
         "requests": [{"as": "info", "get": "/info/{slug}"}],
         "here": {"source": "https://polyhaven.com/a/{slug}"},
         "produce": [{"kind": "each", "in": "$/gltf", "as": "res", "produce": [
             {"kind": "file", "path": "{res}/{slug}_{res}.gltf", "url": "{res/gltf/url}", "size": "{res/gltf/size}"},
             {"kind": "file", "path": "{res}/pack.zip/a.glb", "zip": "{res/zip/url}", "member": "a.glb"}]}]},
    ],
}

ROOT = dict(name="S", base="https://api.example.com", rate=1, cache=3600)


def poly_haven():
    return connector(
        credential(service="data-gov", field="API_KEY", query="api_key", optional=True),
        licence(value="CC0", spdx="CC0-1.0"),
        folder(dir(name="models"), path=""),
        folder(each(dir(name="{a}", title="{a/name}", author="{a/authors|keys|join:, }"), in_="$", as_="a"),
               path="models", get="/assets?type=models"),
        folder(
            request(as_="info", get="/info/{slug}"),
            here(source="https://polyhaven.com/a/{slug}"),
            each(
                file(path="{res}/{slug}_{res}.gltf", url="{res/gltf/url}", size="{res/gltf/size}"),
                file(path="{res}/pack.zip/a.glb", zip="{res/zip/url}", member="a.glb"),
                in_="$/gltf", as_="res"),
            path="models/{slug}", get="/files/{slug}"),
        name="Poly Haven", base="https://api.polyhaven.com", rate=2, cache=86400, home="https://polyhaven.com",
        hosts=["dl.polyhaven.org"], licence="CC0-1.0", credit="Poly Haven",
    )


def bad(*children, **attrs):
    return lambda: declare_document(connector(*(children or (folder(path=""),)), **{**ROOT, **attrs}))


class ConnectorTests(unittest.TestCase):
    def test_the_example_is_its_document_both_ways(self):
        d = declare_document(poly_haven())
        self.assertEqual(d["format"], "connector")
        self.assertEqual(d["document"], EXAMPLE)
        self.assertEqual(CONNECTORS_VOCABULARY.from_tree(CONNECTORS_VOCABULARY.to_tree(EXAMPLE)), EXAMPLE)

    def test_a_connector_that_does_not_read_is_refused_with_why(self):
        cases = [
            (bad(base="http://api.example.com"), "base is the API's https url"),
            (bad(rate=50), "rate is the requests a second it makes at most"),
            (bad(cache=5), "cache is the seconds a listing is kept"),
            (bad(dir(name="x")), "<dir> stands in <folder> or <each>, not in <connector>"),
            (lambda: declare_document(connector(**ROOT)), "declares no <folder>"),
            (bad(folder(path="a//b")), r"path is names and \{var\} segments"),
            (bad(folder(file(path="x.glb"), path="")), "reads its bytes from url, or from zip and member"),
            (bad(folder(file(path="x.glb", zip="https://a/x.zip"), path="")), "zip and member go together"),
            (bad(folder(each(in_="$", as_="$"), path="")), "as is a name"),
            (bad(folder(path="", get="/x", page="start")), "it needs pageSize"),
            (bad(credential(service="data-gov", field="API_KEY"), folder(path="")), "a query parameter or a header"),
            (bad(folder(each(in_="$", as_="x", where="k", is_=1, not_=2), path="")), "where goes with is or with not: one of them"),
            (bad(folder(each(in_="$", as_="x", where="k", is_=[1]), path="")), "is is a text, a number or true/false"),
            (bad(folder(each(in_="$", as_="x", where="k", not_=[1]), path="")), "not is a text, a number or true/false"),
            (bad(folder(dir(name="a", id=3), path="")), "dir> id is a text"),
            (bad(folder(path="", get="/x", page="start")), r"it needs pageSize \(by offset\) or next \(by a token\)"),
            (bad(folder(path="", get="/x", page="link", next="{$/n}")), "next is the template of the next page's token"),
            (bad(folder(path=""), folder(path="")), r'two <folder> in <connector> have path ""|has two <folder path="">'),
        ]
        for fn, why in cases:
            with self.assertRaisesRegex(ValueError, why, msg=why):
                fn()

    def test_id_not_and_next_are_read(self):
        d = declare_document(connector(
            folder(each(dir(name="{a}", id="{a/id}"), in_="$", as_="a", where="k", not_="x"),
                   path="", get="/x", page="cursor", next="{$/n}"),
            **ROOT))["document"]["folders"][0]
        self.assertEqual(d["next"], "{$/n}")
        self.assertEqual(d["produce"][0]["not"], "x")
        self.assertEqual(d["produce"][0]["produce"][0]["id"], "{a/id}")

    def test_a_run_gives_the_document(self):
        out = run_module(
            "from commandagi.design.connectors import connector, dir, folder\n"
            "result = connector(\n"
            "    folder(dir(name=\"models\"), path=\"\"),\n"
            "    name=\"S\", base=\"https://api.example.com\", rate=1, cache=3600,\n"
            ")\n", "connectors/s.connector.py")
        self.assertEqual(out["graph"]["nodes"], {})
        self.assertEqual(out["document"]["format"], "connector")
        self.assertEqual(out["document"]["document"]["folders"], [{"path": "", "produce": [{"kind": "dir", "name": "models"}]}])


if __name__ == "__main__":
    unittest.main()
