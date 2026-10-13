"""The 3D kernel: what a 3D document *is* once OpenCascade has built it.

``commandagi.design.threed`` declares a part; it builds nothing. :class:`Kernel` asks the CommandAGI 3D design service
to build it: its solids, their exact volume and area, a STEP file, a measurement, a drawing view. One service, in one
of three places, chosen by one setting::

    from commandagi.kernel import Kernel

    kernel = Kernel()                      # reads COMMANDAGI_THREED: "platform" (the default) | "local"
    seen = kernel.observe(graph)           # bodies, faces, edges, volume, area, meshes; status and failures
    step = kernel.export(graph, "step")    # an ISO 10303-21 file, as text
    report = kernel.interference(graph, clearance=0.5)   # which bodies clash, engage in a thread, or are too near

A BUILD IN WHICH A FEATURE FAILED IS NOT WHOLE. ``observe`` answers it, with ``status == "failed"`` and ``failures``
(each failed feature, with why), so that it can be looked at and repaired. ``export``, ``measure``, ``interference``,
``drawing`` and ``tessellate`` refuse it: :class:`KernelError` with ``status`` 422 and the same ``failures``. A STEP
file cannot say that two features are missing from it.

=================  =====================================================================================================
``platform``       the hosted service, with your ``COMMANDAGI_API_KEY``. Needs the network and an account.
``local``          this computer, offline, no account. The SDK starts ``commandagi threed serve`` (the ``commandagi``
                   npm package: ``npm install -g commandagi`` then ``commandagi threed install``, once) and stops it
                   when Python exits.
a URL              a service that already runs (``commandagi threed serve``), with ``COMMANDAGI_THREED_TOKEN``.
                   ``COMMANDAGI_THREED_URL`` names it too, as it does for the local host.
=================  =====================================================================================================

The standard library only: no ``requests``, so it imports wherever ``commandagi.design`` does.
"""
from __future__ import annotations

import atexit
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from ._generated import DEFAULT_BASE_URL, ENV_API_KEY, ENV_BASE_URL

ENV_THREED = "COMMANDAGI_THREED"
ENV_THREED_URL = "COMMANDAGI_THREED_URL"
ENV_THREED_TOKEN = "COMMANDAGI_THREED_TOKEN"

__all__ = ["Kernel", "KernelError", "linked_parts", "ENV_THREED", "ENV_THREED_URL", "ENV_THREED_TOKEN"]


class KernelError(Exception):
    """The service refused or could not be reached: ``status`` is its HTTP status (0 when there was no answer).
    ``failures``: for a build that is not whole, each feature that failed (``{"feature", "name"?, "type"?, "message"}``,
    in the order they were built); otherwise empty."""

    def __init__(self, message: str, status: int = 0, failures: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(message)
        self.status = status
        self.failures = list(failures or [])


def _doc_text(doc: Any) -> str:
    """The text the service reads: a 3D document's graph as JSON. ``doc`` is that text, the graph, or what a file
    declares (``part(...)``)."""
    if isinstance(doc, str):
        return doc
    if isinstance(doc, dict):
        return json.dumps(doc)
    from .design import graph_of
    from .design.element import Element, declarer_of

    declare = declarer_of(doc)
    if declare is None and isinstance(doc, Element):
        raise ValueError(f"<{doc.tag}> is not the root of a document (commandagi.design.{doc.module})")
    return json.dumps(declare(doc, "Part")["graph"] if declare else graph_of(doc))


def where_of(where: Optional[str], env: Dict[str, str]) -> str:
    """Which service: ``platform``, ``local`` or a URL. An argument wins, then ``COMMANDAGI_THREED_URL`` (a service that
    runs already), then ``COMMANDAGI_THREED``, then the platform."""
    chosen = (where or env.get(ENV_THREED_URL) or env.get(ENV_THREED) or "platform").strip()
    if chosen in ("platform", "local") or chosen.startswith(("http://", "https://")):
        return chosen.rstrip("/")
    raise ValueError(f"{ENV_THREED} is \"platform\", \"local\" or the URL of a running service, not {chosen!r}")


class _Local:
    """The one service this interpreter started (``commandagi threed serve``), shared by every local Kernel."""

    lock = threading.Lock()
    proc: Optional[subprocess.Popen] = None
    url = ""
    token = ""

    @classmethod
    def ensure(cls, start_timeout: float) -> None:
        with cls.lock:
            if cls.proc is not None and cls.proc.poll() is None:
                return
            cli = shutil.which("commandagi")
            if not cli:
                raise KernelError(
                    "the local 3D kernel is the `commandagi` npm package, and no `commandagi` command is on PATH. "
                    "Install it once: `npm install -g commandagi` then `commandagi threed install`"
                )
            # The bearer is made here and lives in this process and the child's environment only.
            token = secrets.token_hex(32)
            proc = subprocess.Popen(
                [cli, "threed", "serve", "--port", "0", "--with-parent"],
                env={**os.environ, ENV_THREED_TOKEN: token, ENV_THREED_URL: ""},
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            said: List[str] = []
            words: List[str] = []

            def keep_last_words() -> None:
                # Its own lines are read so the pipe never fills; the last ones say why a start failed.
                for line in proc.stderr:
                    words.append(line)
                    del words[:-20]

            threading.Thread(target=lambda: said.append(proc.stdout.readline()), daemon=True).start()
            threading.Thread(target=keep_last_words, daemon=True).start()
            deadline = time.monotonic() + start_timeout
            while not said and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            try:
                url = json.loads(said[0])["url"] if said and said[0].strip() else ""
            except (ValueError, KeyError, TypeError):
                url = ""
            if not url:
                proc.kill()
                why = " ".join(line.strip() for line in words[-3:]) or "no output"
                raise KernelError(f"`commandagi threed serve` did not start within {int(start_timeout)} s: {why}")
            cls.proc, cls.url, cls.token = proc, url, token
            atexit.register(cls.stop)

    @classmethod
    def stop(cls) -> None:
        proc, cls.proc = cls.proc, None
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.stdin.close()  # `--with-parent`: it stops when its standard input closes
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


class Kernel:
    """The 3D design service, where ``where`` (or the environment) says it is. See the module's text."""

    def __init__(
        self,
        where: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 300.0,
        start_timeout: float = 180.0,
    ) -> None:
        self.where = where_of(where, dict(os.environ))
        self.timeout = timeout
        self._start_timeout = start_timeout
        if self.where == "platform":
            self._key = api_key or os.environ.get(ENV_API_KEY)
            if not self._key:
                raise KernelError(f"the platform's 3D service needs an API key: pass api_key or set {ENV_API_KEY}, or set {ENV_THREED}=local")
            self._base = (base_url or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")
        elif self.where != "local":
            self._key = token or os.environ.get(ENV_THREED_TOKEN)
            if not self._key:
                raise KernelError(f"a running 3D service asks for its bearer: pass token or set {ENV_THREED_TOKEN}")
            self._base = self.where

    # ── transport ────────────────────────────────────────────────────────────────────────────────────────────────
    def _post(self, route: str, body: Dict[str, Any]) -> Dict[str, Any]:
        if self.where == "local":
            _Local.ensure(self._start_timeout)
            base, key = _Local.url, _Local.token
        else:
            base, key = self._base, self._key
        # The platform starts a host for the first caller and answers 503 until it is up: ask again until the time is
        # spent. A service on this computer is asked once.
        deadline = time.monotonic() + self.timeout
        while True:
            request = urllib.request.Request(
                base + route, data=json.dumps(body).encode(), method="POST",
                headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=max(1.0, deadline - time.monotonic())) as answer:
                    return json.loads(answer.read().decode())
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")
                failures = None
                try:
                    said = json.loads(text)
                    why = said.get("error") or said.get("reason") or text
                    if said.get("reason") and said.get("error"):
                        why = f"{said['error']}: {said['reason']}"
                    if isinstance(said.get("failures"), list):
                        failures = said["failures"]
                except ValueError:
                    why = text[:300]
                if e.code == 503 and self.where == "platform" and time.monotonic() + 3 < deadline:
                    time.sleep(3)
                    continue
                raise KernelError(f"{route}: {why} (HTTP {e.code})", e.code, failures) from None
            except (urllib.error.URLError, OSError) as e:
                raise KernelError(f"{route}: no answer from {base} ({getattr(e, 'reason', e)})") from None

    def _op(self, op: str, doc: Any, fields: Dict[str, Any]) -> Dict[str, Any]:
        body = {"docText": _doc_text(doc), **{k: v for k, v in fields.items() if v is not None}}
        if self.where == "platform":
            return self._post("/threed/op", {"op": op, **body})
        return self._post("/" + op, body)

    # ── what the kernel answers ──────────────────────────────────────────────────────────────────────────────────
    def observe(self, doc: Any, *, doc_id: Optional[str] = None) -> Dict[str, Any]:
        """Build the document. ``observation``: each body's bounds, volume, area, faces, edges and vertices;
        ``observation["status"]`` (``"built"``, or ``"failed"``: a body is then built from what did not fail) and
        ``observation["failures"]`` (each failed feature, with why). ``meshes``: the triangles."""
        text = _doc_text(doc)
        if self.where != "platform":
            return self._post("/observe", {"docText": text, "digest": ""})
        if doc_id is None:
            try:
                doc_id = str(json.loads(text).get("id") or "sdk")
            except ValueError:
                doc_id = "sdk"
        return self._post("/threed/observe", {"docId": doc_id, "docText": text, "digest": ""})

    # ``parts``, on every call below: the files an assembly places (``externalPart(file_name="bolt.3d.py")``), which
    # the service cannot read. ``linked_parts`` makes it from documents: {"bolt.3d.py": bolt, "bracket.step": text}.

    def export(self, doc: Any, format: str = "step", *, bodies: Optional[List[str]] = None, parts: Optional[Dict[str, Any]] = None) -> str:
        """The document as a STEP (``step``) or IGES (``iges``) file's text; ``bodies`` keeps only those body ids. A
        STEP file names each body as a product of its part's name, and an assembly as the product they are components of."""
        return self._op("export", doc, {"format": format, "bodies": bodies, "parts": parts})["content"]

    def measure(self, doc: Any, quantity: str, a: Dict[str, Any], b: Optional[Dict[str, Any]] = None, *, parts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """``distance`` | ``angle`` | ``closest`` between two entities, or the ``radius`` of one: ``{"value"}``, or
        ``{"points": {"a", "b"}}`` for ``closest``. An entity is ``{"body": "body_0", "kind": "body" | "face" | "edge" |
        "vertex", "index": n}``, the index as observe lists it."""
        return self.measure_all(doc, [{"quantity": quantity, "a": a, **({"b": b} if b is not None else {})}], parts=parts)[0]

    def measure_all(self, doc: Any, measures: List[Dict[str, Any]], *, parts: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Many measurements on ONE build: each ``{"quantity", "a", "b"?}``, answered in the same order."""
        return self._op("measure", doc, {"measures": measures, "parts": parts})["results"]

    def interference(self, doc: Any, *, clearance: Optional[float] = None, bodies: Optional[List[str]] = None, parts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Every pair of bodies, compared on one build. ``clashes``: pairs that occupy the same space (``volume``, mm³).
        ``engagements``: pairs whose shared volume all lies in a declared thread (a screw in a tapped hole: a ``thread``
        feature on the hole or on the screw says so; without it the same overlap is a clash). ``close``: with
        ``clearance`` (mm), pairs that share no volume and are nearer than it, with the ``distance`` and the nearest
        ``points``. ``bodies`` lists each body's id, part name and volume."""
        return self._op("interference", doc, {"clearance": clearance, "bodies": bodies, "parts": parts})

    def drawing(self, doc: Any, *, direction: Optional[List[float]] = None, up: Optional[List[float]] = None,
                bodies: Optional[List[str]] = None, section: Optional[Dict[str, Any]] = None, parts: Optional[Dict[str, Any]] = None) -> Any:
        """A drawing view with hidden lines removed: the visible and hidden edges projected along ``direction``."""
        return self._op("drawing", doc, {"direction": direction, "up": up, "bodies": bodies, "section": section, "parts": parts})["projection"]

    def tessellate(self, doc: Any, deflection: float, *, bodies: Optional[List[str]] = None, parts: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Each body's triangles at this chord deflection (mm): ``{"id", "name", "triangles", "mesh"}``."""
        return self._op("tessellate", doc, {"deflection": deflection, "bodies": bodies, "parts": parts})["bodies"]


def linked_parts(files: Dict[str, Any]) -> Dict[str, Any]:
    """The ``parts`` of a call, from the files an assembly places, by the name each placement gives (``file_name`` or
    ``path``): a 3D document (what its file declares, its graph, or the graph's text) or, for a ``.step`` / ``.stp`` /
    ``.iges`` / ``.igs`` name, the file's text. A document placed inside a placed document is listed here too."""
    out: Dict[str, Any] = {}
    for name, value in files.items():
        lower = name.lower()
        fmt = "step" if lower.endswith((".step", ".stp")) else "iges" if lower.endswith((".iges", ".igs")) else None
        if fmt:
            if not isinstance(value, str):
                raise ValueError(f"{name}: a {fmt.upper()} file is given as its text")
            out[f"{fmt}:name:{name}"] = {"format": fmt, "data": value}
        elif any(lower.endswith(f".3d.{ext}") for ext in ("tsx", "jsx", "py", "rs")):
            out[f"3d:name:{name}"] = {"docText": _doc_text(value)}
        else:
            raise ValueError(f"{name}: a placed file the kernel builds is a 3D document (.3d.tsx, .3d.py, .3d.rs), a STEP file or an IGES file")
    return out
