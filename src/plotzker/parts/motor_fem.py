"""FEM loads of a belt-driven NEMA17 on a mount, shared by the X and Y motor mounts and by the
gantry bracket that carries the X motor mount (docs/fem.md)."""

from cadder.geometry import lever_couple
from cadder.part import Force, Load, Moment
from cadder.regions import Region
from cadder.types import Vec3

from plotzker.loads import MOTOR_LOADS, BeltLoads


def motor_loads(
    region: Region,
    belt: BeltLoads,
    jam: bool,
    pulley_point: Vec3,
    region_point: Vec3,
    pull: Vec3,
    shaft: Vec3,
    couples: bool = True,
) -> list[Load]:
    """Loads the motor puts on the faces of ``region`` (its seat on the mount, or the part of
    the bracket under the mount): the radial pull of two belt runs (a unit vector ``pull``
    toward the idler) moved from the pulley to ``region_point``, the motor's weight, and at a
    jam the stall torque about the unit vector ``shaft``. With ``couples=False`` only the forces
    are returned (for a region on a clamped joint, which carries the couples through its bolts:
    a linear distribution would pull on a contact that can only push)."""
    run = belt.peak_n if jam else belt.preload_n
    force = (2 * run * pull[0], 2 * run * pull[1], 2 * run * pull[2])
    arm = (
        pulley_point[0] - region_point[0],
        pulley_point[1] - region_point[1],
        pulley_point[2] - region_point[2],
    )
    loads: list[Load] = [Force(region, force)]
    if couples:
        loads.append(Moment(region, lever_couple(arm, force)))
    loads.append(Force(region, (0.0, 0.0, -MOTOR_LOADS.weight)))
    if jam and couples:
        torque = MOTOR_LOADS.stall_torque
        loads.append(Moment(region, (torque * shaft[0], torque * shaft[1], torque * shaft[2])))
    return loads
