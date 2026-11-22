"""Text and JSON reports of the part definitions (``python -m plotzker part``)."""

import json
from collections.abc import Mapping
from pathlib import Path

from cadder.part import MaterialPart, Part, PrintedPart, part_to_dict

from plotzker.parts import PARTS


def list_parts(parts: Mapping[str, Part] = PARTS) -> str:
    """One line per part: its profile, material and FEM state."""
    rows = []
    for name, part in parts.items():
        if isinstance(part, PrintedPart):
            setup = f"{part.profile.name}/{part.material.name:<6}"
        elif isinstance(part, MaterialPart):
            setup = f"{part.material.name:<14}"
        else:
            rows.append(f"{name:<28} ({part.fem_status})")
            continue
        rows.append(f"{name:<28} {setup} FEM: {part.fem_status}")
    return "\n".join(rows)


def _get(name: str, parts: Mapping[str, Part]) -> Part:
    """The part called ``name``, or a helpful error."""
    if name in parts:
        return parts[name]
    raise SystemExit(f"{name}: unknown part. Defined: {', '.join(parts)}")


def export_part_stl(name: str, dest: Path, parts: Mapping[str, Part] = PARTS) -> None:
    """Write the part, in its analysis frame, as an STL file."""
    from pythonscad import export

    part = _get(name, parts)
    solid = part.analysis_geometry() if isinstance(part, MaterialPart) else part.build()
    export(solid, str(dest))


def part_json(name: str, parts: Mapping[str, Part] = PARTS) -> str:
    """Everything the FEM sub-agent needs about a part, as JSON."""
    return json.dumps(part_to_dict(_get(name, parts)), indent=2)


def part_text(name: str, parts: Mapping[str, Part] = PARTS) -> str:
    """A readable summary of a part."""
    part = _get(name, parts)
    lines = [f"{part.name}: {part.description}"]
    if not isinstance(part, MaterialPart):
        return "\n".join([*lines, f"  {part.fem_status}"])
    mat = part.material
    if isinstance(part, PrintedPart):
        prof = part.profile
        frame = PrintedPart.OUTPUT_FRAME if part.frame == "output" else part.frame
        lines += [
            f"  analysis frame: {frame}; build direction {part.build_direction}",
            f"  print profile '{prof.name}': {prof.description}",
        ]
    else:
        lines.append(f"  analysis frame: {part.frame}; material axis {part.material_axis}")
    lines += [
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
