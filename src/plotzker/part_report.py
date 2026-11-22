"""Text and JSON reports of the part definitions (``python -m plotzker part``)."""

import json
from collections.abc import Mapping
from pathlib import Path

from plotzker.part import Part, part_to_dict
from plotzker.parts import PARTS, PRINTABLE_PARTS


def list_parts() -> str:
    """One line per printable part: its profile, material and FEM state."""
    rows = []
    for name in PRINTABLE_PARTS:
        part = PARTS.get(name)
        if part is None:
            rows.append(f"{name:<28} (not yet defined as a Part)")
        else:
            rows.append(
                f"{name:<28} {part.profile}/{part.material_data.name:<6} FEM: {part.fem_status}"
            )
    return "\n".join(rows)


def _get(name: str, parts: Mapping[str, Part]) -> Part:
    """The part called ``name``, or a helpful error."""
    if name in parts:
        return parts[name]
    hint = "not yet defined as a Part" if name in PRINTABLE_PARTS else "unknown part"
    raise SystemExit(f"{name}: {hint}. Defined: {', '.join(parts)}")


def export_part_stl(name: str, dest: Path, parts: Mapping[str, Part] = PARTS) -> None:
    """Write the part, in its analysis frame, as an STL file."""
    from pythonscad import export

    export(_get(name, parts).build(), str(dest))


def part_json(name: str, parts: Mapping[str, Part] = PARTS) -> str:
    """Everything the FEM sub-agent needs about a part, as JSON."""
    return json.dumps(part_to_dict(_get(name, parts)), indent=2)


def part_text(name: str, parts: Mapping[str, Part] = PARTS) -> str:
    """A readable summary of a part."""
    part = _get(name, parts)
    prof, mat = part.print_profile, part.material_data
    lines = [
        f"{part.name}: {part.description}",
        f"  analysis frame: {part.frame}; build direction {part.build_direction}",
        f"  print profile '{prof.name}': {prof.description}",
        f"  material {mat.name}: {mat.description}{' (assumed values)' if mat.assumed else ''}",
        f"  FEM: {part.fem_status}",
    ]
    if part.fem:
        lines.append(f"  safety factor {part.fem.safety_factor:g}")
        for case in part.fem.load_cases:
            kind = "sustained" if case.sustained else "peak"
            lines.append(f"  load case {case.name} ({kind}): {case.description}")
        lines += [f"  support {s.name}: {s.description}" for s in part.fem.supports]
        for lim in part.fem.displacement_limits:
            along = f"along {lim.direction}" if lim.direction else "magnitude"
            lines.append(f"  limit {lim.name}: {lim.limit_mm:g} mm {along}")
    return "\n".join(lines)
