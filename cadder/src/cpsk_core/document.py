"""The lossless CPSK document: an element tree that keeps everything a file says.

Parsing keeps formulas as written, attribute order, comments, metadata text, unknown elements and
extension content (other namespaces), so a document can be read, changed and written back. The
writer produces the canonical layout described in :func:`write`. The compiler
(:mod:`cpsk_core.reader`) turns a document into a :class:`cpsk_core.model.Sketch`.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeAlias
from xml.parsers import expat

from cpsk_core.errors import CpskLoadError, Stage, error

NAMESPACE = "https://github.com/shevron/plotzker/ns/cpsk"
"""The CPSK XML namespace (spec §2)."""

CONTAINERS = ("metadata", "variables", "geometry", "constraints")
"""The root's containers, in document order (spec §2)."""

QName: TypeAlias = tuple[str | None, str]
"""An attribute name: (namespace or ``None`` for an unqualified attribute, local name)."""


@dataclass
class Comment:
    """An XML comment, kept in its place."""

    text: str


@dataclass
class Element:
    """An element: CPSK (in :data:`NAMESPACE`) or an extension (any other namespace)."""

    name: str
    attrs: dict[QName, str] = field(default_factory=dict)
    children: list[Node] = field(default_factory=list)
    text: str = ""
    namespace: str | None = NAMESPACE
    line: int | None = None
    """Source line, for messages; ``None`` for elements built in code."""

    @property
    def ours(self) -> bool:
        """Whether this is a CPSK element."""
        return self.namespace == NAMESPACE

    def get(self, name: str) -> str | None:
        """An unqualified attribute."""
        return self.attrs.get((None, name))

    def set(self, name: str, value: str | None) -> None:
        """Set (or, with ``None``, remove) an unqualified attribute."""
        if value is None:
            self.attrs.pop((None, name), None)
        else:
            self.attrs[(None, name)] = value

    def elements(self, name: str | None = None) -> Iterator[Element]:
        """The CPSK child elements, optionally only those called ``name``."""
        for child in self.children:
            if isinstance(child, Element) and child.ours and (name is None or child.name == name):
                yield child

    def first(self, name: str) -> Element | None:
        """The first CPSK child element called ``name``."""
        return next(self.elements(name), None)

    def append(self, child: Element) -> Element:
        """Add a child at the end; returns it."""
        self.children.append(child)
        return child


Node: TypeAlias = Element | Comment


@dataclass
class Document:
    """A CPSK document: the ``<sketch>`` element and the comments before it."""

    root: Element
    prolog: list[Comment] = field(default_factory=list)
    prefixes: dict[str, str] = field(default_factory=dict)
    """Namespace URI → prefix, as declared in the source; used when writing extensions."""

    @classmethod
    def new(cls, *, version: str = "0.1", unit_length: str | None = None, unit_angle: str | None = None) -> Document:
        """An empty document."""
        root = Element("sketch")
        root.set("version", version)
        root.set("unit-length", unit_length)
        root.set("unit-angle", unit_angle)
        return cls(root)

    def container(self, name: str, *, create: bool = False) -> Element | None:
        """A root container (``metadata``, ``variables``, ``geometry``, ``constraints``).

        With ``create``, a missing container is added in its place in the document order.
        """
        found = self.root.first(name)
        if found is not None or not create:
            return found
        element = Element(name)
        rank = CONTAINERS.index(name)
        position = len(self.root.children)
        for index, child in enumerate(self.root.children):
            if not (isinstance(child, Element) and child.ours and child.name in CONTAINERS):
                continue
            if CONTAINERS.index(child.name) > rank:
                position = index
                break
        self.root.children.insert(position, element)
        return element


# ----- Building elements in code -----


def element(name: str, **attrs: str | float | bool | None) -> Element:
    """A CPSK element; keyword names use ``_`` for ``-`` (``start_angle`` → ``start-angle``).

    Numbers are written with :func:`format_number`, booleans as ``true``/``false``, and ``None``
    values are left out.
    """
    created = Element(name)
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, bool):
            text = "true" if value else "false"
        elif isinstance(value, int | float):
            text = format_number(value)
        else:
            text = value
        created.set(key.replace("_", "-"), text)
    return created


def format_number(value: float) -> str:
    """The shortest text that reads back as the same binary64 value (spec §11.4)."""
    if not math.isfinite(value):
        raise ValueError(f"not a finite number: {value}")
    if value == int(value) and abs(value) < 1e16:
        return str(int(value))
    return repr(float(value))


# ----- Parsing -----


def parse(text: str | bytes) -> Document:
    """Parse a document without interpreting it; raises :class:`CpskLoadError` for bad XML."""
    parser = expat.ParserCreate(namespace_separator=" ")
    stack: list[Element] = []
    roots: list[Element] = []
    prolog: list[Comment] = []
    prefixes: dict[str, str] = {}

    def split(name: str) -> tuple[str | None, str]:
        namespace, _, local = name.rpartition(" ")
        return (namespace or None), local

    def start(name: str, attrs: dict[str, str]) -> None:
        namespace, local = split(name)
        attributes = {split(key): value for key, value in attrs.items()}
        created = Element(local, attributes, namespace=namespace, line=parser.CurrentLineNumber)
        (stack[-1].children if stack else roots).append(created)
        stack.append(created)

    def end(name: str) -> None:
        stack.pop()

    def data(text: str) -> None:
        if stack:
            stack[-1].text += text

    def comment(text: str) -> None:
        if stack:
            stack[-1].children.append(Comment(text))
        elif not roots:
            prolog.append(Comment(text))

    def namespace_declaration(prefix: str | None, uri: str) -> None:
        if prefix:
            prefixes.setdefault(uri, prefix)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = data
    parser.CommentHandler = comment
    parser.StartNamespaceDeclHandler = namespace_declaration
    try:
        parser.Parse(text, True)
    except expat.ExpatError as e:
        message = f"malformed XML: {expat.errors.messages[e.code]}"
        raise CpskLoadError([error(Stage.LOAD, "xml", message, line=e.lineno)]) from None
    return Document(roots[0], prolog, prefixes)


def read(path: str | Path) -> Document:
    """Parse a document file (see :func:`parse`)."""
    return parse(Path(path).read_bytes())


# ----- Writing -----

_INDENT = "  "


def write(document: Document) -> str:
    """The document as canonical XML text.

    Layout: an XML declaration, the prolog comments, then one element per line indented by two
    spaces, attributes in their stored order on the element's line, a blank line between the
    root's children and between geometry primitives that have nested constraints. Text is kept
    only in elements without child elements (metadata). Extension namespaces are declared on the
    root with their source prefixes (or ``ns1``, ``ns2``, …).
    """
    prefixes = dict(document.prefixes)
    used = sorted({ns for ns in _namespaces(document.root) if ns != NAMESPACE})
    for uri in used:
        if uri not in prefixes:
            prefixes[uri] = f"ns{len(prefixes) + 1}"
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines += [f"<!--{c.text}-->" for c in document.prolog]
    declarations = [f'xmlns="{NAMESPACE}"'] + [f'xmlns:{prefixes[u]}="{_attr(u)}"' for u in used]
    _write(document.root, 0, lines, prefixes, declarations)
    return "\n".join(lines) + "\n"


def save(document: Document, path: str | Path) -> None:
    """Write a document to a file (see :func:`write`)."""
    Path(path).write_text(write(document), encoding="utf-8")


def _namespaces(element: Element) -> Iterator[str]:
    if element.namespace is not None:
        yield element.namespace
    for namespace, _ in element.attrs:
        if namespace is not None:
            yield namespace
    for child in element.children:
        if isinstance(child, Element):
            yield from _namespaces(child)


def _write(
    element: Element,
    depth: int,
    lines: list[str],
    prefixes: dict[str, str],
    declarations: Sequence[str] = (),
) -> None:
    indent = _INDENT * depth
    name = _name(element.namespace, element.name, prefixes)
    attrs = [*declarations] + [
        f'{_name(ns, local, prefixes)}="{_attr(value)}"' for (ns, local), value in element.attrs.items()
    ]
    opening = f"{indent}<{' '.join([name, *attrs])}"
    if not element.children:
        text = element.text.strip()
        lines.append(f"{opening}>{_text(text)}</{name}>" if text else f"{opening}/>")
        return
    lines.append(f"{opening}>")
    separated = element.namespace == NAMESPACE and element.name in ("sketch", "geometry")
    previous: Element | None = None
    pending: list[str] = []
    for child in element.children:
        if isinstance(child, Comment):
            pending.append(f"{indent}{_INDENT}<!--{child.text}-->")
            continue
        if previous is not None and separated and (element.name == "sketch" or previous.children or child.children):
            lines.append("")
        lines += pending
        pending = []
        _write(child, depth + 1, lines, prefixes)
        previous = child
    lines += pending
    lines.append(f"{indent}</{name}>")


def _name(namespace: str | None, local: str, prefixes: dict[str, str]) -> str:
    if namespace is None or namespace == NAMESPACE:
        return local
    return f"{prefixes[namespace]}:{local}"


def _attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace('"', "&quot;")
        .replace("\n", "&#10;")
        .replace("\t", "&#9;")
    )


def _text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
