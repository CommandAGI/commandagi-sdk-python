"""The 3D kernel: what a 3D document *is* once OpenCascade has built it.

``commandagi.design.threed`` declares a part; it builds nothing. :class:`Kernel` asks the CommandAGI 3D design service
to build it: its solids, their exact volume and area, a STEP file, a measurement, a drawing view. It speaks the kernel
contract (``POST <kernel>/v1/<op>``, ``GET <kernel>/v1/health``; the CommandAGI repository's docs/local-platform.md
§ kernels), which the service on this computer and the platform's door answer alike. One setting says where it runs::

    from commandagi.kernel import Kernel

    kernel = Kernel()                      # reads COMMANDAGI_THREED: "local,cloud" (the default) | "local" | "cloud"
    seen = kernel.observe(graph)           # bodies, faces, edges, volume, area, meshes; status and failures
    step = kernel.export(graph, "step")    # an ISO 10303-21 file, as text
    report = kernel.interference(graph, clearance=0.5)   # which bodies clash, engage in a thread, or are too near

A BUILD IN WHICH A FEATURE FAILED IS NOT WHOLE. ``observe`` answers it, with ``status == "failed"`` and ``failures``
(each failed feature, with why), so that it can be looked at and repaired. ``export``, ``measure``, ``interference``,
``drawing`` and ``tessellate`` refuse it: :class:`KernelError` with ``status`` 422 and the same ``failures``. A STEP
file cannot say that two features are missing from it.

``COMMANDAGI_THREED`` is the places to try, in order, words apart by ``,`` (the setting ``kernels.3d.place``). A place
where the kernel is not installed is passed over; a refusal of the op itself is the answer and is not asked elsewhere.

=================  =====================================================================================================
``local``          this computer, offline, no account. The SDK starts ``commandagi threed serve`` (the npm package
                   ``@commandagi/host``: ``npm install -g @commandagi/host`` then ``commandagi threed install``, once) and stops it
                   when Python exits. ``COMMANDAGI_THREED_URL`` (with ``COMMANDAGI_THREED_TOKEN``) names one that
                   runs already in its place.
``cloud``          the platform's kernel door, with your ``COMMANDAGI_API_KEY``. Needs the network and an account.
a URL              only a service that already runs (``commandagi threed serve``), with ``COMMANDAGI_THREED_TOKEN``.
=================  =====================================================================================================

Every answer says where it ran: ``Kernel.last_ran`` (``{"kernel", "build", "place"}``). The place is where this SDK sent
the request, never what the answer claims, so a result that ran on this computer says ``local`` and is never a cloud
result.

The standard library only: no ``requests``, so it imports wherever ``commandagi.design`` does.
"""
from __future__ import annotations

import atexit
import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from ._generated import DEFAULT_BASE_URL, ENV_API_KEY, ENV_BASE_URL

ENV_THREED = "COMMANDAGI_THREED"
ENV_THREED_URL = "COMMANDAGI_THREED_URL"
ENV_THREED_TOKEN = "COMMANDAGI_THREED_TOKEN"

__all__ = ["Kernel", "KernelError", "KernelAbsent", "linked_parts", "kernel_places", "call_kernel", "where_of", "ENV_THREED", "ENV_THREED_URL", "ENV_THREED_TOKEN"]


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



# ── the placement: a port of packages/domain/world/kernels.js ────────────────────────────────────────────────────────
#
# The CommandAGI repository has ONE function that chooses where a kernel call runs: `callKernel` in
# packages/domain/world/kernels.js, which the local host, the local platform's worker and the TypeScript SDK (a generated
# copy) run. Python cannot run it, so `kernel_places` and `call_kernel` are its port, rule for rule. A change there is
# a change here.

KERNEL_NAMES = ("3d", "fea")
# ``page`` is the workbench page's own kernel (``observe`` only): Python has no transport for it and passes it over.
KERNEL_PLACES = ("page", "local", "cloud")
# The page holds only the 3D kernel: the fea kernel's places begin on this computer.
DEFAULT_PLACES = {"3d": ("page", "local", "cloud"), "fea": ("local", "cloud")}


class KernelAbsent(Exception):
    """A transport's kernel is not there (not installed, not configured): the next place is tried."""


Transport = Callable[[str, Optional[Dict[str, Any]]], Tuple[int, Any]]


def kernel_places(name: str, value: Any) -> List[str]:
    """The places to try, in order, from the setting's value (a list, or the same list as one text with commas).
    None or empty: the 3D kernel's page, this computer, then the cloud (the fea kernel has no page)."""
    if name not in KERNEL_NAMES:
        raise ValueError(f'no kernel "{name}": one of {", ".join(KERNEL_NAMES)}')
    if value is None or value == "":
        return list(DEFAULT_PLACES[name])
    items = [p.strip() for p in value.split(",") if p.strip()] if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)) or not items or any(p not in KERNEL_PLACES for p in items) or len(set(items)) != len(items):
        raise ValueError(f'kernels.{name}.place is a list of "page", "local", "cloud", each at most once, not {json.dumps(value)}')
    return list(items)


def kernel_file(file: Any) -> Dict[str, str]:
    """A file as an input: its content id (sha256 of its bytes, hex) and its bytes (base64)."""
    data = file.encode("utf-8") if isinstance(file, str) else bytes(file)
    return {"id": hashlib.sha256(data).hexdigest(), "bytes": base64.b64encode(data).decode("ascii")}


def call_kernel(kernel: str, op: str, places: List[str], at: Dict[str, Optional[Transport]],
                files: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Tuple[int, Dict[str, Any]]:
    """One call of ``op`` → (status, body), the body with ``ran`` set from the place it was sent to. A place with no
    transport, a transport that raises :class:`KernelAbsent`, a 404 or a 503 ``kernel_unavailable`` falls to the next
    place; any other answer is the answer. When no place ran it: 503 ``kernel_unavailable`` with each place and why.
    ``op == "health"`` asks ``GET /v1/health``."""
    import re

    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", op):
        return 400, {"error": f'"{op}" is not an op name'}
    request = None
    if op != "health":
        request = {"inputs": {name: kernel_file(f) for name, f in (files or {}).items()}, "params": params or {}}
    tried: List[Dict[str, str]] = []
    for place in places:
        send = at.get(place)
        if send is None:
            tried.append({"place": place, "why": "no such place here"})
            continue
        try:
            status, body = send(f"/v1/{op}", request)
        except KernelAbsent as e:
            tried.append({"place": place, "why": str(e)})
            continue
        if not isinstance(body, dict):
            body = {"error": "the kernel answered something that is not a JSON object"}
        if status == 404 or (status == 503 and body.get("error") == "kernel_unavailable"):
            tried.append({"place": place, "why": f'no op "{op}"' if status == 404 else str(body.get("reason") or body.get("error"))})
            continue
        ran = body.get("ran")
        # An op's answer names its build in ``ran``; the health names it at the top.
        build = ran.get("build") if isinstance(ran, dict) and isinstance(ran.get("build"), str) else body.get("build") if isinstance(body.get("build"), str) else None
        return status, {**body, "ran": {"kernel": kernel, "build": build, "place": place}}
    why = "; ".join(f"{t['place']}: {t['why']}" for t in tried) or "no places"
    return 503, {"error": "kernel_unavailable", "reason": f"no place ran {kernel} {op}: {why}", "tried": tried}


def where_of(where: Optional[str], env: Dict[str, str]) -> Tuple[List[str], Optional[str]]:
    """Where a Kernel runs → (places, url of a running service or None). An argument wins, then ``COMMANDAGI_THREED``.
    A URL there is the one place (local, at that URL); ``COMMANDAGI_THREED_URL`` names the local place's service."""
    chosen = (where or env.get(ENV_THREED) or "").strip()
    if chosen.startswith(("http://", "https://")):
        return ["local"], chosen.rstrip("/")
    try:
        places = kernel_places("3d", chosen)
    except ValueError:
        raise ValueError(f'{ENV_THREED} is a list of "page", "local" and "cloud" apart by "," in the order to try (Python passes "page" over), or the URL of a running service, not {chosen!r}') from None
    url = (env.get(ENV_THREED_URL) or "").strip().rstrip("/")
    return places, url or None


def _http(url: str, key: str, body: Optional[Dict[str, Any]], timeout: float) -> Tuple[int, Any]:
    """One request → (status, its JSON). Raises OSError when there was no answer."""
    request = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(), method="GET" if body is None else "POST",
        headers={"authorization": f"Bearer {key}", **({} if body is None else {"content-type": "application/json"})},
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, timeout)) as answer:
            status, text = answer.status, answer.read().decode()
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode(errors="replace")
    try:
        return status, json.loads(text)
    except ValueError:
        return status, {"error": text[:300] or f"HTTP {status}"}


class _Local:
    """The one service this interpreter started (``commandagi threed serve``), shared by every local Kernel."""

    lock = threading.Lock()
    proc: Optional[subprocess.Popen] = None
    url = ""
    token = ""
    installed: Optional[str] = None  # None: not asked yet; "": installed; else why it is not

    @classmethod
    def absent(cls) -> str:
        """Why the local kernel cannot start here, or "" when it can. Asked once: ``commandagi threed status``."""
        with cls.lock:
            if cls.installed is None:
                cli = shutil.which("commandagi")
                if not cli:
                    cls.installed = "no `commandagi` command is on PATH (npm install -g @commandagi/host, then commandagi threed install)"
                else:
                    said: Any = None
                    try:
                        # Its standard output is one JSON object, printed over several lines.
                        out = subprocess.run([cli, "threed", "status"], capture_output=True, text=True, timeout=60)
                        heard = next(iter((out.stdout or out.stderr).strip().splitlines()), "nothing")
                        said = json.loads(out.stdout)
                    except (OSError, subprocess.SubprocessError) as e:
                        heard = str(e)
                    except ValueError:
                        pass
                    if not isinstance(said, dict):
                        cls.installed = (f"`{cli} threed status` gave no status (it said: {heard[:200]}); install the local 3D "
                                         "kernel with `npm install -g @commandagi/host` then `commandagi threed install`")
                    elif said.get("installed") is not True:
                        cls.installed = "the local 3D kernel is not installed (run `commandagi threed install` once)"
                    else:
                        cls.installed = ""
            return cls.installed

    @classmethod
    def ensure(cls, start_timeout: float) -> None:
        with cls.lock:
            if cls.proc is not None and cls.proc.poll() is None:
                return
            cli = shutil.which("commandagi")
            if not cli:
                raise KernelError(
                    "the local 3D kernel is the npm package `@commandagi/host`, and no `commandagi` command is on PATH. "
                    "Install it once: `npm install -g @commandagi/host` then `commandagi threed install`"
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
    """The 3D kernel, placed where ``where`` (or the environment) says. See the module's text."""

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
        self.places, self._url = where_of(where, dict(os.environ))
        self.timeout = timeout
        self._start_timeout = start_timeout
        self._key = api_key or os.environ.get(ENV_API_KEY) or ""
        self._base = (base_url or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")
        self._token = token or os.environ.get(ENV_THREED_TOKEN) or ""
        if self._url and not self._token:
            raise KernelError(f"a running 3D service asks for its bearer: pass token or set {ENV_THREED_TOKEN}")
        #: Where the last answer ran: ``{"kernel", "build", "place"}``. ``local`` is this computer, never the cloud.
        self.last_ran: Optional[Dict[str, Any]] = None

    # ── transports ───────────────────────────────────────────────────────────────────────────────────────────────
    def _local(self, path: str, body: Optional[Dict[str, Any]]) -> Tuple[int, Any]:
        if self._url:
            base, key = self._url, self._token
        else:
            why = _Local.absent()
            if why:
                raise KernelAbsent(why)
            _Local.ensure(self._start_timeout)
            base, key = _Local.url, _Local.token
        try:
            return _http(base + path, key, body, self.timeout)
        except (urllib.error.URLError, OSError) as e:
            raise KernelError(f"{path}: no answer from {base} ({getattr(e, 'reason', e)})") from None

    def _cloud(self, path: str, body: Optional[Dict[str, Any]]) -> Tuple[int, Any]:
        # The platform starts a host for the first caller and answers 503 until it is up: ask again until the time is
        # spent. A place that has no kernel (`kernel_unavailable`) is not waited for.
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                status, said = _http(f"{self._base}/kernels/3d{path}", self._key, body, deadline - time.monotonic())
            except (urllib.error.URLError, OSError) as e:
                raise KernelError(f"{path}: no answer from {self._base} ({getattr(e, 'reason', e)})") from None
            waiting = status == 503 and not (isinstance(said, dict) and said.get("error") == "kernel_unavailable")
            if waiting and time.monotonic() + 3 < deadline:
                time.sleep(3)
                continue
            return status, said

    def call(self, op: str, doc: Any = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """One op of the kernel contract → the whole answer (``outputs``, ``result``, ``ran``). Raises
        :class:`KernelError` with the kernel's refusal (``status``, and ``failures`` for a build that is not whole)."""
        status, body = call_kernel(
            "3d", op, self.places,
            {"local": self._local, "cloud": self._cloud if self._key else None},
            files={} if op == "health" else {"doc": _doc_text(doc)},
            params={k: v for k, v in (params or {}).items() if v is not None},
        )
        self.last_ran = body.get("ran")
        if status != 200:
            why = body.get("error") or body.get("reason") or f"HTTP {status}"
            if body.get("error") and body.get("reason"):
                why = f"{body['error']}: {body['reason']}"
            failures = body.get("failures") if isinstance(body.get("failures"), list) else None
            raise KernelError(f"{op}: {why} (HTTP {status})", status, failures)
        return body

    def _op(self, op: str, doc: Any, fields: Dict[str, Any]) -> Dict[str, Any]:
        return self.call(op, doc, fields)["result"]

    # ── what the kernel answers ──────────────────────────────────────────────────────────────────────────────────
    def observe(self, doc: Any, *, materials: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Build the document. ``observation``: each body's bounds, volume, area, faces, edges and vertices;
        ``observation["status"]`` (``"built"``, or ``"failed"``: a body is then built from what did not fail) and
        ``observation["failures"]`` (each failed feature, with why). ``meshes``: the triangles.

        A body whose ``engineering.material`` names a grade has its mass: ``mass["grams"]`` is its volume × that grade's
        density, and ``mass["massFrom"]`` says the row and its source. ``materials`` are the rows of your own tables,
        nearest first (``commandagi.design.standards.material``); the shipped table is read after them. A body with no
        grade has ``mass["noMass"]``."""
        return self._op("observe", doc, {"digest": "", "materials": materials or None})

    def sheet(self, doc: Any, *, sheet: Optional[str] = None, format: str = "svg", materials: Optional[List[Dict[str, Any]]] = None,
              parts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """An engineering drawing sheet the document declares (``sheet(…)``), as a file: ``content`` is its text (SVG,
        DXF), ``contentBase64`` its bytes (PDF). The views are projected from this build with hidden edges dashed, the
        dimensions are measured on it (``dimensions``: each one's value and text) and the title block is the document's
        engineering data. A document with a failed feature draws no sheet."""
        return self._op("sheet", doc, {"sheet": sheet, "format": format, "materials": materials, "parts": parts})

    def bom(self, doc: Any, *, parts: Optional[Dict[str, Any]] = None, materials: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """The bill of materials: ``lines`` (a line per part with its engineering data and its mass from this build) and
        the same table as ``csv``. ``parts`` are the files an assembly places (``linked_parts``): each placed 3D document
        is the lines of its own parts, and a file that is not given is a line with its name. ``failures``: each feature
        that failed to build (a line's mass is then of what was built)."""
        return self._op("bom", doc, {"parts": parts, "materials": materials})

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

    def check(self, doc: Any, *, parts: Optional[Dict[str, Any]] = None, devices: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """The checks the document declares (``check(kind=…)``), run on one build, with its ``accept`` and ``permitted``
        entries applied: each finding with its ``check``, ``rule``, ``severity``, ``body`` (id, name, part number),
        ``world`` and body-local ``local`` location; each check's ``status`` (``skipped`` with its ``reason`` when it could
        not run, never ``passed``) and its ``limits``. ``problems`` counts the standing errors and the skipped checks. A
        document that declares none gets the interference check.

        A manufacturability check (``printability``, ``mill``) that names a device definition (``options={"device":
        ref}``) reads its limits from ``devices``: ``{ref: {"process": <the definition's process block>}}``, which you
        read (the kernel has no files). A check whose device is not given is skipped with that reason."""
        return self._op("check", doc, {"parts": parts, "devices": devices})

    def dfm(self, doc: Any, *, process: str, limits: Dict[str, Any], setup: Optional[Dict[str, Any]] = None,
            part: Optional[str] = None, bodies: Optional[List[str]] = None, parts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Can this process make this part: the manufacturability checks of the built bodies, judged by ``limits`` (a
        device definition's ``process["print"]`` or ``process["mill"]``, each number with its ``source``). ``print``
        (FDM): build volume, a closed surface, overhangs, bridges, walls, vertical holes. ``mill`` (3-axis from +Z;
        ``setup={"tools": [{"diameter_mm": 3.175}], "stock_top_z"?: z}``): travel, a closed surface, reach, inside
        corners, depth, walls. Each finding is ``pass``, ``fail`` or ``unknown`` (a limit not declared, no tool: never
        ``pass``) with its ``value``, its ``limit`` and ``where`` (the body, the B-rep ``faces``, a point ``at``).
        ``verdict`` is ``fail`` when any fails, else ``unknown`` when any is unknown, else ``pass``. The part is
        checked as it stands in the model: Z is the build or spindle axis."""
        if process not in ("print", "mill"):
            raise ValueError(f'process is "print" or "mill", not {process!r}')
        return self._op("dfm", doc, {"process": process, "limits": limits, "setup": setup, "part": part, "bodies": bodies, "parts": parts})

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
