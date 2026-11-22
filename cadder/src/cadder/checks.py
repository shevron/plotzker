"""Design rules: a project yields ``(ok, message)`` pairs and :func:`run_design_checks` turns
the failures into one :class:`DesignError`."""

from collections.abc import Iterable


class DesignError(ValueError):
    """A design rule is violated."""


def run_design_checks(checks: Iterable[tuple[bool, str]]) -> None:
    """Raise :class:`DesignError` listing every failed rule."""
    failures = [message for ok, message in checks if not ok]
    if failures:
        raise DesignError("Design checks failed:\n  " + "\n  ".join(failures))
