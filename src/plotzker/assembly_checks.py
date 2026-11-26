"""Assemblies whose parts are checked together on the sum of their deflections and play.

A part's own FEM check holds its neighbours rigid, so deflections that are small in each part
but add up, and play between parts, go unseen. The belt tensioners are the case that taught
this (STATUS.md T3.21): a dovetail slider tilted in its clearance while the mount bent. The
floating idlers have no play, but their mount and slider deflections still add up.

Limits are the sum of the members' own limits (nothing new is decided): both parts may use
their budget at most, and play is an extra that must fit in it.
"""

from cadder.assembly import AssemblyCheck, AssemblyLimit, AssemblyTerm

#: Per-part limits of the tensioner's mount and slider (floating_idler.slider_fem / mount_fem)
_ALONG_BELT_MM = 0.3
_OTHER_MM = 0.1

_SOURCE = "limits: sum of the members' limits (0.3 mm along the belt, 0.1 mm otherwise)"


def tensioner_assembly(name: str, description: str, mount: str, slider: str, mount_prefix: str) -> AssemblyCheck:
    """Mount + slider of one floating belt idler, judged on the idler axle's total displacement.

    The slider is tied by a screw on the belt line, so there is no play to add: the terms are the
    two parts' deflections.
    """

    def limit(direction: str, one_part_mm: float, what: str) -> AssemblyLimit:
        terms = (
            AssemblyTerm(f"slider flex, {what}", slider, f"idler_axle_{direction}"),
            AssemblyTerm(f"mount flex, {what}", mount, f"{mount_prefix}_{direction}"),
        )
        return AssemblyLimit(f"idler_axle_{direction}", 2 * one_part_mm, terms)

    return AssemblyCheck(
        name,
        description,
        (mount, slider),
        (
            limit("along_belt", _ALONG_BELT_MM, "along the belt"),
            limit("sideways", _OTHER_MM, "along the axle"),
            limit("vertical", _OTHER_MM, "vertical"),
        ),
        _SOURCE,
    )


ASSEMBLY_CHECKS: dict[str, AssemblyCheck] = {
    a.name: a
    for a in (
        tensioner_assembly(
            "x_idler_tensioner",
            "X idler: the bracket's tower with the floating slider",
            "gantry_end_bracket_left",
            "idler_slider",
            "tower_seat",
        ),
        tensioner_assembly(
            "y_idler_tensioner_left",
            "Y idler, left: the mount's tower with the floating slider",
            "y_idler_mount_left",
            "idler_slider",
            "tower_seat",
        ),
        tensioner_assembly(
            "y_idler_tensioner_right",
            "Y idler, right: the mount's tower with the floating slider",
            "y_idler_mount_right",
            "idler_slider",
            "tower_seat",
        ),
    )
}
