"""Assemblies whose parts are checked together on the sum of their deflections and play.

A part's own FEM check holds its neighbours rigid, so deflections that are small in each part
but add up, and play between parts, go unseen. The belt tensioners are the case that taught
this (STATUS.md T3.19): the belt pulls the idler axle above the tension screw, the slider
tilts in its dovetail by the clearance, and the mount's ridge and block bend, so the idler
leans although each part alone passes its 0.1 mm.

Limits are the sum of the members' own limits (nothing new is decided): both parts may use
their budget at most, and play is an extra that must fit in it.
"""

from plotter_cad.params import Y_TENSIONER, TensionIdler
from plotter_cad.part import Assembly, AssemblyLimit, AssemblyTerm
from plotter_cad.parts.tension_idler import dovetail_play

#: Per-part limits of the tensioner's mount and slider (tension_idler.slider_fem / mount_fem)
_ALONG_BELT_MM = 0.3
_OTHER_MM = 0.1

_SOURCE = (
    "limits: sum of the members' limits (0.3 mm along the belt, 0.1 mm otherwise); play: "
    "tension_idler.dovetail_play (worst case, rigid tilt of the slider in the clearance)"
)


def tensioner_assembly(
    name: str,
    description: str,
    mount: str,
    slider: str,
    mount_prefix: str,
    t: TensionIdler | None = None,
) -> Assembly:
    """Mount + slider of one belt idler, judged on the idler axle's total displacement.

    ``t`` is a dovetail tensioner: its slider tilts in the clearance, which is a rigid term. With
    ``None`` (the floating X idler, tied by a screw on the belt line) there is no play to add.
    """
    play = dovetail_play(t) if t is not None else None

    def limit(direction: str, one_part_mm: float, rigid_mm: float, what: str) -> AssemblyLimit:
        terms = [
            AssemblyTerm(f"slider flex, {what}", slider, f"idler_axle_{direction}"),
            AssemblyTerm(f"mount flex, {what}", mount, f"{mount_prefix}_{direction}"),
        ]
        if play is not None:
            terms.append(
                AssemblyTerm(
                    f"dovetail play: slider tilts {play.tilt_rad:.3f} rad in its clearance",
                    rigid_mm=rigid_mm,
                )
            )
        return AssemblyLimit(f"idler_axle_{direction}", 2 * one_part_mm, tuple(terms))

    return Assembly(
        name,
        description,
        (mount, slider),
        (
            limit(
                "along_belt",
                _ALONG_BELT_MM,
                play.axle_along_belt_mm if play else 0,
                "along the belt",
            ),
            limit("sideways", _OTHER_MM, 0.0, "along the axle"),
            limit("vertical", _OTHER_MM, play.axle_vertical_mm if play else 0, "vertical"),
        ),
        _SOURCE,
    )


ASSEMBLY_CHECKS: dict[str, Assembly] = {
    a.name: a
    for a in (
        tensioner_assembly(
            "x_idler_tensioner",
            "X idler: the bracket's tower with the floating slider (no dovetail: no play term)",
            "gantry_end_bracket_left",
            "x_idler_slider",
            "tower_seat",
        ),
        tensioner_assembly(
            "y_idler_tensioner_left",
            "Y idler, left: mount with its slider",
            "y_idler_mount_left",
            "y_idler_slider_left",
            "idler_seat",
            Y_TENSIONER,
        ),
        tensioner_assembly(
            "y_idler_tensioner_right",
            "Y idler, right: mount with its slider (the left slider's mirror image)",
            "y_idler_mount_right",
            "y_idler_slider_right",
            "idler_seat",
            Y_TENSIONER,
        ),
    )
}
