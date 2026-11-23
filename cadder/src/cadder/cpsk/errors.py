"""Diagnostics and errors reported by the CPSK reader and solver (spec §11.1)."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    """Whether a problem stops processing."""

    ERROR = "error"
    WARNING = "warning"


class Stage(StrEnum):
    """Where a problem was found."""

    LOAD = "load"
    SOLVE = "solve"
    EXPORT = "export"


@dataclass(frozen=True)
class Diagnostic:
    """One problem found in a document.

    ``code`` is a stable identifier for the kind of problem (e.g. ``"reference"``,
    ``"degrees-of-freedom"``), ``ids`` the identifiers or labels of the elements involved.
    """

    severity: Severity
    stage: Stage
    code: str
    message: str
    ids: tuple[str, ...] = ()
    line: int | None = None

    def __str__(self) -> str:
        where = f"line {self.line}: " if self.line is not None else ""
        return f"{self.severity} ({self.code}): {where}{self.message}"


def error(
    stage: Stage, code: str, message: str, *, ids: Iterable[str] = (), line: int | None = None
) -> Diagnostic:
    """An error diagnostic."""
    return Diagnostic(Severity.ERROR, stage, code, message, tuple(ids), line)


def warning(
    stage: Stage, code: str, message: str, *, ids: Iterable[str] = (), line: int | None = None
) -> Diagnostic:
    """A warning diagnostic."""
    return Diagnostic(Severity.WARNING, stage, code, message, tuple(ids), line)


class CpskError(Exception):
    """A document cannot be loaded, solved or exported; ``diagnostics`` says why."""

    def __init__(self, diagnostics: Iterable[Diagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__("\n".join(str(d) for d in self.diagnostics))


class CpskLoadError(CpskError):
    """The document is malformed or its references or formulas are invalid."""


class CpskSolveError(CpskError):
    """The constraints conflict or the solver did not converge."""


class CpskExportError(CpskError):
    """The solved geometry cannot be exported as requested."""
