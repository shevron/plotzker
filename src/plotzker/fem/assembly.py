"""Checking assemblies: the sum of the members' FEM displacements plus the play between them.

Works on the members' recorded results (``fem/results/<part>/result.json``), so the parts must
have been checked first, and their verdicts must be current (the verdicts file says which spec and
geometry each result belongs to). See :class:`cadder.assembly.AssemblyCheck`.
"""

import datetime
import hashlib
import json
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from cadder.assembly import AssemblyCheck, assembly_to_dict
from cadder.part import MaterialPart

from plotzker.fem.evaluate import Status, status_for, worst


@dataclass
class AssemblyRow:
    """One limit of one load case: the terms, their sum and the verdict."""

    name: str
    case: str
    terms: list[tuple[str, float]]
    total: float
    limit: float
    utilization: float
    status: Status


@dataclass
class AssemblyResult:
    """The outcome of an assembly check."""

    assembly: str
    status: Status
    rows: list[AssemblyRow] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """JSON-ready form."""
        return {
            "assembly": self.assembly,
            "status": self.status.value,
            "rows": [
                {
                    "name": r.name,
                    "case": r.case,
                    "terms": [{"term": d, "mm": v} for d, v in r.terms],
                    "total_mm": r.total,
                    "limit_mm": r.limit,
                    "utilization": r.utilization,
                    "status": r.status.value,
                }
                for r in self.rows
            ],
            "notes": self.notes,
        }


def _base(parts: Mapping[str, MaterialPart], name: str) -> str:
    """The part whose check applies to ``name`` (itself, or the original of a mirror image)."""
    return parts[name].mirror_of or name


def _member_values(results: Path, base: str) -> dict[tuple[str, str], float]:
    """(criterion name, load case) → value, from a part's recorded result."""
    path = results / base / "result.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text())
    return {(c["name"], c["case"]): float(c["value"]) for c in data.get("criteria", [])}


def check_assembly(
    assembly: AssemblyCheck,
    parts: Mapping[str, MaterialPart],
    results: Path,
    verdicts: Path | None = None,
) -> AssemblyResult:
    """Sum the members' displacements and the rigid terms per limit and load case; judge them."""
    values: dict[str, dict[tuple[str, str], float]] = {}
    notes: list[str] = []
    for member in assembly.members:
        base = _base(parts, member)
        values[member] = _member_values(results, base)
        if not values[member]:
            notes.append(f"{member}: no recorded FEM result under {results / base}; run it first")
    if notes:
        return AssemblyResult(assembly.name, Status.INCONCLUSIVE, notes=notes)
    recorded = _recorded(verdicts)
    for member in assembly.members:
        entry = recorded.get(_base(parts, member))
        if entry is not None and entry.get("verdict") == "INCONCLUSIVE":
            notes.append(f"{member}: its own check was inconclusive")
    cases = sorted({case for v in values.values() for _, case in v})
    rows = []
    for limit in assembly.limits:
        for case in cases:
            terms: list[tuple[str, float]] = []
            complete = True
            for term in limit.terms:
                if term.part is None:
                    terms.append((term.description, term.rigid_mm))
                    continue
                value = values[term.part].get((term.criterion or "", case))
                if value is None:
                    complete = False
                    notes.append(f"{term.part} has no {term.criterion} for load case {case}")
                    break
                terms.append((term.description, value))
            if not complete:
                continue
            total = sum(v for _, v in terms)
            utilization = total / limit.limit_mm
            rows.append(
                AssemblyRow(
                    limit.name, case, terms, total, limit.limit_mm, utilization,
                    status_for(utilization),
                )
            )  # fmt: skip
    status = worst([r.status for r in rows]) if rows and not notes else Status.INCONCLUSIVE
    return AssemblyResult(assembly.name, status, rows, notes)


def markdown(assembly: AssemblyCheck, result: AssemblyResult) -> str:
    """The report: verdict and, per limit and load case, every term of the sum."""
    lines = [
        f"# Assembly check: {assembly.name}",
        "",
        assembly.description,
        "",
        f"**Verdict: {result.status.value}**",
        "",
        "| Limit | Load case | Total | Limit | Used | Status |",
        "|---|---|---|---|---|---|",
    ]
    for r in result.rows:
        lines.append(
            f"| {r.name} | {r.case} | {r.total:.3f} | {r.limit:g} mm | {r.utilization:.0%} "
            f"| {r.status.value} |"
        )
    lines += ["", "## Terms (mm)", ""]
    for r in result.rows:
        parts = "; ".join(f"{d} {v:.3f}" for d, v in r.terms)
        lines.append(f"- {r.name} ({r.case}): {parts}")
    lines += ["", "## Notes", ""]
    lines += [f"- {n}" for n in result.notes] or ["- none"]
    lines += ["", f"Source: {assembly.source}", ""]
    return "\n".join(lines)


def _recorded(path: Path | None) -> dict[str, dict[str, str]]:
    """The verdicts file's entries."""
    if path is None or not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def spec_hash(assembly: AssemblyCheck, parts: Mapping[str, MaterialPart], verdicts: Path) -> str:
    """Hash of the assembly's definition and of the member verdicts it was computed from."""
    recorded = _recorded(verdicts)
    members = {m: recorded.get(_base(parts, m), {}) for m in assembly.members}
    text = json.dumps([assembly_to_dict(assembly), members], sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def update_verdicts(
    path: Path, assembly: AssemblyCheck, parts: Mapping[str, MaterialPart], result: AssemblyResult
) -> None:
    """Record the verdict of ``assembly`` next to the parts' (kept in the same sorted file)."""
    entries = _recorded(path)
    entries[assembly.name] = {
        "verdict": result.status.value,
        "date": datetime.date.today().isoformat(),
        "spec": spec_hash(assembly, parts, path),
    }
    lines = ["# Last FEM verdict per part (written by `python -m plotzker fem`).", ""]
    for name in sorted(entries):
        lines.append(f"[{name}]")
        lines += [f'{k} = "{v}"' for k, v in entries[name].items()]
        lines.append("")
    path.write_text("\n".join(lines))


def run_assemblies(
    names: list[str],
    parts: Mapping[str, MaterialPart],
    out_dir: Path,
    verdicts: Path | None,
    record: bool = True,
    log: Callable[[str], None] = print,
) -> list[AssemblyResult]:
    """Check the named assemblies from the members' recorded results; write the reports."""
    from plotzker.assembly_checks import ASSEMBLY_CHECKS

    results = []
    for name in names:
        assembly = ASSEMBLY_CHECKS[name]
        result = check_assembly(assembly, parts, out_dir, verdicts)
        folder = out_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "report.md").write_text(markdown(assembly, result))
        (folder / "result.json").write_text(json.dumps(result.to_dict(), indent=2))
        if verdicts is not None and record:
            update_verdicts(verdicts, assembly, parts, result)
        log(f"{name}: {result.status.value}; report: {folder / 'report.md'}")
        results.append(result)
    return results


def assembly_status_lines(
    assemblies: Mapping[str, AssemblyCheck], parts: Mapping[str, MaterialPart], verdicts: Path
) -> list[str]:
    """One line per assembly: its last verdict, and whether a member's verdict changed since."""
    recorded = _recorded(verdicts)
    lines = []
    for name, assembly in assemblies.items():
        entry = recorded.get(name)
        if entry is None:
            state = "never checked"
        elif entry.get("spec") != spec_hash(assembly, parts, verdicts):
            state = (
                f"STALE (a member or the assembly changed since {entry['date']}; "
                f"was {entry['verdict']})"
            )
        else:
            state = f"{entry['verdict']} ({entry['date']})"
        lines.append(f"{'assembly ' + name:<28} {state}")
    return lines
