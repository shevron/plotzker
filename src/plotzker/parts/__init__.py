"""Printable parts, one module per part, each modeled in its print orientation.

:data:`PARTS` maps each part's name (= STL file name, ``stl/<name>.stl``) to its
:class:`~cadder.part.Part`. Parts with a print profile, material and FEM specification are
printed parts (:class:`~cadder.part.PrintedPart`, module-level ``PART``); the others are
plain ``Part`` objects until they get their data (``docs/fem.md``).
"""

from cadder.part import MaterialPart, Part

from plotzker.parts import (
    belt_clamp,
    gantry_end_bracket,
    idler_slider,
    loom_anchor,
    loom_rail,
    pen_holder_body,
    pen_slide,
    psu_bracket,
    psu_hood,
    x_carriage,
    x_endstop_mount,
    x_motor_mount,
    y_idler_mount,
    y_motor_mount,
    zrib_guard,
    zrib_hanger,
)
from plotzker.types import Side

#: Printed parts not yet given a print profile, material and FEM data
_PLAIN: dict[str, Part] = {
    part.name: part
    for part in (
        Part(
            name="belt_clamp",
            description="Belt clamp cap: clamps a belt end (×4 for Y, ×2 for X)",
            build=belt_clamp.belt_clamp,
        ),
        Part(
            name="loom_anchor",
            description="Loom anchor on the right gantry bracket",
            build=loom_anchor.loom_anchor,
        ),
        Part(name="loom_rail", description="Loom rail segment (×6)", build=loom_rail.loom_rail),
        Part(
            name="zrib_hanger",
            description="ZRIB hanger: carries the controller under the baseboard (×2)",
            build=zrib_hanger.zrib_hanger,
        ),
        Part(
            name="psu_hood",
            description="PSU terminal hood with the C14 inlet and the XT60 (×1)",
            build=psu_hood.psu_hood,
        ),
        Part(
            name="zrib_guard",
            description="ZRIB guard strap under the board's long edges (×2)",
            build=zrib_guard.zrib_guard,
        ),
    )
}

_PRINTED: dict[str, Part] = {
    part.name: part
    for part in (
        gantry_end_bracket.PART_LEFT,
        gantry_end_bracket.PART_RIGHT,
        x_endstop_mount.PART,
        idler_slider.PART,
        x_carriage.PART,
        pen_slide.PART,
        pen_holder_body.PART,
        psu_bracket.PART,
        x_motor_mount.PART,
        y_idler_mount.PART_LEFT,
        y_idler_mount.PART_RIGHT,
        y_motor_mount.PART_LEFT,
        y_motor_mount.PART_RIGHT,
    )
}

#: Order of listings and exports
_ORDER = [
    "gantry_end_bracket_left",
    "gantry_end_bracket_right",
    "belt_clamp",
    "loom_anchor",
    "loom_rail",
    "pen_holder_body",
    "pen_slide",
    "x_carriage",
    "zrib_hanger",
    "zrib_guard",
    "psu_bracket",
    "psu_hood",
    "x_motor_mount",
    "x_endstop_mount",
    "idler_slider",
] + [f"{kind}_{side.value}" for side in Side for kind in ("y_motor_mount", "y_idler_mount")]

#: Every part of the plotter, by name (= STL file name)
PARTS: dict[str, Part] = {name: (_PRINTED | _PLAIN)[name] for name in _ORDER}

#: The parts with a material (and so possibly an FEM check)
MATERIAL_PARTS: dict[str, MaterialPart] = {
    name: part for name, part in PARTS.items() if isinstance(part, MaterialPart)
}
