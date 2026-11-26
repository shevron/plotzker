"""Load magnitudes shared by the FEM load cases. Every value is ASSUMED until measured.

Forces in N, torques in N·mm, accelerations in mm/s². One place to refine them: part
definitions read these, they don't repeat them (docs/fem.md).
"""

from dataclasses import dataclass

from cadder.hardware import PULLEY_SPEC

#: ASSUMED: peak acceleration of the axes (firmware cap; the pen allows no more)
ACCELERATION = 3000.0
#: ASSUMED: gantry mass (it includes the X motor) and the carriage with its tool head (kg)
GANTRY_KG = 1.5
CARRIAGE_HEAD_KG = 0.25
G = 9.80665  #: m/s², for weights


@dataclass(frozen=True)
class MotorLoads:
    """A NEMA17 on a mount."""

    stall_torque: float = 400.0  #: ASSUMED: holding torque (0.4 N·m), the most a jam can add
    weight: float = 0.28 * G  #: ASSUMED: motor mass 0.28 kg

    @property
    def pulley_radius(self) -> float:
        """Pitch radius of the 20T drive pulley (mm)."""
        return PULLEY_SPEC.pd / 2

    @property
    def jam_share(self) -> float:
        """Extra tension on the driven run of a belt at stall: torque / radius, half per run."""
        return self.stall_torque / self.pulley_radius / 2


MOTOR_LOADS = MotorLoads()


@dataclass(frozen=True)
class BeltLoads:
    """Tension of one belt run."""

    preload_n: float = 40.0  #: ASSUMED: set when tensioning, acts continuously
    #: ASSUMED: added at a jam (the driven run), from the motor's stall torque; real drive
    #: forces (gantry mass × acceleration, 2-3 N) are far below it
    dynamic_n: float = MOTOR_LOADS.jam_share

    @property
    def peak_n(self) -> float:
        """Tension of the most loaded run at a jam."""
        return self.preload_n + self.dynamic_n


X_BELT_LOADS = BeltLoads()
Y_BELT_LOADS = BeltLoads()

#: ASSUMED: a hand or a curled sheet knocks the pen sideways (N, short)
PEN_KNOCK = 20.0
#: ASSUMED: servo stall force at the horn tip: 1.9 kg·cm / 17 mm (N)
SERVO_STALL = 1.9 * G * 10 / 17
#: ASSUMED: pen pressure (80 g, the top of the design range) and the drag it causes (N)
PEN_PRESSURE = 0.080 * G
PEN_DRAG = 0.5 * PEN_PRESSURE
#: ASSUMED: pen tip height above the baseboard for the knock levers (mm, middle of the media)
PEN_TIP_Z = 22.5
