"""Shared design parameters of the DIY pen plotter.

Every dimension a part needs lives here (or, for vendor parts, in
:mod:`plotter_cad.hardware`); part modules contain no magic numbers. Parameters are
grouped into frozen dataclasses with one module-level instance each (``TOL``,
``BEAM``, ``CARRIAGE``...). Values computed from others are properties, never typed in.

Machine frame (used by assemblies):
    origin = top surface of the baseboard, front-left corner;
    +X across the machine (along the gantry beam, A3 short side);
    +Y front to back (along the Y shafts, A3 long side); +Z up.

Comment markers: ``ASSUMED`` = catalog value awaiting a measurement;
``DESIGN (Tn.m)`` = design choice that the named task may refine.
Units: mm, degrees.
"""

import math
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from plotter_cad.geometry import cos_deg
from plotter_cad.hardware import (
    ECCENTRIC,
    ENDSTOP,
    GT2,
    IDLER,
    NEMA17,
    PULLEY,
    SCS10UU,
    SK10,
    VSLOT,
    VWHEEL,
    Y_SHAFT,
    metric,
)

# -----------------------------------------------------------------------------
# Print tolerances (tune after a test print; defaults from CLAUDE.md)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Tolerances:
    bolt: float = 0.4  #: clearance-hole oversize: M3 → 3.4, M5 → 5.4
    slide: float = 0.2  #: sliding fit (diametral)
    press: float = 0.0  #: press fit (0 to -0.1)
    nut: float = 0.3  #: nut trap: across-flats oversize
    gap: float = 0.3  #: general clearance between mating printed parts
    min_wall: float = 1.6  #: 4 perimeters at 0.4 mm nozzle
    layer_h: float = 0.2
    nozzle_d: float = 0.4
    insert_pocket_depth: float = 7  #: M3 heat-set insert pocket depth

    def bolt_hole_d(self, m: float) -> float:
        """Clearance hole for an M``m`` bolt."""
        return m + self.bolt

    def nut_trap_af(self, m: float) -> float:
        """Across flats of a nut trap."""
        return metric(m).nut_af + self.nut

    def nut_trap_ac(self, m: float) -> float:
        """Across corners of a nut trap (for a 6-sided cylinder)."""
        return self.nut_trap_af(m) / cos_deg(30)

    def nut_trap_h(self, m: float) -> float:
        """Height (thickness) of a nut trap slot."""
        return metric(m).nut_h + self.nut

    def cbore_d(self, m: float) -> float:
        """Counterbore for a socket head cap screw head."""
        return metric(m).head_d + 2 * self.bolt

    def slide_d(self, d: float) -> float:
        return d + self.slide

    def press_d(self, d: float) -> float:
        return d + self.press


TOL = Tolerances()

# -----------------------------------------------------------------------------
# Requirements (README §1, §5)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Requirements:
    media_a3: tuple[float, float] = (297, 420)  #: A3 short side across X (D10)
    media_max_t: float = 15  #: R2, D15
    x_travel: float = 410  #: target travel (README §4.2)
    y_travel: float = 540  #: target travel (D11)
    #: Min gap above the thickest media for everything except the pen. DESIGN
    gantry_media_clear: float = 3
    # Pen head (README §4.3, D14, D18)
    pen_d_range: tuple[float, float] = (7, 16)
    pen_lift_min: float = 5
    pen_float_min: float = 3
    pen_height_adjust: float = 20
    pen_axis_max_offset: float = 25  #: pen axis to the carriage front face
    pen_pressure_g: tuple[float, float] = (20, 80)


REQ = Requirements()

# -----------------------------------------------------------------------------
# Baseboard and bed (README §4.8, D16, D17)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    board_size: tuple[float, float, float] = (650, 850, 18)  #: X × Y × thickness (plywood)
    bed_panel_t: float = 9  #: DESIGN (T3.7): 6–9 mm plywood/MDF
    bed_steel_t: float = 0.8  #: DESIGN (T3.7): 0.5–1 mm galvanized steel
    bed_adjust_gap: float = 5  #: DESIGN (T3.7): baseboard → panel underside, mid-adjustment
    bed_size: tuple[float, float] = (400, 480)  #: DESIGN (T3.7): steel/panel X × Y

    @property
    def bed_top_z(self) -> float:
        return self.bed_adjust_gap + self.bed_panel_t + self.bed_steel_t

    @property
    def media_top_z(self) -> float:
        return self.bed_top_z + REQ.media_max_t


FRAME = Frame()

# -----------------------------------------------------------------------------
# Drive (D7)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Drive:
    motor_full_steps: int = 200  #: 1.8°
    microsteps: int = 16

    @property
    def steps_per_mm(self) -> float:
        return self.motor_full_steps * self.microsteps / (PULLEY.teeth * GT2.pitch)


DRIVE = Drive()

# -----------------------------------------------------------------------------
# Belt clamps (shared by the Y belt under the gantry brackets and the X belt under
# the carriage). The belt back bears on the channel ceiling; the cap's ridges sit
# in the tooth gaps.
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class BeltClamp:
    squeeze: float = 0.3  #: belt compression in the clamp
    length: float = 20  #: along the belt (10 teeth)
    t: float = 4  #: cap thickness
    w: float = 16  #: cap width (across the belt)
    screw_dx: float = 5.5  #: M3 offset from the belt center
    ridge_w: float = 0.9  #: GT2 tooth gap ≈ 1.0

    @property
    def ridge_h(self) -> float:
        """Tooth ridges (0.35): with the squeeze they engage ~0.65 of the 0.75 tooth."""
        return GT2.tooth_h - self.squeeze - 0.1

    @property
    def channel_d(self) -> float:
        """Belt channel depth in the part above the belt."""
        return GT2.thickness - self.squeeze

    @property
    def channel_w(self) -> float:
        return GT2.width + 0.4


CLAMP = BeltClamp()

# -----------------------------------------------------------------------------
# Tool-plate interface v1 (D8, README §4.4)
# -----------------------------------------------------------------------------
# The carriage front face carries a hook (cleat) along its top edge and two M3
# clamp points along its bottom edge. A tool head hangs on the hook and is clamped
# by 2 × M3 into heat-set inserts in the carriage.
#
#   carriage face (front view)          side section (tool head hanging)
#   ┌──────── w ───────────┐                carriage │▒▒╲ hook (45° undercut)
#   │▔▔▔▔▔▔ hook ▔▔▔▔▔▔▔▔▔▔│ ← hook_h                │▒▒ ╲▁▁ tool plate
#   │       [conn]         │                         │   │
#   │   ⊕              ⊕   │ ← 2 × M3 at screw_z     │ ⊕ │
#   └──────────────────────┘                         │   │
#
# Interface origin: center of the bottom edge of the interface area, on the
# carriage front face.


@dataclass(frozen=True)
class ToolPlate:
    w: float = 50  #: DESIGN (T3.3): interface width (X)
    h: float = 45  #: DESIGN (T3.3): height, bottom edge to top of hook
    hook_h: float = 6  #: DESIGN: vertical height of the hook lip
    hook_d: float = 3  #: DESIGN: undercut depth (how far the tool plate tucks in)
    hook_angle: float = 45  #: DESIGN: undercut angle (printable without support)
    screw_m: float = 3
    screw_pitch: float = 36  #: DESIGN: M3 center to center (X)
    screw_z: float = 7  #: DESIGN: M3 centers above the interface bottom edge
    plate_t: float = 5  #: DESIGN: minimum tool-plate thickness at the interface
    #: DESIGN: tool-head connector window in the carriage's top tab (3-pin servo now,
    #: room for 6-pin)
    conn_size: tuple[float, float] = (16, 8)
    fit_gap: float = TOL.gap  #: tool plate ↔ carriage interface clearance

    @property
    def bottom_z(self) -> float:
        """Interface bottom edge (abs z) = carriage bottom."""
        return CARRIAGE.bottom_z

    @property
    def top_z(self) -> float:
        return self.bottom_z + self.h


TOOL_PLATE = ToolPlate()

# -----------------------------------------------------------------------------
# Y axis (D6, D11, D13) and the height stack-up below the beam
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class YAxis:
    scs_pitch: float = 90  #: DESIGN (T3.2): SCS center to center per side, 80–100
    end_margin: float = 2  #: DESIGN: SCS block ↔ SK10 gap at the travel ends
    belt_x: float = -30  #: Y belt center, bracket-local x (outboard of the shaft)

    @property
    def shaft_spacing(self) -> float:
        """Shaft center to center (520): the beam ends sit over the shafts."""
        return BEAM.length + 2 * BEAM.end_offset

    @property
    def shaft_x(self) -> tuple[float, float]:
        """Shaft positions in the machine frame (centered on the baseboard)."""
        board_x = FRAME.board_size[0]
        return ((board_x - self.shaft_spacing) / 2, (board_x + self.shaft_spacing) / 2)

    @property
    def shaft_y0(self) -> float:
        """Shaft front end."""
        return (FRAME.board_size[1] - Y_SHAFT.length) / 2

    @property
    def sk10_y(self) -> tuple[float, float]:
        """SK10 mid-thickness, front and back."""
        return (self.shaft_y0 + SK10.length / 2, self.shaft_y0 + Y_SHAFT.length - SK10.length / 2)

    @property
    def shaft_z(self) -> float:
        return SK10.shaft_h

    @property
    def scs_base_z(self) -> float:
        return self.shaft_z - SCS10UU.shaft_h

    @property
    def scs_top_z(self) -> float:
        return self.scs_base_z + SCS10UU.height

    @property
    def gantry_len_y(self) -> float:
        """Gantry end length along Y."""
        return self.scs_pitch + SCS10UU.length

    @property
    def travel_avail(self) -> float:
        return Y_SHAFT.length - 2 * SK10.length - self.gantry_len_y - 2 * self.end_margin

    # Y belt line (fixes the Y motor and idler heights for T3.5)
    @property
    def belt_back_z(self) -> float:
        """Back of the belt's top run (abs z)."""
        return self.scs_top_z + CLAMP.channel_d

    @property
    def belt_pitch_z(self) -> float:
        return self.belt_back_z - GT2.pitch_line_from_back

    @property
    def pulley_axis_z(self) -> float:
        """Y motor shaft / idler axle height (abs z)."""
        return self.belt_pitch_z - PULLEY.pd / 2


Y_AXIS = YAxis()

# -----------------------------------------------------------------------------
# X axis: 4020 beam, upright (D12)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Beam:
    length: float = 520
    size: tuple[int, int] = (1, 2)  #: vslot_x size: 20 deep (Y) × 40 tall (Z)
    #: Beam end relative to its shaft axis (+ = inboard). 0 = the beam end sits over
    #: the shaft, so the gantry weight bears straight down on the SCS blocks. DESIGN (T3.2)
    end_offset: float = 0

    @property
    def depth(self) -> float:
        return self.size[0] * VSLOT.unit

    @property
    def height(self) -> float:
        return self.size[1] * VSLOT.unit

    @property
    def bottom_z_min(self) -> float:
        """Lowest beam bottom that lets the carriage clear the thickest media."""
        return FRAME.media_top_z + REQ.gantry_media_clear + CARRIAGE.below_beam

    @property
    def bottom_z(self) -> float:
        """DESIGN (T3.2): set by the gantry end brackets."""
        return math.ceil(self.bottom_z_min)

    @property
    def top_z(self) -> float:
        return self.bottom_z + self.height

    @property
    def rise_above_scs(self) -> float:
        """How far the brackets lift the beam bottom above the SCS top face."""
        return self.bottom_z - Y_AXIS.scs_top_z


BEAM = Beam()

# -----------------------------------------------------------------------------
# X carriage (T3.3) — carriage-local frame: x from the carriage center along the
# beam, y from the beam's center plane (+y = behind the beam), z = machine z.
# -----------------------------------------------------------------------------


class Preload(Enum):
    """Bottom-wheel preload (D21)."""

    ECCENTRIC = "eccentric"  #: 2 eccentric spacers on the bottom pair
    SLOT = "slot"  #: fallback: slotted axle holes + M3 push screw, clamped by the axle nut


@dataclass(frozen=True)
class Carriage:
    #: DESIGN (T3.3): wheel center to center along X; wide enough that the bottom
    #: wheels' bolt heads sit outside the 50 mm tool plate
    wheel_pitch_x: float = 64
    plate_t: float = 8  #: DESIGN (T3.3): front plate thickness
    margin_below_wheel: float = 3  #: DESIGN (T3.3): material below the lowest wheel edge
    preload: Preload = Preload.ECCENTRIC
    preload_slot_travel: float = 2  #: DESIGN (T3.3): slot length for the fallback
    #: Printed stand-off under each top wheel: bears on the 625 inner ring only (land ≈ 8)
    top_boss_d: float = 7.5
    bridge_w: float = 34  #: bridge over the beam top, between the top wheels (x)
    bridge_clear: float = 2.5  #: bridge underside above the beam top
    bridge_h: float = 17.5
    rear_w: float = 52  #: rear clamp block width (x): two X belt clamps
    rear_h: float = 17.5  #: tall enough for the endstop trigger above the clamps
    tab_w: float = 24  #: top tab (connector + strain relief) width
    tab_h: float = 15  #: top tab height above the plate
    zip_slot: tuple[float, float] = (4, 2)  #: zip-tie slot (x × z)
    trig_z_above: float = 14  #: X endstop trigger screw: height above the bridge underside
    trig_y: float = 27.5  #: ... and its y

    @property
    def w(self) -> float:
        """Carriage envelope along X (wheels)."""
        return self.wheel_pitch_x + VWHEEL.od

    @property
    def plate_w(self) -> float:
        """Front plate width (82)."""
        return self.wheel_pitch_x + 18

    @property
    def below_beam(self) -> float:
        """How far the lowest part of the carriage sits below the beam's bottom face."""
        return VWHEEL.axis_to_face + VWHEEL.od / 2 + self.margin_below_wheel

    @property
    def wheel_z(self) -> tuple[float, float]:
        """Wheel axle heights (abs): top pair, bottom pair."""
        return (BEAM.top_z + VWHEEL.axis_to_face, BEAM.bottom_z - VWHEEL.axis_to_face)

    @property
    def bottom_z(self) -> float:
        return BEAM.bottom_z - self.below_beam

    @property
    def top_z(self) -> float:
        return self.wheel_z[0] + VWHEEL.od / 2 + self.margin_below_wheel

    @property
    def plate_back_y(self) -> float:
        """Plate back face (wheel face − stand-off)."""
        return -VWHEEL.width / 2 - ECCENTRIC.stack

    @property
    def plate_front_y(self) -> float:
        """Carriage front face (tool plate side)."""
        return self.plate_back_y - self.plate_t

    @property
    def bridge_z(self) -> float:
        """Bridge / rear block underside (abs z)."""
        return BEAM.top_z + self.bridge_clear

    @property
    def trig_z(self) -> float:
        """X endstop trigger screw axis (abs z)."""
        return self.bridge_z + self.trig_z_above

    @property
    def end_keepout(self) -> float:
        """Carriage stop distance from each beam end.

        In front of the beam the tool head can't pass over the SCS blocks / bracket
        (x ≤ SCS width / 2 from the shaft); tool head assumed tool-plate wide.
        """
        return SCS10UU.width / 2 - BEAM.end_offset - (self.w - TOOL_PLATE.w) / 2 + 2

    @property
    def travel_avail(self) -> float:
        """X travel available."""
        return BEAM.length - self.w - 2 * self.end_keepout


CARRIAGE = Carriage()

# -----------------------------------------------------------------------------
# Gantry end brackets (T3.2) — parts/gantry_end_bracket.py
# -----------------------------------------------------------------------------
# Bracket-local frame (left bracket; the right one is its mirror image): origin on
# the SCS top-face plane, over the shaft axis, midway between the two SCS blocks;
# +x inboard, +y back, +z up. Printed base-down: local z = 0 is the print bed.


@dataclass(frozen=True)
class GantryBracket:
    base_t: float = 10  #: base plate on the SCS blocks (M5×20 → 10 mm thread engagement)
    x_out: float = -38  #: outboard edge (covers the Y belt clamp)
    face_t: float = 8  #: plate the beam end bolts to (YZ plane)
    face_y: tuple[float, float] = (-28, 11)  #: its y extent (≤ +11: X belt runs behind)
    face_above: float = 3  #: face plate height above the beam top
    recess: float = 1.5  #: beam-end locating pocket depth in the face plate
    rib_t: float = 6
    #: Rib start positions (y); y -10…+5 kept clear for hex-key access to the beam bolts
    rib_y0: tuple[float, ...] = (-28, -16, 5)
    beam_bolt_m: float = 5  #: 2 × M5 into the beam's tapped end bores
    # Y endstop trigger: M3 screw (+ lock nut) pointing forward from a boss on the
    # front-outboard corner; adjusts each side's home position (gantry squaring).
    trig_x: float = -30  #: screw axis, bracket-local x
    trig_boss: tuple[float, float, float] = (12, 9, 10)  #: boss x × y × z, on the base

    @property
    def x_in(self) -> float:
        """Inboard edge over the blocks."""
        return SCS10UU.width / 2

    @property
    def len_y(self) -> float:
        """= SCS block extent; keeps the Y travel."""
        return Y_AXIS.scs_pitch + SCS10UU.length

    @property
    def notch_y(self) -> float:
        """Between the blocks the base stops at the beam end so the carriage can pass."""
        return Y_AXIS.scs_pitch / 2 - SCS10UU.length / 2 - 0.5

    @property
    def trig_z(self) -> float:
        """Trigger screw axis height (local)."""
        return self.base_t + 5


BRACKET = GantryBracket()

# -----------------------------------------------------------------------------
# X belt: vertical loop behind the beam (motor shaft along Y, body behind the beam;
# T3.4). Top run cut and clamped under the carriage's rear block.
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class XBelt:
    #: Belt center behind the beam's rear face. Set so the X motor plate fits between
    #: the gantry bracket's rear bolt rows and long motor shafts clear the beam (T3.4)
    behind_beam_face: float = 13

    @property
    def y(self) -> float:
        """Belt center behind the beam's center plane (23)."""
        return BEAM.depth / 2 + self.behind_beam_face

    @property
    def back_z(self) -> float:
        """Back of the top run (abs z)."""
        return CARRIAGE.bridge_z + CLAMP.channel_d

    @property
    def pulley_axis_z(self) -> float:
        """X motor shaft / idler axle (abs z)."""
        return self.back_z - GT2.pitch_line_from_back - PULLEY.pd / 2


X_BELT = XBelt()

# -----------------------------------------------------------------------------
# X drive (T3.4): motor mount (right end), idler mount + tensioner and X endstop
# mount (left end). Designed in the LEFT bracket-local frame (x = 0 at the shaft =
# beam end, +x inboard, y from the beam center plane, +y behind the beam); the
# motor mount is used mirrored on the right. Both mounts sit on the gantry
# bracket's base over the rear SCS block and are clamped by its rear M5 rows
# (those 4 bolts become M5×25).
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class XDrive:
    foot_t: float = 5  #: foot clamped under the rear SCS bolts
    # Motor
    motor_x: float = 1  #: DESIGN: motor shaft x (near the beam end)
    motor_plate_t: float = 5  #: front face = plate_y0
    motor_rib_t: float = 6  #: rib under the motor
    # Idler (toothed 20T on an M5 axle, cantilevered from the plate) + tensioner
    idler_x: float = -24  #: DESIGN: idler axle, mid-slot (outboard of the beam end)
    idler_slot: float = 8  #: axle slot length along x (tension travel; belt ±8 mm)
    idler_plate_t: float = 11.5  #: thick enough to stand alone (fits between the bolt rows)
    idler_plate_x: tuple[float, float] = (-42, -8)
    idler_top_z: float = 108  #: plate top, abs z (the endstop mount sits here)
    endstop_insert_x: tuple[float, float] = (-22, -12)  #: endstop-mount inserts on the plate top

    @property
    def bolt_rows(self) -> tuple[float, float]:
        """Rear SCS bolt rows (y)."""
        p, c = Y_AXIS.scs_pitch, SCS10UU.hole_pitch_y
        return (p / 2 - c / 2, p / 2 + c / 2)

    @property
    def plate_y0(self) -> float:
        """Plates start behind the first bolt row."""
        return self.bolt_rows[0] + metric(5).head_d / 2 + 0.75

    @property
    def foot_y(self) -> tuple[float, float]:
        p, length = Y_AXIS.scs_pitch, SCS10UU.length
        return (p / 2 - length / 2, p / 2 + length / 2)

    @property
    def motor_face_y(self) -> float:
        """Motor mounting face."""
        return self.plate_y0 + self.motor_plate_t

    @property
    def pulley_hub_y(self) -> float:
        """Pulley's motor-side end."""
        return X_BELT.y + PULLEY.belt_z

    @property
    def idler_spacer_len(self) -> float:
        """Printed spacer, plate → idler."""
        return self.plate_y0 - (X_BELT.y + IDLER.width / 2)


X_DRIVE = XDrive()


@dataclass(frozen=True)
class XEndstopMount:
    """X endstop mount on the idler plate top. Board in the YZ plane, switch facing +x;
    the carriage's trigger screw head presses the lever toward -x. The lever points
    -y, its tip just in front of the trigger."""

    pre_trip: float = 2  #: trip this far before the carriage reaches its end
    plate_t: float = 6
    pad_slot: float = 4  #: ±x adjustment of the mount on the idler plate

    @property
    def lever_h(self) -> float:
        """Lever plane above the board. ASSUMED"""
        return ENDSTOP.pcb[2] + ENDSTOP.switch[2] + 0.5

    @property
    def head_x_min(self) -> float:
        """Trigger screw head at the carriage's end of travel (bracket-local x)."""
        return (
            CARRIAGE.end_keepout
            + CARRIAGE.w / 2
            - CARRIAGE.rear_w / 2
            - metric(3).nut_h
            - metric(3).head_h
        )

    @property
    def plate_front_x(self) -> float:
        return self.head_x_min + self.pre_trip - self.lever_h

    @property
    def lever_tip_y(self) -> float:
        """The trigger presses 2 mm from the lever tip."""
        return CARRIAGE.trig_y - 2

    @property
    def board_y(self) -> tuple[float, float]:
        """Board extent in y: switch end, far end (holes)."""
        far = self.lever_tip_y + ENDSTOP.len_lever
        return (far - ENDSTOP.pcb[0], far)


X_ENDSTOP = XEndstopMount()

# -----------------------------------------------------------------------------
# Design checks — the build fails if the parameters break a requirement
# -----------------------------------------------------------------------------


class DesignError(ValueError):
    """Raised when the parameters violate a design requirement."""


def design_checks() -> Iterator[tuple[bool, str]]:
    """Yield ``(passed, description)`` for every design rule."""
    m5 = metric(5)
    yield (
        Y_AXIS.travel_avail >= REQ.y_travel,
        (f"Y travel too short: {Y_AXIS.travel_avail:g} < {REQ.y_travel:g}"),
    )
    yield (
        CARRIAGE.travel_avail >= REQ.x_travel,
        (f"X travel too short: {CARRIAGE.travel_avail:g} < {REQ.x_travel:g}"),
    )
    yield REQ.x_travel >= REQ.media_a3[0] + 20, "X travel does not cover A3 + margins"
    yield REQ.y_travel >= REQ.media_a3[1] + 20, "Y travel does not cover A3 + margins"
    yield (
        FRAME.bed_size[0] <= Y_AXIS.shaft_spacing - SCS10UU.width - 2 * 5,
        "Bed panel collides with the SCS blocks",
    )
    yield BEAM.bottom_z >= BEAM.bottom_z_min, "Carriage would hit 15 mm media"
    yield DRIVE.steps_per_mm == 80, "Steps/mm changed — update README §5"
    yield -Y_AXIS.belt_x - GT2.width / 2 >= SK10.width / 2 + 3, "Y belt too close to the SK10"
    yield -Y_AXIS.belt_x - CLAMP.w / 2 >= SCS10UU.width / 2 + 1, "Y belt clamp hits the SCS block"
    yield -Y_AXIS.belt_x + CLAMP.w / 2 <= -BRACKET.x_out, "Y belt clamp outside the bracket"
    yield PULLEY.length + 1 <= NEMA17.shaft_len_min, "Pulley longer than the shortest motor shaft"
    yield (
        Y_AXIS.shaft_x[0] + Y_AXIS.belt_x - CLAMP.w / 2 > 0,
        "Y belt clamp overhangs the baseboard",
    )
    yield CARRIAGE.plate_back_y < -BEAM.depth / 2 - 2, "Carriage plate too close to the beam"
    yield (
        TOOL_PLATE.w / 2 + 1 <= CARRIAGE.wheel_pitch_x / 2 - m5.washer_od / 2,
        "Bottom wheel bolt heads overlap the tool plate",
    )
    yield (
        CARRIAGE.bridge_w / 2 + 2 <= CARRIAGE.wheel_pitch_x / 2 - VWHEEL.od / 2,
        "Bridge hits the top wheels",
    )
    yield X_BELT.y - CLAMP.w / 2 >= BEAM.depth / 2 + 1, "X belt clamp too close to the beam"
    yield (
        BEAM.end_offset + BRACKET.recess + 1 <= CARRIAGE.end_keepout,
        "Carriage wheels hit the gantry bracket",
    )
    yield (
        CARRIAGE.top_z - 2 - CARRIAGE.zip_slot[1] >= CARRIAGE.bridge_z + CARRIAGE.bridge_h + 0.5,
        "Zip-tie slots blocked by the bridge",
    )
    yield (
        X_DRIVE.motor_face_y - NEMA17.shaft_len >= BEAM.depth / 2 + 1,
        "X motor shaft would hit the beam",
    )
    yield (
        X_DRIVE.motor_face_y - NEMA17.shaft_len_min <= X_DRIVE.pulley_hub_y - PULLEY.hub_len,
        "Shortest motor shaft doesn't reach the pulley hub",
    )
    yield (
        X_DRIVE.plate_y0 + X_DRIVE.idler_plate_t <= X_DRIVE.bolt_rows[1] - m5.head_d / 2,
        "Idler plate covers the rear bolt row",
    )
    yield X_DRIVE.idler_spacer_len > 0, "Idler spacer length"
    yield (
        X_DRIVE.idler_x + X_DRIVE.idler_slot / 2 + IDLER.flange_d / 2 + 2
        <= X_ENDSTOP.plate_front_x - X_ENDSTOP.plate_t,
        "Idler flange hits the endstop plate",
    )


def check_design() -> None:
    """Raise :class:`DesignError` listing every failed design rule."""
    failures = [message for passed, message in design_checks() if not passed]
    if failures:
        raise DesignError("Design checks failed:\n  " + "\n  ".join(failures))


def report() -> str:
    """Key numbers of the current parameter set, one topic per line."""

    def fmt(*values: float) -> str:
        return ", ".join(f"{v:g}" for v in values)

    return "\n".join(
        [
            f"Stack-up: shaft {fmt(Y_AXIS.shaft_z)}, SCS top {fmt(Y_AXIS.scs_top_z)}, "
            f"bed top {fmt(FRAME.bed_top_z)}, media top {fmt(FRAME.media_top_z)}",
            f"Beam bottom {fmt(BEAM.bottom_z)} (min {fmt(BEAM.bottom_z_min)}), "
            f"top {fmt(BEAM.top_z)}; rise above SCS top {fmt(BEAM.rise_above_scs)}",
            f"Travel available X {fmt(CARRIAGE.travel_avail)} / Y {fmt(Y_AXIS.travel_avail)} "
            f"(targets {fmt(REQ.x_travel)} / {fmt(REQ.y_travel)})",
            f"Steps/mm {fmt(DRIVE.steps_per_mm)}; shaft spacing {fmt(Y_AXIS.shaft_spacing)} "
            f"(x {Y_AXIS.shaft_x[0]:g} / {Y_AXIS.shaft_x[1]:g}); "
            f"X end keep-out {fmt(CARRIAGE.end_keepout)}",
            f"Carriage: wheels z [{fmt(*CARRIAGE.wheel_z)}], bottom {fmt(CARRIAGE.bottom_z)}, "
            f"top {fmt(CARRIAGE.top_z)}; front face y {fmt(CARRIAGE.plate_front_y)}; "
            f"tool plate z {fmt(TOOL_PLATE.bottom_z)}–{fmt(TOOL_PLATE.top_z)}",
            f"X belt: center y {fmt(X_BELT.y)} behind beam center, back of top run z "
            f"{fmt(X_BELT.back_z)}, motor/idler axis z {fmt(X_BELT.pulley_axis_z)}",
            f"Y belt: back of top run z {fmt(Y_AXIS.belt_back_z)}, pulley/idler axis z "
            f"{fmt(Y_AXIS.pulley_axis_z)}, belt center {fmt(-Y_AXIS.belt_x)} "
            "outboard of each shaft",
        ]
    )
