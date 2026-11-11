"""X carriage with wheels, eccentric spacers, bolts and X belt clamps (fit check, T3.3).

Carriage-local frame (``params.Carriage``). Not printable.
"""

from pythonscad import cube

from plotter_cad.hardware import GT2, eccentric_spacer, hex_nut, metric, shcs, vslot_x, vwheel
from plotter_cad.params import BEAM, CARRIAGE, CLAMP, X_BELT
from plotter_cad.parts.x_carriage import CLAMP_X, WHEEL_X, x_carriage_installed
from plotter_cad.parts.y_belt_clamp import y_belt_clamp


def carriage_assembly(ecc_rot: float = 0):
    """Carriage, wheels, spacers, axle bolts, X belt clamps and the endstop trigger."""
    c = CARRIAGE
    washer_t = metric(5).washer_t
    items = [x_carriage_installed().color("MediumSeaGreen")]
    for sx in (-1, 1):
        x = sx * WHEEL_X
        # top wheels on printed stand-offs
        items.append(vwheel().translate([x, 0, c.wheel_z[0]]))
        items.append(
            shcs(5, 35).rotate([90, 0, 0]).translate([x, c.plate_front_y - washer_t, c.wheel_z[0]])
        )
        # bottom wheels on eccentric spacers (the bolt sits ECCENTRIC.offset off the boss axis)
        items.append(vwheel().translate([x, 0, c.wheel_z[1]]))
        items.append(eccentric_spacer(ecc_rot).translate([x, c.plate_back_y, c.wheel_z[1]]))
        items.append(
            shcs(5, 35).rotate([90, 0, 0]).translate([x, c.plate_front_y - washer_t, c.wheel_z[1]])
        )
    # X belt clamp caps (belt runs along x) + belt ends
    for sx in (-1, 1):
        items.append(
            y_belt_clamp()
            .rotate([0, 0, 90])
            .translate([sx * CLAMP_X + CLAMP.length / 2, X_BELT.y, c.bridge_z - CLAMP.t])
            .color("Gold")
        )
        items.append(
            cube([CLAMP.length, GT2.width, GT2.thickness])
            .translate(
                [
                    sx * CLAMP_X - CLAMP.length / 2,
                    X_BELT.y - GT2.width / 2,
                    c.bridge_z + CLAMP.channel_d - GT2.thickness,
                ]
            )
            .color("#111")
        )
    # X endstop trigger: the screw head outside the rear block's left end touches the
    # switch; a lock nut sits between head and block (shown at the end of its
    # adjustment, as params.XEndstopMount.head_x_min assumes), a captive nut inside
    lock_nut_x = -c.rear_w / 2 - metric(3).nut_h
    items.append(hex_nut(3).rotate([0, 90, 0]).translate([lock_nut_x, c.trig_y, c.trig_z]))
    items.append(shcs(3, 16).rotate([0, -90, 0]).translate([lock_nut_x, c.trig_y, c.trig_z]))
    return items


def carriage_fit_check():
    """The carriage assembly on a 240 mm piece of the beam."""
    beam = vslot_x(240, BEAM.size).translate([-120, -BEAM.depth / 2, BEAM.bottom_z])
    return [*carriage_assembly(), beam]
