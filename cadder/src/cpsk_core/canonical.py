"""Canonical constraint placement (spec §11.4): every constraint nested under one primitive."""

from __future__ import annotations

from cpsk_core.document import Comment, Document, Element, Node
from cpsk_core.reader import OPERANDS

_PRIMITIVES = ("point", "line", "circle", "arc")


def nest_constraints(document: Document) -> None:
    """Move the top-level constraints under their canonical parent primitives (spec §11.4).

    A constraint goes under the primitive that is or owns ``about`` (``symmetric``), otherwise
    under the operand primitive that comes first in document order; it is appended after the
    parent's other children. In the moved constraint the operand that is the parent itself is
    omitted and the parent's points are written with ``self``. Comments directly before a moved
    constraint move with it. Constraints that reference no primitive (only implicit references)
    and extension content stay at the top level; an empty ``<constraints>`` is removed.
    """
    geometry = document.container("geometry")
    constraints = document.container("constraints")
    if geometry is None or constraints is None:
        return
    order: dict[str, tuple[int, Element]] = {}
    for index, primitive in enumerate(geometry.elements()):
        identifier = primitive.get("id")
        if primitive.name in _PRIMITIVES and identifier is not None:
            order[identifier] = (index, primitive)
    kept: list[Node] = []
    pending: list[Comment] = []
    for child in constraints.children:
        if isinstance(child, Comment):
            pending.append(child)
            continue
        parent = _parent(child, order) if child.ours and child.name in OPERANDS else None
        if parent is None:
            kept += [*pending, child]
        else:
            order[parent][1].children += [*pending, _nested(child, parent)]
        pending = []
    kept += pending
    constraints.children = kept
    if not kept:
        document.root.children.remove(constraints)


def _parent(constraint: Element, order: dict[str, tuple[int, Element]]) -> str | None:
    def owner(reference: str | None) -> str | None:
        head = (reference or "").split(".")[0]
        return head if head in order else None

    if constraint.name == "symmetric":
        about = owner(constraint.get("about"))
        if about is not None:
            return about
    owners = {o for name in OPERANDS[constraint.name] if (o := owner(constraint.get(name)))}
    return min(owners, key=lambda o: order[o][0]) if owners else None


def _nested(constraint: Element, parent: str) -> Element:
    nested = Element(
        constraint.name,
        dict(constraint.attrs),
        constraint.children,
        constraint.text,
        constraint.namespace,
        constraint.line,
    )
    omitted = False
    for name in OPERANDS[constraint.name]:
        reference = nested.get(name)
        if reference == parent and not omitted:
            nested.set(name, None)
            omitted = True
        elif reference == parent:
            nested.set(name, "self")
        elif reference is not None and reference.startswith(f"{parent}."):
            nested.set(name, "self" + reference[len(parent) :])
    return nested
