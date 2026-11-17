"""Generic tensioning idler with its hardware: idler, axle bolt and nut, tension screw and nut
(fit check, prototype). Assembly frame of ``parts.tension_idler``. Not printable."""

from typing import TYPE_CHECKING

from plotter_cad.geometry import get_handle
from plotter_cad.hardware import gt2_idler, hex_nut, shcs
from plotter_cad.params import TENSION_IDLER as T
from plotter_cad.params import TOL
from plotter_cad.parts.tension_idler import SLIDER_X0, tension_idler_installed

if TYPE_CHECKING:
    from pythonscad import Solid


def tension_idler_fit_check() -> list[Solid]:
    """Rail + slider (assembled), idler, M5 axle (head on the -y arm), M3 tension screw."""
    part = tension_idler_installed()
    axle = get_handle(part, "axle")
    screw = get_handle(part, "screw")
    axle_nut = (
        hex_nut(T.axle_m)
        .rotate([0, 0, 90])
        .rotate([-90, 0, 0])
        .translate([SLIDER_X0 + T.axle_x, T.nut_seat_y, T.axle_z])
    )
    screw_nut = (
        hex_nut(T.screw_m).rotate([0, 90, 0]).translate([SLIDER_X0 + TOL.nut_wall, 0, T.screw_z])
    )
    idler = gt2_idler().rotate([90, 0, 0]).translate([SLIDER_X0 + T.axle_x, 0, T.axle_z])
    return [
        part.color("SteelBlue"),
        idler,
        shcs(T.axle_m, 25).align(axle),
        axle_nut,
        shcs(T.screw_m, T.screw_len).align(screw),
        screw_nut,
    ]
