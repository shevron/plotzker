"""Text and JSON reports of a project's parts (the ``part`` command)."""

import json
from collections.abc import Mapping
from pathlib import Path

from cadder.part import Part


def list_parts(parts: Mapping[str, Part]) -> str:
    """One line per part: its profile, material and FEM state."""
    return "\n".join(part.listing() for part in parts.values())


def _get(name: str, parts: Mapping[str, Part]) -> Part:
    """The part called ``name``, or a helpful error."""
    if name in parts:
        return parts[name]
    raise SystemExit(f"{name}: unknown part. Defined: {', '.join(parts)}")


def export_part_stl(name: str, dest: Path, parts: Mapping[str, Part]) -> None:
    """Write the part, in its analysis frame, as an STL file."""
    from pythonscad import export

    export(_get(name, parts).analysis_geometry(), str(dest))


def part_json(name: str, parts: Mapping[str, Part]) -> str:
    """Everything the FEM sub-agent needs about a part, as JSON."""
    return json.dumps(_get(name, parts).to_dict(), indent=2)


def part_text(name: str, parts: Mapping[str, Part]) -> str:
    """A readable summary of a part."""
    return "\n".join(_get(name, parts).describe())
