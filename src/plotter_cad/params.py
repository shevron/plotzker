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
# Print tolerances (tune after a test print; defaults from README.md §7.4)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Tolerances:
    """Print tolerances."""

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
        """Hole diameter for a sliding fit on a ``d`` mm part."""
        return d + self.slide

    def press_d(self, d: float) -> float:
        """Hole diameter for a press fit on a ``d`` mm part."""
        return d + self.press


TOL = Tolerances()

# -----------------------------------------------------------------------------
# Requirements (README §2, STATUS.md §5)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Requirements:
    """Requirements the design must meet (README §2)."""

    media_a3: tuple[float, float] = (297, 420)  #: A3 short side across X (D10)
    media_max_t: float = 15  #: R2, D15
    x_travel: float = 410  #: target travel (README §3.2)
    y_travel: float = 540  #: target travel (D11)
    #: Min gap above the thickest media for everything except the pen. DESIGN
    gantry_media_clear: float = 3
    # Pen head (README §3.3, D14, D18)
    pen_d_range: tuple[float, float] = (7, 16)
    pen_lift_min: float = 5
    pen_float_min: float = 3
    pen_height_adjust: float = 20
    pen_axis_max_offset: float = 25  #: pen axis to the carriage front face
    pen_pressure_g: tuple[float, float] = (20, 80)


REQ = Requirements()

# -----------------------------------------------------------------------------
# Baseboard and bed (README §3.8, D16, D17)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    """Frame boards, bed stack and media height."""

    board_size: tuple[float, float, float] = (650, 850, 18)  #: X × Y × thickness (plywood)
    bed_panel_t: float = 9  #: DESIGN (T3.7): 6–9 mm plywood/MDF
    bed_steel_t: float = 0.8  #: DESIGN (T3.7): 0.5–1 mm galvanized steel
    bed_adjust_gap: float = 5  #: DESIGN (T3.7): baseboard → panel underside, mid-adjustment
    bed_size: tuple[float, float] = (400, 480)  #: DESIGN (T3.7): steel/panel X × Y

    @property
    def bed_top_z(self) -> float:
        """Z of the top of the bed."""
        return self.bed_adjust_gap + self.bed_panel_t + self.bed_steel_t

    @property
    def media_top_z(self) -> float:
        """Z of the top of the thickest media."""
        return self.bed_top_z + REQ.media_max_t


FRAME = Frame()

# -----------------------------------------------------------------------------
# Drive (D7)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Drive:
    """Stepper drive and belt-pulley settings."""

    motor_full_steps: int = 200  #: 1.8°
    microsteps: int = 16

    @property
    def steps_per_mm(self) -> float:
        """Steps per mm of belt travel."""
        return self.motor_full_steps * self.microsteps / (PULLEY.teeth * GT2.pitch)


DRIVE = Drive()

# -----------------------------------------------------------------------------
# Belt clamps (shared by the Y belt under the gantry brackets and the X belt under
# the carriage). The belt back bears on the channel ceiling; the cap's ridges sit
# in the tooth gaps.
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class BeltClamp:
    """Belt clamp channel dimensions."""

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
        """Belt channel width."""
        return GT2.width + 0.4


CLAMP = BeltClamp()

# -----------------------------------------------------------------------------
# Tool-plate interface v1 (D8, README §3.4)
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
    """Tool-plate interface between carriage and tool heads."""

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
        """Z of the top edge."""
        return self.bottom_z + self.h


TOOL_PLATE = ToolPlate()

# -----------------------------------------------------------------------------
# Y axis (D6, D11, D13) and the height stack-up below the beam
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class YAxis:
    """Y axis: shafts, linear bearing blocks and travel."""

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
        """Z of the Y shaft axis."""
        return SK10.shaft_h

    @property
    def scs_base_z(self) -> float:
        """Z of the underside of the SCS blocks."""
        return self.shaft_z - SCS10UU.shaft_h

    @property
    def scs_top_z(self) -> float:
        """Z of the top of the SCS blocks."""
        return self.scs_base_z + SCS10UU.height

    @property
    def gantry_len_y(self) -> float:
        """Gantry end length along Y."""
        return self.scs_pitch + SCS10UU.length

    @property
    def travel_avail(self) -> float:
        """Available gantry travel along Y."""
        return Y_SHAFT.length - 2 * SK10.length - self.gantry_len_y - 2 * self.end_margin

    # Y belt line (fixes the Y motor and idler heights for T3.5)
    @property
    def belt_back_z(self) -> float:
        """Back of the belt's top run (abs z)."""
        return self.scs_top_z + CLAMP.channel_d

    @property
    def belt_pitch_z(self) -> float:
        """Z of the belt pitch line."""
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
    """Gantry beam (V-slot extrusion)."""

    length: float = 520
    size: tuple[int, int] = (1, 2)  #: vslot_x size: 20 deep (Y) × 40 tall (Z)
    #: Beam end relative to its shaft axis (+ = inboard). 0 = the beam end sits over
    #: the shaft, so the gantry weight bears straight down on the SCS blocks. DESIGN (T3.2)
    end_offset: float = 0

    @property
    def depth(self) -> float:
        """Extent along Y."""
        return self.size[0] * VSLOT.unit

    @property
    def height(self) -> float:
        """Extent along Z."""
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
        """Z of the top face."""
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
    """X carriage dimensions."""

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
        """Z of the underside."""
        return BEAM.bottom_z - self.below_beam

    @property
    def top_z(self) -> float:
        """Z of the top edge."""
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
    """Gantry end bracket dimensions."""

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
    trig_screw_len: float = 16  #: M3 trigger screw length (tip 7 mm in front of the boss)

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
    """X belt position."""

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
# X endstop (T3.4, redone in T3.5 for the measured board): the board lies flat
# (components up, front edge toward +x) on a pad on the idler plate top. The carriage's
# trigger screw head, moving -x, pushes the lever toward the board. Left bracket-local
# frame (see X drive below). Board axes: u = -y, v = +x, w = +z.
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class XEndstopMount:
    """X endstop mount: pad on the idler plate, carrying the board flat."""

    pad_t: float = 5  #: pad thickness: the M3 heads sit in counterbores under the board
    pad_slot: float = 4  #: ±x adjustment of the pad on the idler plate
    pad_margin: float = 1  #: board edge to pad edge (y)

    @property
    def head_x_min(self) -> float:
        """Trigger screw head face at the carriage's end of travel (bracket-local x)."""
        return (
            CARRIAGE.end_keepout
            + CARRIAGE.w / 2
            - CARRIAGE.rear_w / 2
            - metric(3).nut_h
            - metric(3).head_h
        )

    @property
    def board_front_x(self) -> float:
        """Front edge of the board."""
        return self.head_x_min - ENDSTOP.trigger_v

    @property
    def board_x(self) -> tuple[float, float]:
        """Board extent in x: rear edge, front edge."""
        return (self.board_front_x - ENDSTOP.pcb[0], self.board_front_x)

    @property
    def board_y(self) -> tuple[float, float]:
        """Board extent in y: the lever hinge is at +y, its tip toward -y."""
        yc = CARRIAGE.trig_y + ENDSTOP.contact_u
        return (yc - ENDSTOP.pcb[1] / 2, yc + ENDSTOP.pcb[1] / 2)

    @property
    def board_bottom_z(self) -> float:
        """Board underside (abs z): the lever's center line is at the trigger screw's height."""
        return CARRIAGE.trig_z - ENDSTOP.lever_z

    @property
    def pad_z(self) -> tuple[float, float]:
        """Pad extent in z (the board sits on its top)."""
        return (self.board_bottom_z - self.pad_t, self.board_bottom_z)

    @property
    def hole_x(self) -> float:
        """Board mounting hole line (x)."""
        return self.board_front_x + ENDSTOP.hole_v


X_ENDSTOP = XEndstopMount()

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
    """X drive: motor, idler and mounting feet."""

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
    endstop_insert_x: tuple[float, float] = (-22, -12)  #: endstop-mount inserts on the plate top

    @property
    def idler_top_z(self) -> float:
        """Plate top, abs z: the X endstop pad sits on it."""
        return X_ENDSTOP.pad_z[0]

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
        """Y range of the foot under the SCS block."""
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

# -----------------------------------------------------------------------------
# Y drive (T3.5): per side, a motor mount behind the rear SK10, an idler mount with
# a slot tensioner in front of the front SK10, and a Y endstop mount carried by the
# baseboard. Designed in the LEFT side frame: x from the shaft axis (belt at
# ``Y_AXIS.belt_x``, outboard = -x), y and z in the machine frame (z = 0 is the
# baseboard top). The right side is the mirror image.
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class YDrive:
    """Y motor mount and Y idler mount with tensioner."""

    foot_t: float = 6  #: printed foot on the baseboard (M4 wood screws, counterbored)
    foot_screw_m: float = 4  #: ASSUMED: wood/chipboard screws into the 18 mm plywood
    # Idler (toothed 20T on an M5 axle, cantilevered from a plate outboard of it)
    #: DESIGN (T3.5): axle (mid-slot) in front of the gantry's front face at its end of travel
    idler_from_front: float = 47
    idler_slot: float = 8  #: axle slot length along y (belt tension travel)
    idler_gap: float = 1.25  #: idler flange to plate: one M5 washer + clearance
    idler_plate_t: float = 9
    plate_margin: float = 6  #: material around the slot ends
    head_gap: float = 2.5  #: tension screw head to the gantry front, beyond the head height
    idler_foot_out: float = 16  #: foot beyond the plate, outboard
    # Motor (shaft points outboard; body inboard, behind the rear SK10)
    motor_gap: float = 3  #: rear SK10 face to the motor body
    hub_gap: float = 1  #: pulley hub to the motor plate
    motor_plate_t: float = 5
    motor_foot_out: float = 26  #: foot beyond the plate, outboard (screws under the open side)
    gusset_len: float = 16
    gusset_t: float = 3

    @property
    def gantry_front_y(self) -> float:
        """Front face of the gantry bracket at its end of travel (machine y)."""
        return Y_AXIS.shaft_y0 + SK10.length + Y_AXIS.end_margin

    @property
    def idler_y(self) -> float:
        """Idler axle, middle of the slot (machine y)."""
        return self.gantry_front_y - self.idler_from_front

    @property
    def idler_plate_x(self) -> tuple[float, float]:
        """Idler plate x extent (outboard of the idler)."""
        x1 = Y_AXIS.belt_x - IDLER.width / 2 - self.idler_gap
        return (x1 - self.idler_plate_t, x1)

    @property
    def idler_plate_y(self) -> tuple[float, float]:
        """Idler plate y extent: around the slot, up to the tension screw head."""
        front = self.idler_y - self.idler_slot / 2 - TOL.bolt_hole_d(5) / 2 - self.plate_margin
        return (front, self.gantry_front_y - metric(3).head_h - self.head_gap)

    @property
    def idler_top_z(self) -> float:
        """Idler plate top: level with the idler flange top."""
        return Y_AXIS.pulley_axis_z + IDLER.flange_d / 2

    @property
    def idler_foot_x0(self) -> float:
        """Outboard edge of the idler foot."""
        return self.idler_plate_x[0] - self.idler_foot_out

    @property
    def motor_y(self) -> float:
        """Motor shaft axis (machine y): the body clears the rear SK10."""
        return Y_AXIS.sk10_y[1] + SK10.length / 2 + self.motor_gap + NEMA17.width / 2

    @property
    def pulley_hub_x(self) -> float:
        """Pulley's motor-side face (x); the pulley extends outboard from here."""
        return Y_AXIS.belt_x + PULLEY.belt_z

    @property
    def motor_plate_x(self) -> tuple[float, float]:
        """Motor plate x extent; the motor face is its inboard side."""
        x0 = self.pulley_hub_x + self.hub_gap
        return (x0, x0 + self.motor_plate_t)

    @property
    def motor_plate_y(self) -> tuple[float, float]:
        """Motor plate y extent (the motor width)."""
        return (self.motor_y - NEMA17.width / 2, self.motor_y + NEMA17.width / 2)

    @property
    def motor_top_z(self) -> float:
        """Top of the motor and its plate."""
        return Y_AXIS.pulley_axis_z + NEMA17.width / 2

    @property
    def motor_foot_x0(self) -> float:
        """Outboard edge of the motor foot."""
        return self.motor_plate_x[0] - self.motor_foot_out


Y_DRIVE = YDrive()


@dataclass(frozen=True)
class YEndstopMount:
    """Y endstop: the board stands on the idler plate's tower, in the plane of the trigger
    screw's travel (components toward the machine center, front edge toward +y). The screw
    tip, moving -y, pushes the lever toward the board. Board axes: v = +y, w = +x (left
    frame), u = -z on the left side and +z on the right (the board is chiral)."""

    tower_margin: float = 1  #: board edge to tower edge (y)

    @property
    def trigger_tip_y(self) -> float:
        """Trigger screw tip at the end of travel (machine y)."""
        return Y_DRIVE.gantry_front_y + BRACKET.trig_boss[1] - BRACKET.trig_screw_len

    @property
    def board_front_y(self) -> float:
        """Front edge of the board."""
        return self.trigger_tip_y - ENDSTOP.trigger_v

    @property
    def board_y(self) -> tuple[float, float]:
        """Board extent in y: rear edge, front edge."""
        return (self.board_front_y - ENDSTOP.pcb[0], self.board_front_y)

    @property
    def trig_z(self) -> float:
        """Trigger screw axis (abs z)."""
        return Y_AXIS.scs_top_z + BRACKET.trig_z

    @property
    def board_x0(self) -> float:
        """Board underside (left frame x): the lever's center line is on the trigger axis."""
        return BRACKET.trig_x - ENDSTOP.lever_z

    @property
    def tower_x(self) -> tuple[float, float]:
        """Tower x extent: from the idler plate's outer face to the board's underside."""
        return (Y_DRIVE.idler_plate_x[0], self.board_x0)

    @property
    def tower_y(self) -> tuple[float, float]:
        """Tower y extent."""
        return (self.board_y[0] - self.tower_margin, self.board_y[1] + self.tower_margin)

    def board_z_center(self, u_z: int) -> float:
        """Board center height; ``u_z`` = board width direction along z (-1 left, +1 right)."""
        return self.trig_z - u_z * ENDSTOP.contact_u

    def board_z(self, u_z: int) -> tuple[float, float]:
        """Board extent in z."""
        zc = self.board_z_center(u_z)
        return (zc - ENDSTOP.pcb[1] / 2, zc + ENDSTOP.pcb[1] / 2)


Y_ENDSTOP = YEndstopMount()

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
    yield DRIVE.steps_per_mm == 80, "Steps/mm changed — update STATUS.md §5"
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
        X_DRIVE.idler_top_z >= X_BELT.pulley_axis_z + IDLER.flange_d / 2 + 0.5,
        "X idler flange hits the endstop pad",
    )
    yield (
        X_DRIVE.idler_top_z >= X_BELT.pulley_axis_z + TOL.bolt_hole_d(5) / 2 + TOL.min_wall + 2,
        "X idler plate too low around the axle slot",
    )
    yd, ye = Y_DRIVE, Y_ENDSTOP
    shaft_left = Y_AXIS.shaft_x[0]
    yield (
        shaft_left + yd.idler_foot_x0 >= 3 and shaft_left + yd.motor_foot_x0 >= 3,
        "Y drive foot hangs over the baseboard edge",
    )
    yield (
        yd.motor_plate_y[1] <= FRAME.board_size[1],
        "Y motor mount hangs over the back of the baseboard",
    )
    yield (
        yd.motor_plate_y[0] - Y_AXIS.sk10_y[1] - SK10.length / 2 >= yd.motor_gap - 0.01,
        "Y motor hits the rear SK10",
    )
    yield (
        yd.motor_plate_x[1] - NEMA17.shaft_len_min <= yd.pulley_hub_x - PULLEY.hub_len,
        "Shortest motor shaft doesn't reach the Y pulley hub",
    )
    yield (
        Y_AXIS.pulley_axis_z - PULLEY.flange_d / 2 >= yd.foot_t + 1,
        "Y pulley hits the motor foot",
    )
    yield (
        Y_AXIS.pulley_axis_z - NEMA17.width / 2 >= 0,
        "Y motor body would hit the baseboard",
    )
    yield (
        yd.idler_plate_y[1]
        - TOL.insert_pocket_depth
        - (yd.idler_y + yd.idler_slot / 2 + TOL.bolt_hole_d(5) / 2)
        >= TOL.min_wall,
        "Y idler tension screw pocket too close to the axle slot",
    )
    yield (
        ye.board_x0 + ENDSTOP.height <= -SK10.body_w / 2 - 1,
        "Y endstop board (with its connector) hits the front SK10",
    )
    yield (
        yd.idler_y + yd.idler_slot / 2 + IDLER.flange_d / 2 + 1
        <= ye.board_y[0] - ENDSTOP.connector_overhang,
        "Y idler hits the Y endstop board's connector",
    )
    yield (
        ye.board_front_y + ENDSTOP.rest_protrusion <= yd.gantry_front_y - 1,
        "Y endstop lever reaches the gantry bracket",
    )
    yield (
        ye.tower_y[1] <= yd.idler_plate_y[1] and ye.tower_y[0] >= 0,
        "Y endstop tower outside the idler plate or the baseboard",
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
            f"Y drive: idler axle y {fmt(Y_DRIVE.idler_y)} (slot ±{fmt(Y_DRIVE.idler_slot / 2)}), "
            f"motor axis y {fmt(Y_DRIVE.motor_y)}; endstop board front y "
            f"{fmt(Y_ENDSTOP.board_front_y)}, trigger tip y {fmt(Y_ENDSTOP.trigger_tip_y)} at the "
            f"end of travel (X: board front x {fmt(X_ENDSTOP.board_front_x)}, head x "
            f"{fmt(X_ENDSTOP.head_x_min)})",
        ]
    )
