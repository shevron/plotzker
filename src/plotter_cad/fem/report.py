"""Written results of a run: the Markdown report and the committed verdicts file."""

import datetime
import hashlib
import json
import tomllib
from pathlib import Path

from plotter_cad.fem.runner import FemResult
from plotter_cad.part import Part, part_to_dict


def spec_hash(part: Part) -> str:
    """Hash of everything the check depends on besides geometry (part properties)."""
    return hashlib.sha256(json.dumps(part_to_dict(part), sort_keys=True).encode()).hexdigest()[:16]


def file_hash(path: Path) -> str:
    """Short hash of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def markdown(result: FemResult) -> str:
    """The report: verdict, criteria, sanity checks, assumptions."""
    lines = [
        f"# FEM check: {result.part}",
        "",
        f"**Verdict: {result.status.value}** ({result.seconds:g} s)",
        "",
        "| Criterion | Load case | Value | Limit | Used | Status |",
        "|---|---|---|---|---|---|",
    ]
    for c in result.criteria:
        lines.append(
            f"| {c.name} | {c.case} | {c.value:g} | {c.limit:g} {c.unit} | {c.utilization:.0%} "
            f"| {c.status.value} |"
        )
    lines += ["", "Details:", ""]
    lines += [f"- {c.name} ({c.case}): {c.detail}" for c in result.criteria if c.detail]
    lines += ["", "## Sanity checks", ""]
    lines += [f"- {'ok' if c.ok else '**FAILED**'} {c.name}: {c.detail}" for c in result.checks]
    if result.pictures:
        lines += ["", "## Pictures", ""]
        lines += [f"- [{p}]({p})" for p in result.pictures]
        lines += [
            "",
            "Utilization = failure index × safety factor (1.0 = at the allowable; blue is fine, "
            "red is over). The `.vtu` files open in ParaView or FreeCAD.",
        ]
    lines += ["", "## Assumed inputs", ""]
    lines += [f"- {a}" for a in result.assumed]
    lines += ["", "## Notes", ""]
    lines += [f"- {n}" for n in result.notes]
    lines += ["", f"Mesh: {json.dumps(result.mesh)}", ""]
    return "\n".join(lines)


def update_verdicts(path: Path, part: Part, result: FemResult, geometry_hash: str) -> None:
    """Record the verdict, date and input hashes of ``part`` in the committed verdicts file."""
    entries: dict[str, dict[str, str]] = {}
    if path.is_file():
        with path.open("rb") as f:
            entries = tomllib.load(f)
    entries[part.name] = {
        "verdict": result.status.value,
        "date": datetime.date.today().isoformat(),
        "geometry": geometry_hash,
        "spec": spec_hash(part),
    }
    lines = ["# Last FEM verdict per part (written by `python -m plotter_cad fem`).", ""]
    for name in sorted(entries):
        lines.append(f"[{name}]")
        lines += [f'{k} = "{v}"' for k, v in entries[name].items()]
        lines.append("")
    path.write_text("\n".join(lines))
