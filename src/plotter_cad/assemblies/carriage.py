"""X carriage with wheels, eccentric spacers, bolts and X belt clamps (fit check, T3.3).

Carriage-local frame (``params.Carriage``). Not printable.
"""

from typing import TYPE_CHECKING

from pythonscad import cube

from plotter_cad.geometry import Matrix, get_handle, get_handles, handle, shift_handle
from plotter_cad.hardware import GT2, eccentric_spacer, hex_nut, metric, shcs, vslot_x, vwheel
from plotter_cad.params import BEAM, CARRIAGE, CLAMP
from plotter_cad.parts.belt_clamp import belt_clamp
from plotter_cad.parts.x_carriage import x_carriage_installed

if TYPE_CHECKING:
    from pythonscad import Solid


AXLE_BOLT_L = 42  #: M5 axle bolt length (washer and head sit in the counterbore)


def _on_beam_plane(axle: Matrix) -> Matrix:
    """A wheel's position: on the axle's line, at the beam's center plane (no rotation)."""
    return handle([axle[0][3], 0, axle[2][3]])


def carriage_assembly(ecc_rot: float = 0) -> list[Solid]:
    """Carriage, wheels, spacers, axle bolts, X belt clamps and the endstop trigger."""
    c = CARRIAGE
    wash = metric(5).washer_t
    carriage = x_carriage_installed()
    items = [carriage.color("MediumSeaGreen")]
    top = get_handles(carriage, "wheel_axles_top")
    bottom = get_handles(carriage, "wheel_axles_bottom")
    for axle_top, axle_bottom in zip(top, bottom, strict=True):
        wheel_top = _on_beam_plane(axle_top)
        wheel_bottom = _on_beam_plane(axle_bottom)
        items.append(vwheel().align(wheel_top))
        items.append(
            shcs(5, AXLE_BOLT_L).align(shift_handle(axle_top, [0, -wash + c.head_recess, 0]))
        )
        # bottom wheels on eccentric spacers (the bolt sits ECCENTRIC.offset off the boss axis)
        items.append(vwheel().align(wheel_bottom))
        items.append(
            eccentric_spacer(ecc_rot).align(
                handle([wheel_bottom[0][3], c.plate_back_y, wheel_bottom[2][3]])
            )
        )
        items.append(
            shcs(5, AXLE_BOLT_L).align(shift_handle(axle_bottom, [0, -wash + c.head_recess, 0]))
        )
    for mount in get_handles(carriage, "belt_clamps"):
        clamp = belt_clamp()
        items.append(clamp.align(mount, get_handle(clamp, "mount")).color("Gold"))
        items.append(
            cube([GT2.width, CLAMP.length, GT2.thickness])
            .translate([-GT2.width / 2, 0, -GT2.thickness])
            .align(mount)
            .color("#111")
        )
    # X endstop trigger: the screw head outside the rear block's left end touches the
    # switch; a lock nut sits between head and block (shown at the end of its
    # adjustment, as params.XEndstopMount.head_x_min assumes), a captive nut inside
    trigger = get_handle(carriage, "trigger_screw")
    lock_nut_x = trigger[0][3] - metric(3).nut_h
    items.append(hex_nut(3).align(handle([lock_nut_x, trigger[1][3], trigger[2][3]], [0, 90, 0])))
    items.append(shcs(3, 16).align(shift_handle(trigger, [-metric(3).nut_h, 0, 0])))
    return items


def carriage_fit_check() -> list[Solid]:
    """The carriage assembly on a 240 mm piece of the beam."""
    beam = vslot_x(240, BEAM.size).translate([-120, -BEAM.depth / 2, BEAM.bottom_z])
    return [*carriage_assembly(), beam]
