"""Shared design parameters of the DIY pen plotter.

Every dimension a part needs lives here (or, for vendor parts, in
:mod:`plotzker.hardware`); part modules contain no magic numbers. Parameters are
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

from cadder.checks import run_design_checks
from cadder.hardware import (
    ECCENTRIC,
    FT90M,
    GT2,
    IDLER,
    NEMA17,
    PULLEY,
    SCS10UU,
    SK10,
    VSLOT,
    VWHEEL,
    metric,
)
from cadder.printing import Tolerances

from plotzker.hardware import C14_INLET, ENDSTOP, PSU, XT60, Y_SHAFT, ZRIB

# -----------------------------------------------------------------------------
# Print tolerances (tune after a test print; defaults from README.md §7.4)
# -----------------------------------------------------------------------------


#: Print tolerances of this machine's prints (PETG, default profile); cadder's defaults, with the
#: nut slot values measured on test prints (T3.12).
TOL = Tolerances(nut_slot=0.4, nut_t=0.1)

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

    board_size: tuple[float, float, float] = (
        700,
        900,
        18,
    )  #: X × Y × thickness (plywood; wider than the mechanics, D30)
    bed_panel_t: float = 9  #: DESIGN (T3.7): 6–9 mm plywood/MDF
    bed_steel_t: float = 0.8  #: DESIGN (T3.7): 0.5–1 mm galvanized steel
    bed_adjust_gap: float = 5  #: DESIGN (T3.7): baseboard → panel underside, mid-adjustment
    bed_size: tuple[float, float] = (400, 480)  #: DESIGN (T3.7): panel X × Y
    #: DESIGN (T3.7): the steel sheet stops this far short of the panel edge, which leaves the
    #: panel corners free for the adjustment posts' nuts (they stand above the panel)
    steel_margin: float = 24

    @property
    def bed_origin(self) -> tuple[float, float]:
        """Front-left corner of the bed panel (centered on the baseboard)."""
        return (
            (self.board_size[0] - self.bed_size[0]) / 2,
            (self.board_size[1] - self.bed_size[1]) / 2,
        )

    @property
    def steel_size(self) -> tuple[float, float]:
        """Steel sheet X × Y."""
        return (
            self.bed_size[0] - 2 * self.steel_margin,
            self.bed_size[1] - 2 * self.steel_margin,
        )

    @property
    def bed_top_z(self) -> float:
        """Z of the top of the bed."""
        return self.bed_adjust_gap + self.bed_panel_t + self.bed_steel_t

    @property
    def media_top_z(self) -> float:
        """Z of the top of the thickest media."""
        return self.bed_top_z + REQ.media_max_t


FRAME = Frame()


@dataclass(frozen=True)
class WoodScrew:
    """The wood screws on hand for fixing printed parts to the baseboard: 4 × 25 mm,
    countersunk. They are long: under a thin foot they would reach through the plywood, so
    printed parts carry a boss (``boss_t`` thick) at every screw."""

    m: float = 4
    length: float = 25
    head_d: float = 8.0  #: ASSUMED: countersunk head diameter
    tip_margin: float = 2  #: plywood left under the screw tip
    boss_d: float = 13  #: boss diameter (room for the countersink and a wall)

    @property
    def boss_t(self) -> float:
        """Thickness under the head so that the tip stops ``tip_margin`` short of the far face."""
        return self.length - (FRAME.board_size[2] - self.tip_margin)

    @property
    def hole_d(self) -> float:
        """Clearance hole."""
        return self.m + TOL.bolt

    @property
    def sink_d(self) -> float:
        """Countersink diameter at the surface (head plus clearance)."""
        return self.head_d + 2 * TOL.bolt

    @property
    def sink_h(self) -> float:
        """Countersink depth (90° cone)."""
        return (self.sink_d - self.hole_d) / 2


WOOD_SCREW = WoodScrew()

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
# Belt clamps (one cap design for the Y belts under the gantry brackets and the X belt
# under the carriage). The mating part has a flat underside; the belt's back bears on it.
# The cap has a groove (between two rails) that holds the belt sideways, with ridges that
# sit in the tooth gaps; the rails press on the flat underside and set the squeeze.
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class BeltClamp:
    """Belt clamp cap dimensions."""

    squeeze: float = 0.3  #: belt compression in the clamp
    length: float = 20  #: along the belt (10 teeth)
    t: float = 4  #: cap plate thickness (under the groove)
    w: float = 16  #: cap width (across the belt)
    screw_dx: float = 5.5  #: M3 offset from the belt center
    ridge_w: float = 0.9  #: GT2 tooth gap ≈ 1.0
    #: nut underside above the flat underside it clamps against (the floor below takes the pull)
    nut_z: float = 4.0

    @property
    def ridge_h(self) -> float:
        """Tooth ridges (0.35): with the squeeze they engage ~0.65 of the 0.75 tooth."""
        return GT2.tooth_h - self.squeeze - 0.1

    @property
    def channel_d(self) -> float:
        """Groove depth = rail height: the belt less its squeeze."""
        return GT2.thickness - self.squeeze

    @property
    def channel_w(self) -> float:
        """Groove width."""
        return GT2.width + 0.4

    @property
    def total_t(self) -> float:
        """Cap thickness including the rails: from the cap's bottom to the flat underside."""
        return self.t + self.channel_d


CLAMP = BeltClamp()

# -----------------------------------------------------------------------------
# Tool-plate interface v1 (D8, README §3.4)
# -----------------------------------------------------------------------------
# The carriage front face carries a hook (cleat) along its top edge and two M3
# clamp points along its bottom edge. A tool head hangs on the hook and is clamped
# by 2 × M3 into nuts pressed into the carriage.
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
# v1 pen holder (T3.6): gravity-loaded pen slide on a Ø6 rod, lifted by the FT90M
# -----------------------------------------------------------------------------
# Head frame (used by the pen-holder parts): x across (0 = carriage center), d forward
# from the carriage front face (so carriage y = front face − d), z absolute.
#
#   side view (looking along +x, carriage on the left)
#   carriage │ plate │ slide ┌ lug ┐ horn    servo wall ┌ servo ─────────┐
#   face     │       │ column│     │ pin→   ──────────────────────────────
#                      V-block + yoke + M5 thumbscrew clamp the pen (axis ~22 mm out)
#
# The slide hangs on the rod through two printed sleeves. The servo horn's pin sits in a
# slot of the slide's lug and lifts the slide by the slot's ceiling; lowering the pin
# lets the slide drop until the pen touches (gravity sets the pressure) and leaves the
# slot clearance as float.


@dataclass(frozen=True)
class PenHolder:
    """v1 pen holder dimensions."""

    # --- pen slide and rod
    rod_d: float = 6.0  #: Ø6 rod on hand (cut to length, ~63 mm)
    rod_x: float = 5.5  #: DESIGN (T3.6): rod axis x
    sleeve_wall: float = 2.0  #: slide material around the rod bore
    slide_h: float = 45  #: DESIGN (T3.6): slide height (sleeves + relief between)
    sleeve_len: float = 13  #: DESIGN (T3.6): bearing length at each end of the slide
    slide_gap: float = 0.6  #: slide back face ↔ tool plate front face
    slide_z0: float = 47  #: DESIGN (T3.6): slide bottom with the pen on the bed (contact);
    #: high enough that the plate's M3 screws stay reachable under the slide
    lift: float = REQ.pen_lift_min + 2  #: DESIGN: pen-up stroke above contact
    float_travel: float = REQ.pen_float_min  #: DESIGN: slide travel above contact at constant force
    sink: float = 1.0  #: DESIGN: how far the slide may drop below nominal contact
    stop_margin: float = 1.0  #: DESIGN: gap between the slide and the upper arm when raised
    arm_t: float = 5  #: rod arm thickness (z)
    arm_w: float = 10  #: rod arm boss diameter (a pen of any size must clear it)
    rod_seat_depth: float = 4  #: blind rod hole in the lower arm
    # --- pen clamp: 90° V-block, yoke and M5 thumbscrew
    pen_x: float = 13  #: DESIGN (T3.6): pen axis x
    apex_d: float = 11  #: DESIGN (T3.6): V apex distance from the carriage face
    block_half_w: float = 12  #: V-block half width (x)
    yoke_in: float = 9.6  #: yoke arm inner face, from the pen axis (x)
    yoke_clear_d: float = 0.7  #: thumbscrew bar ↔ the largest pen
    yoke_bar_t: float = 8  #: bar thickness (captive M5 nut + walls)
    yoke_h: float = 22  #: yoke height (z)
    clamp_screw_len: float = 20  #: M5 screw
    # --- lift linkage
    horn_hole: int = 1  #: horn hole used for the pin, counted from the tip's last hole
    pin_d: float = 2.0  #: M2 screw through the horn hole (ASSUMED horn hole fit)
    horn_t: float = 1.8  #: ASSUMED: horn thickness
    horn_clear: float = 0.8  #: lug ↔ horn
    boss_clear: float = 0.5  #: horn ↔ servo boss
    pin_reach: float = 3.0  #: how far the pin projects behind the horn into the lug
    slot_extra_w: float = 0.6  #: lug slot width above the pin diameter and its arc shift
    slot_extra_h: float = 1.0
    ceiling_above_z0: float = 22  #: lug slot ceiling above the slide bottom (at contact)
    lug_t: float = 4.4
    lug_x0: float = -13.4
    lug_h: float = 20
    lug_above: float = 4  #: lug material above the slot ceiling (the lifting edge)
    # anti-rotation key: rib on the tool plate in a groove of the lug
    key_x: float = -10.1  #: DESIGN: key center x
    key_w: float = 3.0
    key_h: float = 2.6  #: rib height above the plate face
    # --- servo bracket (wall with a window for the FT90M; the output side faces the plate)
    servo_clear: float = 0.15  #: servo body ↔ window, per side
    wall_t: float = 3.0
    rib_t: float = 1.6  #: outer rib / webs
    web_t: float = 2.0
    wall_margin: float = 3.5  #: wall beyond the outermost tab hole (z)
    wall_extra_z: float = 2.0  #: extra wall height for the horn's swing

    # ---- derived: z
    @property
    def lower_arm_top(self) -> float:
        """Top of the lower rod arm (slide's lowest stop)."""
        return self.slide_z0 - self.sink

    @property
    def lower_arm_bottom(self) -> float:
        """Underside of the lower rod arm."""
        return self.lower_arm_top - self.arm_t

    @property
    def upper_arm_bottom(self) -> float:
        """Underside of the upper rod arm."""
        return self.slide_z0 + self.slide_h + self.lift + self.stop_margin

    @property
    def upper_arm_top(self) -> float:
        """Top of the upper rod arm (and of the body)."""
        return self.upper_arm_bottom + self.arm_t

    @property
    def rod_len(self) -> float:
        """Rod length (from the seat in the lower arm to the top of the upper arm)."""
        return self.upper_arm_top - (self.lower_arm_top - self.rod_seat_depth)

    @property
    def pin_travel(self) -> float:
        """Vertical travel of the pin between pen up and pen down."""
        return self.lift + self.float_travel

    @property
    def horn_r(self) -> float:
        """Radius of the pin hole from the shaft."""
        return FT90M.horn_len - FT90M.horn_last_hole - self.horn_hole * FT90M.horn_hole_pitch

    @property
    def slot_ceiling_z(self) -> float:
        """Lug slot ceiling at contact."""
        return self.slide_z0 + self.ceiling_above_z0

    @property
    def lug_z(self) -> tuple[float, float]:
        """Lug z extent at contact."""
        top = self.slot_ceiling_z + self.lug_above
        return top - self.lug_h, top

    @property
    def pin_down_z(self) -> float:
        """Pin center, pen down: below the ceiling by the pin radius and the float."""
        return self.slot_ceiling_z - self.pin_d / 2 - self.float_travel

    @property
    def pin_up_z(self) -> float:
        """Pin center, pen up."""
        return self.pin_down_z + self.pin_travel

    @property
    def shaft_z(self) -> float:
        """Servo shaft axis: the pin's mid travel (the horn is horizontal)."""
        return self.pin_down_z + self.pin_travel / 2

    @property
    def horn_swing_deg(self) -> float:
        """Horn rotation either side of horizontal."""
        return math.degrees(math.asin(self.pin_travel / 2 / self.horn_r))

    @property
    def servo_body_z(self) -> tuple[float, float]:
        """Servo body z extent: the shaft is near the lower end."""
        length = FT90M.body[0]
        return (
            self.shaft_z - FT90M.shaft_offset,
            self.shaft_z + length - FT90M.shaft_offset,
        )

    @property
    def servo_center_z(self) -> float:
        """Servo body center along z (the tab holes are symmetrical about it)."""
        lo, hi = self.servo_body_z
        return (lo + hi) / 2

    @property
    def wall_z(self) -> tuple[float, float]:
        """Servo wall z extent."""
        half = FT90M.hole_pitch / 2 + self.wall_margin + self.wall_extra_z
        return self.servo_center_z - half, self.servo_center_z + half

    # ---- derived: x
    @property
    def servo_x(self) -> float:
        """Servo center and shaft x: against the outer rib."""
        return -TOOL_PLATE.w / 2 + self.rib_t + self.servo_clear + FT90M.body[1] / 2

    @property
    def pin_x(self) -> float:
        """Pin x at the horn's horizontal position."""
        return self.servo_x + self.horn_r

    @property
    def slot_x(self) -> tuple[float, float]:
        """Lug slot x extent: wide enough for the pin on its arc (x shifts by
        ``horn_r (1 - cos swing)`` between mid travel and the ends)."""
        shift = self.horn_r * (1 - math.cos(math.radians(self.horn_swing_deg)))
        center = self.pin_x - shift / 2
        half = (self.pin_d + shift + self.slot_extra_w) / 2
        return center - half, center + half

    @property
    def wall_x(self) -> tuple[float, float]:
        """Servo wall x extent."""
        return -TOOL_PLATE.w / 2, self.servo_x + FT90M.body[1] / 2 + self.servo_clear + 2

    # ---- derived: d
    @property
    def plate_d(self) -> tuple[float, float]:
        """Tool plate back and front faces."""
        return TOOL_PLATE.fit_gap, TOOL_PLATE.fit_gap + TOOL_PLATE.plate_t

    @property
    def slide_d0(self) -> float:
        """Slide back face."""
        return self.plate_d[1] + self.slide_gap

    @property
    def sleeve_od(self) -> float:
        """Slide column diameter."""
        return self.rod_d + TOL.slide + 2 * self.sleeve_wall

    @property
    def rod_d_pos(self) -> float:
        """Rod axis distance from the carriage face."""
        return self.slide_d0 + self.sleeve_od / 2

    @property
    def horn_d(self) -> tuple[float, float]:
        """Horn back and front faces."""
        back = self.slide_d0 + self.lug_t + self.horn_clear
        return back, back + self.horn_t

    @property
    def wall_d(self) -> float:
        """Servo wall front face (the servo tabs rest on it)."""
        body_h = FT90M.body[2]
        past_tabs = body_h - FT90M.tab_z - FT90M.tab_t
        return self.horn_d[1] + self.boss_clear + FT90M.top_h + past_tabs

    @property
    def servo_front_d(self) -> float:
        """Front end of the servo body."""
        return self.wall_d + FT90M.tab_z + FT90M.tab_t

    def pen_axis_d(self, pen_d: float) -> float:
        """Distance of a pen's axis from the carriage face, held in the 90° V."""
        return self.apex_d + pen_d / 2 * math.sqrt(2)

    @property
    def yoke_bar_d(self) -> tuple[float, float]:
        """Thumbscrew bar back and front faces."""
        back = self.pen_axis_d(REQ.pen_d_range[1]) + REQ.pen_d_range[1] / 2 + self.yoke_clear_d
        return back, back + self.yoke_bar_t

    @property
    def yoke_z(self) -> tuple[float, float]:
        """Yoke z extent (at the slide's mid-height)."""
        mid = self.slide_z0 + self.slide_h / 2
        return mid - self.yoke_h / 2, mid + self.yoke_h / 2


PEN = PenHolder()

# -----------------------------------------------------------------------------
# ZRIB mount under the baseboard (T3.7, D30)
# -----------------------------------------------------------------------------
# Two identical hangers (mirror images) screwed to the underside of the baseboard, one on
# each long side of the board; four posts carry the ZRIB with its components pointing down
# (heat sinks in free air), and two light straps under the legs guard the board's edges.
#
# Mount frame: u along the board's 110 mm (rear) edge = machine X, v toward the rear = machine
# Y, z up with 0 at the underside of the baseboard (the mount hangs at negative z).
#
#   side view along v (one hanger)            ▒▒ rail     ░ board  ▓ strap
#   baseboard ════════════════════════════
#   rail      ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒    ← wood screws at u = ±60 (outside the board)
#   post                ┃  ░░░░░░░░░░░  ┃            posts at the board's holes (u = ±50)
#   leg  ▒             board with parts ↓           ▒ leg
#        ▒                                        ▒
#   strap ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓


@dataclass(frozen=True)
class ZribMount:
    """ZRIB hangers and guard straps."""

    rail_t: float = 6  #: DESIGN (T3.7): hanger rail thickness (z)
    plate_t: float = 5  #: hanger rail thickness (v)
    post_d: float = 9
    post_h: float = 5  #: board's solder side to the rail underside (room for the pin tails)
    leg_w: float = 8  #: along u (an M3 nut fits)
    leg_t: float = 9  #: along v (a nut slot reaches past the screw axis, with a wall)
    leg_gap: float = 11  #: board edge to the leg's inner face
    wood_screw_gap: float = 4  #: board edge to the screw center, along u
    wood_screw_v: float = 5  #: from the post row inward (v), clear of the strap for a driver
    boss_d: float = 11.5  #: round boss that takes the screw head
    strap_t: float = 3
    strap_gap: float = 3  #: heat sink tops to the strap
    strap_screw_len: float = 12  #: M3

    @property
    def board_z(self) -> float:
        """Solder-side face of the board (negative z)."""
        return -(self.rail_t + self.post_h)

    @property
    def sink_bottom_z(self) -> float:
        """Lowest point of the heat sinks."""
        return self.board_z - ZRIB.height

    @property
    def strap_top_z(self) -> float:
        """Top face of the strap."""
        return self.sink_bottom_z - self.strap_gap

    @property
    def strap_bottom_z(self) -> float:
        """Underside of the strap = the mount's total drop below the baseboard."""
        return self.strap_top_z - self.strap_t

    @property
    def leg_u(self) -> tuple[float, float]:
        """Leg extent along u (positive side)."""
        inner = ZRIB.width / 2 + self.leg_gap
        return inner, inner + self.leg_w

    @property
    def wood_screw_u(self) -> float:
        """Wood screw position along u (positive side)."""
        return ZRIB.width / 2 + self.wood_screw_gap

    @property
    def post_v(self) -> float:
        """Post row (negative-v side hanger): -hole pitch / 2."""
        return -ZRIB.hole_pitch[1] / 2

    @property
    def plate_v(self) -> tuple[float, float]:
        """Plate extent along v (negative-v hanger): the outer face is flush with the posts'."""
        outer = self.post_v - self.post_d / 2
        return outer, outer + self.plate_t

    @property
    def strap_screw_u(self) -> float:
        """Strap screw position along u (positive side): the leg's center."""
        return sum(self.leg_u) / 2

    @property
    def strap_screw_v(self) -> float:
        """Strap screw position along v (negative-v hanger): the leg's center."""
        return self.plate_v[0] + self.leg_t / 2

    @property
    def strap_nut_z(self) -> float:
        """Bottom of the strap screw's nut slot (the leg's end wall below it is 2 mm)."""
        return self.strap_top_z + 2


ZMOUNT = ZribMount()


# -----------------------------------------------------------------------------
# PSU beside the baseboard (T3.31, D38)
# -----------------------------------------------------------------------------
# The supply stands on edge beside the board's right edge, off the table (D30: free air to
# its fan, mains off the plywood): bottom face (M4 holes) toward the board, fan face out,
# label wall up, switch wall (115/230 V selector) down, terminal end toward the front. Two
# brackets hang it from the board's underside; a printed hood closes the terminal end and
# carries the C14 inlet (fuse + switch) and the XT60.
#
#   seen from the front (machine x →, z ↑)       ▒ bracket  ░ PSU  ═ board
#
#                       ▒▒░░░░░░░░░░░░   ← label wall up, z = top_z
#   ════════════════════▒▒░░░░░░░░░░░░   board top z = 0
#   ════════════════════▒▒░░░░PSU░░░░░   M4 into the bottom face (holes 50 apart)
#             ▒▒▒▒▒▒▒▒▒▒▒▒░░░░░░░░░░░░   flange under the board: 2 wood screws up
#                         ░░░░░░░░░░░░   fan face → (free air)
#                                         switch wall down, clear of the table
#
# Parts are designed in the PSU frame (hardware/psu.py); ``placement`` takes it to the machine.


@dataclass(frozen=True)
class PsuMount:
    """PSU brackets and terminal hood."""

    # Placement (machine frame)
    #: DESIGN (T3.31): bottom face to the board edge = bracket upright (15: FEM found 10 and 12
    #: too flexible when the PSU is leant on)
    edge_gap: float = 15
    #: DESIGN (T3.31): machine z of the label wall (the PSU's top). The lower M4 holes then sit
    #: in front of the board's edge, and the hood stays well clear of the table
    top_z: float = 69
    # Brackets (PSU frame)
    bracket_w: float = 28  #: along y, centered on a hole line
    hole_margin: float = 8  #: the upright reaches this far past the upper M4 hole
    flange_reach: float = 40  #: flange under the board, from the board edge inward
    wood_screw_in: tuple[float, float] = (9, 31)  #: wood screws, inward from the board edge
    psu_screw_len: float = 15  #: M4 ISO 4762 into the bottom face
    #: DESIGN (T3.31, FEM): above the board the upright grows inward and rests on the board's
    #: top, so the PSU's pull can't bend it about the corner alone
    brace_t: float = 4
    #: DESIGN (T3.31, FEM): fillet in the upright/flange corner; the board's underside edge on
    #: the right side is eased (45°) by the same amount to make room for it. 1, not 3: the lower
    #: M4's head counterbore reaches to 1.6 mm from the corner
    corner_r: float = 1
    # Hood (PSU frame)
    #: DESIGN (T3.31): hood inside to the PSU case, each side. 0: the first print, at 0.5, came
    #: out 51 across the 50 mm case and was loose
    clearance: float = 0.0
    wall_t: float = 2.0
    #: DESIGN (T3.31): in front of the wall ends: the inlet's flange (49.5 across its points)
    #: lies along it and over the start of the fan-side sleeve
    depth: float = 42
    sleeve_fan: float = 24  #: over the fan face: covers the open strip (cover setback 18.4)
    sleeve_side: float = 40  #: screw tabs over the label and switch walls, past the y = 32 holes
    tab_margin: float = 7  #: the tabs reach this far past their holes (in z)
    sleeve_bottom: float = 8  #: over the bottom face, short of the bracket
    hood_screw_len: float = 6  #: M4 ISO 4762 through a tab into the case
    #: DESIGN (T3.31): inlet cutout center; its long side runs along x (across the print, a
    #: 48 mm bridge), clear of the XT60 behind it
    inlet_x: float = 64
    inlet_y: float = -16
    inlet_boss_t: float = 3.5  #: boss inside the wall for the inlet's M3 nuts
    #: DESIGN (T3.31): XT60 in the board-side wall, low (under the board), in line with the ZRIB,
    #: close to the open end so it can be pushed in by hand from inside
    xt60_x: float = 100
    xt60_y: float = -22
    #: lip round the front section's window: the collar stops on it when the plug is pulled
    xt60_lip: float = 0.8
    #: the window's corner chamfers on one side, the connector's 2.2: keys the polarity
    xt60_key: float = 2.2
    #: the pocket's rounded corners on that side, a little under the collar's
    xt60_pocket_r: float = 1.2
    #: DESIGN (T3.31): press fit, per side, tuned on test pieces. Negative: interference.
    #: Across the connector's short side (its width), where the fit grips:
    xt60_window_fit: float = -0.2  #: window 6.0 on the 6.4 front (it prints ~0.2 wide)
    xt60_pocket_fit: float = -0.05  #: pocket 8.0 on the 8.1 collar (it prints to size)
    #: along its long side:
    xt60_window_long_fit: float = 0.0
    xt60_pocket_long_fit: float = 0.05
    #: extra room at the top of the print (+y) for the window's and pocket's bridges to sag
    #: into; without it the collar stopped 0.9 short of the lip on that side
    xt60_window_relief: float = 0.3
    xt60_pocket_relief: float = 0.5
    #: DESIGN (T3.31): how far behind the lip the pocket grips the collar: short of the rim
    xt60_grip: float = 3.0
    #: the male plug stands out round the female's front section by about this much (ASSUMED)
    xt60_plug_margin: float = 5

    @property
    def xt60_sleeve(self) -> float:
        """Sleeve inside the board-side wall: ends within the collar, so nothing reaches the
        rim behind it."""
        return self.xt60_lip + self.xt60_grip - self.wall_t

    @property
    def xt60_protrude(self) -> float:
        """How far the mating face stands out of the wall."""
        return XT60.front_len - self.xt60_lip

    @property
    def xt60_window(self) -> tuple[float, float]:
        """The lip's window: along x (the connector's height) and along y (its width)."""
        w, h = XT60.front
        return h + 2 * self.xt60_window_fit, w + 2 * self.xt60_window_long_fit

    @property
    def xt60_pocket(self) -> tuple[float, float]:
        """The pocket gripping the collar behind the lip: along x and along y."""
        w, h = XT60.collar
        return h + 2 * self.xt60_pocket_fit, w + 2 * self.xt60_pocket_long_fit

    @property
    def terminal_y(self) -> float:
        """Machine y of the terminal end: the XT60 lines up with the ZRIB's center."""
        return BASEBOARD.zrib_center[1] - self.xt60_y

    @property
    def origin(self) -> tuple[float, float, float]:
        """Machine position of the PSU frame's origin (the frame turns +90° about y)."""
        return FRAME.board_size[0] + self.edge_gap, self.terminal_y, self.top_z

    @property
    def low_z(self) -> float:
        """Machine z of the switch wall (the PSU's underside)."""
        return self.top_z - PSU.size[0]

    @property
    def board_x(self) -> tuple[float, float]:
        """The baseboard's top and underside in PSU x (x runs downward)."""
        return self.top_z, self.top_z + FRAME.board_size[2]

    @property
    def edge_z(self) -> float:
        """The board edge in PSU z (the board lies at z below this)."""
        return -self.edge_gap

    @property
    def upright_x(self) -> tuple[float, float]:
        """The bracket upright's extent in PSU x: past the upper hole down to the flange."""
        return PSU.bottom_hole_x[0] - self.hole_margin, self.board_x[1] + WOOD_SCREW.boss_t

    @property
    def wood_screw_z(self) -> tuple[float, ...]:
        """The flange's wood screws in PSU z."""
        return tuple(self.edge_z - d for d in self.wood_screw_in)

    @property
    def counterbore(self) -> tuple[float, float]:
        """M4 head counterbore in the upright: diameter, depth."""
        m4 = metric(4)
        return m4.head_d + 2 * TOL.bolt, m4.head_h + TOL.bolt

    @property
    def psu_screw_depth(self) -> float:
        """How far the bracket's M4 enters the case."""
        return self.psu_screw_len - (self.edge_gap - self.counterbore[1])

    @property
    def hood_screw_depth(self) -> float:
        """How far a hood screw enters the case (head on the sleeve)."""
        return self.hood_screw_len - self.wall_t - self.clearance

    @property
    def hood_x(self) -> tuple[float, float, float, float]:
        """Hood in PSU x: outer and inner faces (outer0, inner0, inner1, outer1)."""
        c, t = self.clearance, self.wall_t
        return -c - t, -c, PSU.size[0] + c, PSU.size[0] + c + t

    @property
    def hood_z(self) -> tuple[float, float, float, float]:
        """Hood in PSU z: outer and inner faces (outer0, inner0, inner1, outer1)."""
        c, t = self.clearance, self.wall_t
        return -c - t, -c, PSU.size[2] + c, PSU.size[2] + c + t

    @property
    def brace_z(self) -> float:
        """The brace's inner face over the board's top (PSU z)."""
        return self.edge_z - self.brace_t

    @property
    def pilot_xy(self) -> tuple[tuple[float, float], ...]:
        """Pilot holes for the brackets' wood screws, in the machine frame (from below)."""
        ox, oy, _ = self.origin
        return tuple((ox + z, oy + y) for y in PSU.hole_y for z in self.wood_screw_z)


PSU_MOUNT = PsuMount()


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
        return (board_x - self.shaft_spacing) / 2, (board_x + self.shaft_spacing) / 2

    @property
    def shaft_y0(self) -> float:
        """Shaft front end."""
        return (FRAME.board_size[1] - Y_SHAFT.length) / 2

    @property
    def sk10_y(self) -> tuple[float, float]:
        """SK10 mid-thickness, front and back."""
        return self.shaft_y0 + SK10.length / 2, self.shaft_y0 + Y_SHAFT.length - SK10.length / 2

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

    @property
    def gantry_y_range(self) -> tuple[float, float]:
        """Gantry center along Y (machine frame) at the front and back ends of travel."""
        front = self.shaft_y0 + SK10.length + self.end_margin + self.gantry_len_y / 2
        return front, front + self.travel_avail

    # Y belt line (fixes the Y motor and idler heights for T3.5)
    @property
    def belt_back_z(self) -> float:
        """Back of the belt's top run (abs z)."""
        return self.scs_top_z  # the belt back is flush with the bracket's flat underside

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


@dataclass(frozen=True)
class Carriage:
    """X carriage dimensions."""

    #: DESIGN (T3.3): wheel center to center along X; wide enough that the bottom
    #: wheels' bolt heads sit outside the 50 mm tool plate
    wheel_pitch_x: float = 64
    plate_t: float = 8  #: DESIGN (T3.3): front plate thickness
    #: DESIGN: counterbore depth for the axle bolts' washers and heads on the front face
    #: (lets M5×42 bolts replace the M5×35)
    head_recess: float = 2
    margin_below_wheel: float = 3  #: DESIGN (T3.3): material below the lowest wheel edge
    #: Printed stand-off under each top wheel: bears on the 625 inner ring only (land ≈ 8)
    top_boss_d: float = 7.5
    bridge_w: float = 34  #: bridge over the beam top, between the top wheels (x)
    bridge_clear: float = 2.5  #: bridge underside above the beam top
    bridge_h: float = 17.5
    rear_w: float = 52  #: rear clamp block width (x): two X belt clamps
    rear_h: float = 17.5  #: rear clamp block height (its top is the X belt's flat bearing face)
    tab_w: float = 24  #: top tab (connector + strain relief) width
    tab_h: float = 15  #: top tab height above the plate
    zip_slot: tuple[float, float] = (4, 2)  #: zip-tie slot (x × z)
    #: X endstop trigger screw (M3): short, so the captive nut cannot pull it off its axis
    #: (T3.14); it still reaches ~3 mm through the nut at the end of its adjustment
    trig_screw_len: float = 12
    trig_dy: float = -0.5  #: X endstop trigger screw: y behind the X belt center (plug space)

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
        return BEAM.top_z + VWHEEL.axis_to_face, BEAM.bottom_z - VWHEEL.axis_to_face

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
        """Bridge underside (abs z): the bridge passes under the beam (DESIGN: X belt at the
        bottom of the carriage)."""
        return BEAM.bottom_z - self.bridge_clear - self.bridge_h

    @property
    def block_z(self) -> float:
        """Rear block underside (abs z); its top is the X belt's bearing face."""
        return X_BELT.back_z - self.rear_h

    @property
    def trig_y(self) -> float:
        """X endstop trigger screw y."""
        return X_BELT.y + self.trig_dy

    @property
    def trig_z(self) -> float:
        """X endstop trigger screw axis (abs z): the lever's height above the board's shelf."""
        return X_ENDSTOP.board_bottom_z + ENDSTOP.lever_z

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

    @property
    def center_x_range(self) -> tuple[float, float]:
        """Carriage center along X (machine frame) at the left and right ends of travel."""
        beam_x0 = (FRAME.board_size[0] - BEAM.length) / 2
        left = beam_x0 + self.end_keepout + self.w / 2
        return left, left + self.travel_avail


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
    def shelf_x(self) -> float:
        """Left bracket only: the base reaches out to the X idler tower's outer face (T3.22)."""
        return X_IDLER.tower_s0

    @property
    def shelf_y(self) -> tuple[float, float]:
        """Y range of the shelf: the tower's."""
        return X_IDLER.tower_across

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
# T3.4). The lower run is cut and clamped on top of the carriage's rear block.
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class XBelt:
    """X belt position."""

    #: Belt center behind the beam's rear face. Set so the X motor plate fits between
    #: the gantry bracket's rear bolt rows and long motor shafts clear the beam (T3.4)
    behind_beam_face: float = 16
    motor_clear: float = 1  #: motor body above the unclamped rear bolt heads

    @property
    def y(self) -> float:
        """Belt center behind the beam's center plane (23)."""
        return BEAM.depth / 2 + self.behind_beam_face

    @property
    def back_z(self) -> float:
        """Back of the lower run (abs z): the carriage's rear block top bears on it."""
        return self.pulley_axis_z - GT2.pitch_line_from_back - PULLEY.pd / 2

    @property
    def pulley_axis_z(self) -> float:
        """X motor shaft / idler axle (abs z). DESIGN: as low as the motor allows: its body
        clears the rear bolt heads (the foot clamps only the front row) by ``motor_clear``."""
        return (
            Y_AXIS.scs_top_z
            + BRACKET.base_t
            + metric(5).head_h
            + self.motor_clear
            + NEMA17.width / 2
        )


X_BELT = XBelt()

# -----------------------------------------------------------------------------
# X endstop (T3.4, redone in T3.5 for the measured board): the board lies flat
# (components up, front edge toward +x) on a pad on the idler plate top. The carriage's
# trigger screw head, moving -x, pushes the lever toward the board. Left bracket-local
# frame (see X drive below). Board axes: u = -y, v = +x, w = +z.
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class XEndstopMount:
    """X endstop: the board lies directly on the idler mount's foot (Creality type)."""

    #: DESIGN (T3.14): recess in the foot under the board, for the solder joints and pins that
    #: protrude up to 1.8 mm (measured) from its underside, so the board seats flat on the lands
    relief_depth: float = 2.2
    land_d: float = 6  #: flat land around each board screw hole

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
        return self.board_front_x - ENDSTOP.pcb[0], self.board_front_x

    @property
    def board_y(self) -> tuple[float, float]:
        """Board extent in y: the lever hinge is at +y, its tip toward -y."""
        yc = CARRIAGE.trig_y + ENDSTOP.contact_u
        return yc - ENDSTOP.pcb[1] / 2, yc + ENDSTOP.pcb[1] / 2

    @property
    def board_bottom_z(self) -> float:
        """Board underside (abs z) = top of the idler mount's foot."""
        return Y_AXIS.scs_top_z + BRACKET.base_t + X_DRIVE.foot_t

    @property
    def hole_x(self) -> float:
        """Board mounting hole line (x)."""
        return self.board_front_x + ENDSTOP.hole_v

    @property
    def plug_top_z(self) -> float:
        """Top of the plug keep-out (bracket-local z)."""
        e = ENDSTOP
        return self.board_bottom_z - Y_AXIS.scs_top_z + e.pcb[2] + e.connector[2] + e.plug_clearance

    @property
    def plug_x0(self) -> float:
        """Outboard end of the plug keep-out (x), bracket-local."""
        return self.board_front_x + ENDSTOP.plug_keepout_v


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
    #: DESIGN (T3.11): counterbore for the motor mount's M5 heads, so they clear the motor's
    #: lowest M3 screw heads (the thread engagement of the M5×25 grows to the block's 12 mm)
    foot_head_recess: float = 2
    # Motor
    motor_x: float = 1  #: DESIGN: motor shaft x (near the beam end)
    motor_plate_t: float = 5  #: front face = plate_y0
    motor_rib_t: float = 6  #: rib under the motor
    # Idler: a floating slider tied to a tower on the bracket (X_IDLER, T3.22)
    #: DESIGN (T3.16): idler axle at mid-travel, outboard of the beam end
    idler_x: float = -21
    #: DESIGN (T3.22): the endstop mount's foot (the only foot left on the idler side) reaches
    #: out to this x, past the rear bolts
    foot_x0: float = -20

    @property
    def bolt_rows(self) -> tuple[float, float]:
        """Rear SCS bolt rows (y)."""
        p, c = Y_AXIS.scs_pitch, SCS10UU.hole_pitch_y
        return p / 2 - c / 2, p / 2 + c / 2

    @property
    def plate_y0(self) -> float:
        """Plates start behind the first bolt row."""
        return self.bolt_rows[0] + metric(5).head_d / 2 + 0.75

    @property
    def foot_y(self) -> tuple[float, float]:
        """Y range of the foot under the SCS block."""
        p, length = Y_AXIS.scs_pitch, SCS10UU.length
        return p / 2 - length / 2, p / 2 + length / 2

    @property
    def motor_face_y(self) -> float:
        """Motor mounting face."""
        return self.plate_y0 + self.motor_plate_t

    @property
    def pulley_hub_y(self) -> float:
        """Pulley's motor-side end."""
        return X_BELT.y + PULLEY.belt_z

    @property
    def motor_foot_y(self) -> tuple[float, float]:
        """Y range of the motor mount's foot: under the front bolt row and the plate only."""
        return self.foot_y[0], self.motor_face_y


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

    foot_t: float = 6  #: printed foot on the baseboard; the screws go through bosses (WOOD_SCREW)
    # SK10 corner pocket (both mounts): the SK10's base sits in a cut-out of the foot, pushed
    # into the corner formed by the end wall (against its outer face, the shaft-end plane) and
    # the outboard side wall. The inboard side and the side toward the other SK10 are open, so
    # the SK10's width and chamfer tolerances don't matter.
    pocket_wall: float = 4  #: end wall thickness (it also spaces the motor)
    #: DESIGN (T3.5): end wall reach from the SK10's outboard edge. Short enough not to be
    #: fragile (a thin cantilever), long enough to square the mount to the SK10's face
    pocket_end_len: float = 24
    # Idler: a floating slider tied to a tower on the foot (Y_IDLER, T3.23)
    idler_slot: float = 8  #: tension travel along y (the idler's travel; belt ±4 mm)
    # Motor (shaft points outboard; body inboard, behind the rear SK10)
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
    def motor_gap(self) -> float:
        """Rear SK10 face to the motor body: the pocket's end wall."""
        return self.pocket_wall

    @property
    def pocket_half(self) -> float:
        """Wall faces at the SK10's nominal outboard edge (no clearance: the SK10 touches it)."""
        return SK10.width / 2

    @property
    def front_pocket_y(self) -> tuple[float, float]:
        """Front pocket's frame, y extent: from the end wall's outer face to the SK10's inboard
        face."""
        return Y_AXIS.shaft_y0 - self.pocket_wall, Y_AXIS.shaft_y0 + SK10.length

    @property
    def rear_pocket_y(self) -> tuple[float, float]:
        """Rear pocket's frame, y extent."""
        end = Y_AXIS.shaft_y0 + Y_SHAFT.length
        return end - SK10.length, end + self.pocket_wall

    @property
    def idler_y(self) -> float:
        """Idler axle, middle of the slot (machine y): the idler stays clear of the endstop
        board's plug keep-out."""
        return Y_ENDSTOP.keepout_y0 - 1 - self.idler_slot / 2 - IDLER.flange_d / 2

    @property
    def idler_block_y(self) -> float:
        """Outer (front) face of the tensioner's end block, machine y: the screw head's seat."""
        return Y_IDLER.tower_s0

    @property
    def idler_foot_x0(self) -> float:
        """Outboard edge of the idler foot: the wood screws' bosses, outboard of the tower."""
        return Y_IDLER.belt_pos - Y_IDLER.tower_half - WOOD_SCREW.boss_d - 1

    @property
    def idler_foot_x1(self) -> float:
        """Inboard edge of the idler foot's main plate (the tower's pad reaches further)."""
        return Y_AXIS.belt_x + 9.5

    @property
    def idler_foot_y(self) -> tuple[float, float]:
        """Y extent of the idler foot's main plate: the end block to the endstop tower."""
        return self.idler_block_y, Y_ENDSTOP.tower_y[1] + Y_ENDSTOP.tower_margin

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
        return x0, x0 + self.motor_plate_t

    @property
    def motor_plate_y(self) -> tuple[float, float]:
        """Motor plate y extent (the motor width)."""
        return self.motor_y - NEMA17.width / 2, self.motor_y + NEMA17.width / 2

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
    tower_t: float = 10  #: tower thickness (x): room for the M3 nut pockets in its outboard face
    #: DESIGN (T3.14): recess in the tower face under the board for the solder joints and pins
    #: that protrude up to 1.8 mm (measured), leaving a flat land round each screw hole
    relief_depth: float = 2.2
    land_d: float = 6

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
        return self.board_front_y - ENDSTOP.pcb[0], self.board_front_y

    @property
    def keepout_y0(self) -> float:
        """Rear end of the plug keep-out behind the connector."""
        return self.board_front_y + ENDSTOP.plug_keepout_v

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
        """Tower x extent: its outboard face to the board's underside."""
        return self.board_x0 - self.tower_t, self.board_x0

    @property
    def tower_y(self) -> tuple[float, float]:
        """Tower y extent."""
        return self.board_y[0] - self.tower_margin, self.board_y[1] + self.tower_margin

    def board_z_center(self, u_z: int) -> float:
        """Board center height; ``u_z`` = board width direction along z (-1 left, +1 right)."""
        return self.trig_z - u_z * ENDSTOP.contact_u

    def board_z(self, u_z: int) -> tuple[float, float]:
        """Board extent in z."""
        zc = self.board_z_center(u_z)
        return zc - ENDSTOP.pcb[1] / 2, zc + ENDSTOP.pcb[1] / 2


Y_ENDSTOP = YEndstopMount()

# -----------------------------------------------------------------------------
# Y loom (T3.8, D32): one round loom from the gantry's right bracket, folded in a U on the
# baseboard beside the right Y belt, through a hole in the baseboard to the ZRIB
# -----------------------------------------------------------------------------
# Top view of the strip right of the right shaft (x from the shaft; ▒ = inner rail segments):
#
#    belt │▒│ moving leg      static leg │ edge          U fold travels with the gantry:
#    +30  │▒│ +48                +80     │ +90           the fold sits half as far from the
#         rail 40…42.5   (loom Ø8, R 16)                 anchor as the gantry does


@dataclass(frozen=True)
class Loom:
    """The gantry loom (dimensions of the finished loom: ASSUMED until it is built) and the
    parts that guide it."""

    d: float = 8  #: ASSUMED: loom outer diameter (STATUS.md T3.8 spec)
    bend_r: float = 16  #: ASSUMED: tightest bend radius (centerline)
    tie_w: float = 3.6  #: zip tie width
    tie_t: float = 1.5  #: zip tie thickness
    # Anchor block on the right bracket's base, outboard of the X motor mount (bracket-local frame)
    anchor_x: tuple[float, float] = (-38, -23)  #: flush with the base's outboard edge
    anchor_y: tuple[float, float] = (12, 42)  #: between the beam rib and the belt clamp
    anchor_h: float = 12
    anchor_screw_x: float = -30.5
    anchor_screw_y: tuple[float, float] = (15, 39)  #: M3 pair, either side of the groove
    anchor_screw_len: float = 16
    # Path (offsets from the right shaft axis x; machine y)
    moving_dx: float = 48  #: lying leg that follows the gantry
    static_dx: float = 80  #: lying leg that stays
    rail_dx: float = 42  #: loom-side face of the inner rail
    rail_t: float = 2.5
    rail_h: float = 12
    rail_len: float = 80
    rail_pitch: float = 100
    rail_count: int = 6
    rail_y0: float = 200  #: first segment's start
    foot_w: float = 14  #: rail foot, on the belt side
    hole_d: float = 12  #: baseboard hole to the ZRIB
    hole_y: float = 150  #: static anchor: the hole's y (the loom ends there)
    exit_dy: float = 27  #: anchor groove axis behind the gantry center

    @property
    def anchor_cy(self) -> float:
        """Groove axis along the block (bracket-local y)."""
        return sum(self.anchor_y) / 2

    @property
    def groove_z(self) -> float:
        """Loom axis in the anchor groove, bracket-local z."""
        return BRACKET.base_t + self.anchor_h - 4.5

    def drop_arc(self, steps: int = 7) -> list[tuple[float, float]]:
        """Axis of the loom's bend from the groove down toward the baseboard, as (bracket-local
        x, bracket-local z) points. The bend starts before the loom leaves the block, so the
        anchor carries a relief along it."""
        x0 = -(self.moving_dx - self.bend_r)
        return [
            (
                x0 - self.bend_r * math.sin(a),
                self.groove_z - self.bend_r + self.bend_r * math.cos(a),
            )
            for a in (math.radians(90 * i / (steps - 1)) for i in range(steps))
        ]

    @property
    def lying_z(self) -> float:
        """Axis of the loom lying on the baseboard."""
        return self.d / 2

    @property
    def hole_x(self) -> float:
        """Static leg x and the baseboard hole (machine frame)."""
        return Y_AXIS.shaft_x[1] + self.static_dx

    @property
    def moving_x(self) -> float:
        """Moving leg x (machine frame)."""
        return Y_AXIS.shaft_x[1] + self.moving_dx

    @property
    def rail_x(self) -> float:
        """Loom-side face of the inner rail (machine frame)."""
        return Y_AXIS.shaft_x[1] + self.rail_dx

    @property
    def rail_starts(self) -> tuple[float, ...]:
        """Start y of each rail segment."""
        return tuple(self.rail_y0 + i * self.rail_pitch for i in range(self.rail_count))

    @property
    def fold_width(self) -> float:
        """Distance between the legs' axes (= 2 R, set by the fold)."""
        return self.static_dx - self.moving_dx

    def start_y(self, gantry_y: float) -> float:
        """Where the moving leg starts to lie on the baseboard (after the drop)."""
        return gantry_y + self.exit_dy + self.bend_r

    @property
    def lying_len(self) -> float:
        """Length of loom lying on the baseboard: fixed, set so that the fold just clears the
        drop with the gantry at the back end."""
        back = Y_AXIS.gantry_y_range[1]
        return math.pi * self.bend_r + self.start_y(back) - self.hole_y

    def fold_y(self, gantry_y: float) -> float:
        """Where the U fold starts (the straight legs end), for the gantry at ``gantry_y``."""
        return (self.lying_len - math.pi * self.bend_r + self.hole_y + self.start_y(gantry_y)) / 2

    @property
    def apex_y(self) -> float:
        """Rearmost point of the fold (gantry at the back end)."""
        return self.fold_y(Y_AXIS.gantry_y_range[1]) + self.bend_r


LOOM = Loom()

# -----------------------------------------------------------------------------
# Baseboard layout (T3.7, D31): runners underneath, SK10 holes, bed posts, ZRIB position
# -----------------------------------------------------------------------------
# Machine frame, seen from above (x across, y front to back); ▒ = runner on the underside:
#
#   y 900 ┌──────────────────────────────────────────────┐
#         │  Y motor mounts (not pre-drilled, D26)       │
#   y 750 │   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ runner 3 ▒▒▒▒▒▒▒▒▒▒▒▒▒▒    │
#         │      ◎ post                       ◎ post     │  bed posts (M5 stud from below)
#   y 450 │   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ runner 2 ▒▒▒▒▒▒▒▒▒▒▒▒▒▒    │
#         │              ZRIB under here →  [ZRIB]       │  between runners 1 and 2
#   y 150 │   ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ runner 1 ▒▒▒▒▒▒▒▒▒▒▒▒▒▒    │
#         │  SK10 ▪▪                             ▪▪ SK10 │
#   y   0 └──────────────────────────────────────────────┘


@dataclass(frozen=True)
class Baseboard:
    """Runners, bed posts and the ZRIB position on the baseboard."""

    # Runners: 2040 offcuts on edge (20 wide along y, 40 tall), along X under the board
    runner_len: float = 520
    runner_w: float = 20
    runner_h: float = 40
    runner_pitch: float = 300  #: DESIGN (T3.7): runner to runner; the middle one is centered
    runner_screws: int = 4  #: per runner: M5 countersunk into drop-in T-nuts in the top slot
    runner_screw_len: float = 30
    runner_screw_head_d: float = 10.0  #: M5 countersunk head (ISO 10642)
    tnut_t: float = 4.0  #: ASSUMED: M5 drop-in T-nut thickness
    slot_lip_t: float = 1.8  #: ASSUMED: wall between the profile's top face and the T-nut
    # SK10 fixing: M5 bolts through the baseboard, nut and washer underneath
    sk10_bolt_len: float = 35
    #: DESIGN (T3.7): holes under the second rail's SK10s are oversized, so the gantry aligns
    #: that rail (README §3.2)
    sk10_float_hole_d: float = 7.0
    # Bed posts: an M5 stud from below (head under the board) carries the panel on a spring; a
    # nut on top of the panel pulls it down. Turn the nut to level the corner (README §3.8)
    post_inset: float = 15  #: panel corner to post axis
    post_bolt_len: float = 45
    post_adjust: float = 3  #: DESIGN: panel height range ± around ``Frame.bed_adjust_gap``
    spring_od: float = 9
    spring_id: float = 6
    spring_len: float = 12  #: free length
    # ZRIB: centered between the first two runners, toward the right (its USB side faces +y)
    zrib_from_right: float = 180
    pilot_d: float = 2.5  #: DESIGN: pilot hole for the 4 mm wood screws (hangers)

    @property
    def runner_x(self) -> tuple[float, float]:
        """Runner extent along X (centered on the board, like the beam)."""
        x0 = (FRAME.board_size[0] - self.runner_len) / 2
        return x0, x0 + self.runner_len

    @property
    def runner_y(self) -> tuple[float, float, float]:
        """Runner center lines along Y."""
        mid = FRAME.board_size[1] / 2
        return mid - self.runner_pitch, mid, mid + self.runner_pitch

    @property
    def runner_screw_x(self) -> tuple[float, ...]:
        """Screw positions along a runner, evenly spread."""
        x0, x1 = self.runner_x
        step = (x1 - x0) / self.runner_screws
        return tuple(x0 + (i + 0.5) * step for i in range(self.runner_screws))

    @property
    def sk10_hole_x(self) -> tuple[float, float]:
        """SK10 hole offsets from the shaft axis."""
        return -SK10.hole_pitch / 2, SK10.hole_pitch / 2

    @property
    def post_xy(self) -> tuple[tuple[float, float], ...]:
        """Bed post axes: four points near the panel corners."""
        x0, y0 = FRAME.bed_origin
        bx, by = FRAME.bed_size
        i = self.post_inset
        return tuple((x, y) for x in (x0 + i, x0 + bx - i) for y in (y0 + i, y0 + by - i))

    @property
    def zrib_center(self) -> tuple[float, float]:
        """ZRIB mount origin (the board's center) in the machine frame."""
        return (
            FRAME.board_size[0] - self.zrib_from_right,
            (self.runner_y[0] + self.runner_y[1]) / 2,
        )

    @property
    def zrib_pilot_xy(self) -> tuple[tuple[float, float], ...]:
        """Pilot holes for the hangers' wood screws (mount frame u → x, v → y)."""
        cx, cy = self.zrib_center
        u = ZMOUNT.wood_screw_u
        v = abs(ZMOUNT.post_v + ZMOUNT.wood_screw_v)
        return tuple((cx + su * u, cy + sv * v) for sv in (-1, 1) for su in (-1, 1))

    @property
    def post_stud_z(self) -> float:
        """Underside of the bolt head's washer: the head hangs under the board."""
        return -FRAME.board_size[2] - metric(5).washer_t

    @property
    def nut_top_z(self) -> float:
        """Top of the post's nut at the highest panel setting."""
        m5 = metric(5)
        top_panel = FRAME.bed_adjust_gap + self.post_adjust + FRAME.bed_panel_t
        return top_panel + m5.washer_t + m5.nut_h


BASEBOARD = Baseboard()

# -----------------------------------------------------------------------------
# Design checks — the build fails if the parameters break a requirement
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class FloatingIdler:
    """A belt idler on a floating slider held only by its tension screw (STATUS.md T3.22, T3.23).

    The screw runs along the belt line at the axle's height, through a tower (on the left gantry
    bracket for X, on the idler mount for Y), so the belt's pull and the screw's are one line: no
    couple, no rail. The screw head sits on the tower's outer face (hex key from outside); a
    captive nut at the slider's rear wall pulls the slider toward the tower, and a blind tunnel in
    the wall takes the screw's tip as the slider moves. Two walls beside the slider (gussets of
    the tower) only keep it from rolling.

    Two frames: the *installed* frame of the part that carries the tower, where ``s`` is the
    coordinate along the slide direction and ``belt_pos`` the belt line's transverse position;
    and the *tensioner* frame (x along the slide, from the tower's outer face; y along the axle,
    on the belt line; z as in the installed frame), where the slider's solids and the FEM regions
    are described.
    """

    axle_z: float  #: idler axle and tension screw height (installed frame z)
    axle_pos: float  #: idler axle along the slide direction at mid-travel (installed frame)
    belt_pos: float  #: the belt line's transverse position (installed frame)
    floor_z: float  #: top of what the tower stands on (installed frame z)
    #: DESIGN: the walls run along the slider to this slide coordinate (installed frame)
    wall_end_s: float
    axle_m: float = 5  #: idler axle (bolt) size
    screw_m: float = 3  #: tension screw size
    side_play: float = 1.0  #: idler end play to each arm
    travel: float = 8  #: DESIGN: slider travel (tensioning range)
    stop_gap: float = 0.5  #: slider to tower when fully tensioned
    arm_clear: float = 1.5  #: web to the idler flange
    #: radius around the axle at the arms' front ends: the ring of material that the axle pushes;
    #: its hoop stress is across the layers when the slider prints upside down
    arm_end_r: float = 9.0
    below_axle: float = 11.0  #: DESIGN: slider underside below the axle (clears the endstop plug)
    nut_slot_extra: float = 0.0  #: extra thickness of the nut slot (0.2 printed 0.3 mm loose)
    tip_clear: float = 1.0  #: screw tip to the tunnel's end when tight
    head_side: int = 1  #: the arm (-1: -y, 1: +y) that carries the axle bolt's head
    #: DESIGN: tower plate (screw head seat), along x; just thin enough for the M3×25 screw (the
    #: next length, M3×30, would add 5 mm to the slider's wall and so to the overhang)
    plate_t: float = 11.4
    washer_od: float = 9.0  #: DESIGN: large M3 washer (DIN 9021) under the screw head
    wall_t: float = 8.0  #: DESIGN: tower's side walls (gussets and slider guides)
    wall_gap: float = 0.5  #: slider to each wall (loose: the walls carry no belt load)

    @property
    def gap_y(self) -> float:
        """Clear width between the arms: the idler plus its end play on each side."""
        return IDLER.width + 2 * self.side_play

    @property
    def arm_t(self) -> float:
        """Arm thickness: a pressed-in axle nut pocket plus the wall behind it."""
        return TOL.nut_trap_h(self.axle_m) + TOL.nut_wall

    @property
    def width(self) -> float:
        """Slider width (y)."""
        return self.gap_y + 2 * self.arm_t

    @property
    def nut_y(self) -> float:
        """Start (lowest y) of the axle nut's hex pocket, in the outer face of the nut-side arm."""
        h = TOL.nut_trap_h(self.axle_m)
        return self.width / 2 - h if self.head_side < 0 else -self.width / 2 - 1

    @property
    def nut_seat_y(self) -> float:
        """Lowest y of the axle nut seated in its pocket (the nut model's bottom face)."""
        return self.width / 2 - metric(self.axle_m).nut_h if self.head_side < 0 else -self.width / 2

    @property
    def axle_head_rot(self) -> float:
        """Rotation about x that points a bolt's shank from its head seat through the arms."""
        return 90 if self.head_side < 0 else -90

    @property
    def screw_z(self) -> float:
        """The screw runs at the axle's height."""
        return self.axle_z

    @property
    def z_bottom(self) -> float:
        """Slider underside."""
        return self.axle_z - self.below_axle

    @property
    def arm_top(self) -> float:
        """Top of the slider."""
        return self.axle_z + self.arm_end_r

    @property
    def nut_t(self) -> float:
        """Thickness of the nut slot."""
        return TOL.nut_trap_h(self.screw_m) + self.nut_slot_extra

    @property
    def screw_len(self) -> float:
        """Shortest standard screw (5 mm steps): reaches the nut at full slack."""
        need = (
            self.plate_t
            + self.stop_gap
            + self.travel
            + TOL.nut_wall
            + self.nut_t
            + 0.5  # thread beyond the nut
        )
        return float(5 * math.ceil(need / 5))

    @property
    def tip_len(self) -> float:
        """How far the screw's tip reaches past the nut's front face when tight."""
        return self.screw_len - (self.plate_t + self.stop_gap + TOL.nut_wall + self.nut_t)

    @property
    def web_t(self) -> float:
        """Slider rear wall: thrust wall, nut slot, the tunnel for the tip, a front wall."""
        return TOL.nut_wall + self.nut_t + self.tip_len + self.tip_clear + TOL.min_wall

    @property
    def tunnel_end(self) -> float:
        """End of the screw's tunnel, from the slider's rear face."""
        return self.web_t - TOL.min_wall

    @property
    def axle_x(self) -> float:
        """Axle position along the slider, from its rear face."""
        return self.web_t + IDLER.flange_d / 2 + self.arm_clear

    @property
    def length(self) -> float:
        """Slider length (x)."""
        return self.axle_x + self.arm_end_r

    @property
    def chamfer_x(self) -> float:
        """Where the arms' flat top ends and the 45° line down to the round end starts: the point
        from which the tangent to the round end (radius ``arm_end_r``) is at 45°."""
        return self.axle_x + (math.sqrt(2) - 1) * self.arm_end_r

    @property
    def rear_mid(self) -> float:
        """Slider's rear face at mid-travel in the tensioner frame (from the tower's outer face)."""
        return self.plate_t + self.stop_gap + self.travel / 2

    @property
    def axle_rel(self) -> float:
        """Idler axle at mid-travel in the tensioner frame."""
        return self.rear_mid + self.axle_x

    @property
    def slider_s0(self) -> float:
        """Slider's rear face at mid-travel, installed-frame slide coordinate."""
        return self.axle_pos - self.axle_x

    @property
    def tower_s0(self) -> float:
        """Tower's outer face (the screw head's seat), installed-frame slide coordinate."""
        return self.axle_pos - self.axle_rel

    @property
    def tower_half(self) -> float:
        """Half the tower's width across the belt line: the slider, its clearance, a wall."""
        return self.width / 2 + self.wall_gap + self.wall_t

    @property
    def tower_across(self) -> tuple[float, float]:
        """The tower's extent across the belt line (installed frame)."""
        return self.belt_pos - self.tower_half, self.belt_pos + self.tower_half

    @property
    def wall_len(self) -> float:
        """The walls' length from the tower's outer face."""
        return self.wall_end_s - self.tower_s0

    axle_len: float = 25  #: axle bolt length (M5 ISO 4762)

    @property
    def head_pocket(self) -> tuple[float, float]:
        """Radius round the axle and depth into its wall (from the wall's inner face) that the
        axle bolt's head needs, with clearance."""
        return (
            metric(self.axle_m).head_d / 2 + 0.5,
            metric(self.axle_m).head_h - self.wall_gap + 0.5,
        )

    @property
    def tip_pocket(self) -> tuple[float, float]:
        """Radius and depth that the axle bolt's tip needs in the other wall (the nut sits inside
        the arm's pocket), with clearance."""
        return self.axle_m / 2 + 0.5, max(self.axle_len - self.width - self.wall_gap, 0) + 0.5

    def sweep(self, radius: float) -> tuple[float, float]:
        """Range (tensioner frame x) that something of ``radius`` round the axle sweeps over the
        slider's travel."""
        return self.axle_rel - self.travel / 2 - radius, self.axle_rel + self.travel / 2 + radius

    @property
    def tower_top(self) -> float:
        """Top of the tower: the screw head's seat and a wall above it."""
        return self.screw_z + metric(self.screw_m).head_d / 2 + TOL.min_wall


#: The X idler (T3.22): axle on the X belt line (left bracket-local z), the tower on the bracket's
#: shelf; the walls stop short of the endstop's plug space, the foot and the rear bolt heads
X_IDLER = FloatingIdler(
    axle_z=X_BELT.pulley_axis_z - Y_AXIS.scs_top_z,
    axle_pos=X_DRIVE.idler_x,
    belt_pos=X_BELT.y,
    floor_z=BRACKET.base_t,
    wall_end_s=-23.0,
    head_side=1,  # the front arm's face is 3 mm from the bracket's beam face: no room for a head
)
#: The Y idler (T3.23): axle on the Y belt line (side frame z, baseboard top = 0), the tower on the
#: idler mount's foot; slide direction +y
Y_IDLER = FloatingIdler(
    axle_z=Y_AXIS.pulley_axis_z,
    axle_pos=Y_DRIVE.idler_y,
    belt_pos=Y_AXIS.belt_x,
    floor_z=Y_DRIVE.foot_t,
    wall_end_s=Y_DRIVE.idler_y - 2,
    travel=Y_DRIVE.idler_slot,
    head_side=1,  # as the X idler: one slider for all three (the right mount's tower is flipped)
)


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
    yield (
        CLAMP.channel_w > GT2.width
        and CLAMP.screw_dx - TOL.bolt_hole_d(3) / 2 >= CLAMP.channel_w / 2 + 0.5,
        "Belt clamp screws would cut into the belt groove",
    )
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
        "Bridge hits the wheels",
    )
    yield X_BELT.y - CLAMP.w / 2 >= BEAM.depth / 2 + 1, "X belt clamp too close to the beam"
    yield (
        BEAM.end_offset + BRACKET.recess + 1 <= CARRIAGE.end_keepout,
        "Carriage wheels hit the gantry bracket",
    )
    yield (
        X_BELT.pulley_axis_z - NEMA17.width / 2
        >= Y_AXIS.scs_top_z + BRACKET.base_t + metric(5).head_h,
        "X motor hits the rear bolt heads",
    )
    yield (
        CARRIAGE.bridge_z + CARRIAGE.bridge_h <= BEAM.bottom_z - 1,
        "Carriage bridge hits the beam",
    )
    yield (
        X_DRIVE.motor_face_y - NEMA17.shaft_len >= BEAM.depth / 2 + 1,
        "X motor shaft would hit the beam",
    )
    yield (
        X_DRIVE.motor_face_y - NEMA17.shaft_len_min <= X_DRIVE.pulley_hub_y - PULLEY.hub_len,
        "Shortest motor shaft doesn't reach the pulley hub",
    )
    xi = X_IDLER
    yield (
        abs(xi.axle_z - (X_BELT.pulley_axis_z - Y_AXIS.scs_top_z)) < 1e-6
        and xi.screw_z == xi.axle_z,
        "X idler's axle or tension screw is off the X belt line",
    )
    yield (
        xi.z_bottom >= X_ENDSTOP.plug_top_z + 0.3,
        "X idler slider dips into the endstop plug's keep-out",
    )
    yield (
        xi.tip_len + xi.tip_clear <= xi.tunnel_end - TOL.nut_wall - xi.nut_t + 1e-6,
        "X tension screw's tip doesn't fit in the slider's tunnel when tight",
    )
    yield (
        xi.axle_z - IDLER.flange_d / 2 >= xi.z_bottom + 1,
        "X idler hits the slider's underside",
    )
    yield (
        xi.axle_z - xi.z_bottom >= xi.arm_end_r + 1,
        "X slider's arms don't reach below the axle's end radius",
    )
    yield (
        xi.slider_s0 + xi.web_t <= xi.wall_end_s
        and xi.wall_end_s <= X_ENDSTOP.plug_x0 - 0.5
        and xi.wall_end_s <= X_DRIVE.foot_x0 - 0.5
        and xi.wall_end_s <= -SCS10UU.hole_pitch_x / 2 - m5.head_d / 2 - 1,
        "X idler tower's walls don't cover the slider's wall or hit the foot or the bolt heads",
    )
    yield (
        BRACKET.shelf_x <= xi.tower_s0 and BRACKET.shelf_x <= BRACKET.x_out,
        "Bracket shelf doesn't reach the X idler tower's outboard face",
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
        yd.foot_t <= Y_AXIS.scs_base_z - 0.5,
        "Pocket walls would catch the SCS blocks",
    )
    yield (
        0 < yd.pocket_end_len <= SK10.width,
        "SK10 pocket end wall must lie within the SK10's width",
    )
    yield (
        yd.front_pocket_y[1] <= yd.gantry_front_y,
        "Front pocket reaches into the gantry's travel",
    )
    yield (
        Y_AXIS.pulley_axis_z - PULLEY.flange_d / 2 >= max(yd.foot_t, WOOD_SCREW.boss_t) + 1,
        "Y pulley hits the motor foot or a screw boss",
    )
    yield (
        Y_AXIS.pulley_axis_z - NEMA17.width / 2 >= 0,
        "Y motor body would hit the baseboard",
    )
    yield (
        ye.board_x0 + ENDSTOP.thickness <= -SK10.body_w / 2 - 1,
        "Y endstop board (with its connector) hits the front SK10",
    )
    yield (
        yd.idler_y + yd.idler_slot / 2 + IDLER.flange_d / 2 + 1 <= ye.keepout_y0,
        "Y idler hits the Y endstop plug keep-out",
    )
    yield (
        ye.board_front_y + ENDSTOP.rest_protrusion <= yd.gantry_front_y - 1,
        "Y endstop lever reaches the gantry bracket",
    )
    yield (
        ye.tower_y[1] <= yd.idler_foot_y[1] and ye.tower_y[0] >= 0,
        "Y endstop tower outside the idler foot or the baseboard",
    )
    yi = Y_IDLER
    yield (
        abs(yi.axle_z - Y_AXIS.pulley_axis_z) < 1e-6 and yi.screw_z == yi.axle_z,
        "Y idler's axle or tension screw is off the Y belt line",
    )
    yield (
        yi.tip_len + yi.tip_clear <= yi.tunnel_end - TOL.nut_wall - yi.nut_t + 1e-6,
        "Y tension screw's tip doesn't fit in the slider's tunnel when tight",
    )
    yield (
        yi.axle_z - IDLER.flange_d / 2 >= yi.z_bottom + 1 and yi.z_bottom >= yd.foot_t + 1,
        "Y idler hits the slider's underside, or the slider hits the foot",
    )
    yield (
        yi.slider_s0 + yi.web_t <= yi.wall_end_s
        and yi.tower_s0 >= 3
        and yd.idler_y + yd.idler_slot / 2 + yi.arm_end_r <= ye.keepout_y0,
        "Y idler tower: the walls don't cover the slider's wall, it is off the baseboard, or "
        "the slider reaches the endstop plug's keep-out",
    )
    pen_lo, pen_hi = REQ.pen_d_range
    # --- ZRIB mount (T3.7)
    zm = ZMOUNT
    yield (
        -zm.strap_bottom_z <= 40,
        f"ZRIB mount hangs {-zm.strap_bottom_z:g} mm below the baseboard (2040 on edge: 40)",
    )
    yield (
        zm.wood_screw_u + zm.boss_d / 2 <= zm.leg_u[0] - 1
        and zm.wood_screw_u - WOOD_SCREW.head_d / 2 >= ZRIB.width / 2,
        "ZRIB mount wood screw boss hits the leg, or its head is not reachable beside the board",
    )
    yield (
        WOOD_SCREW.length - WOOD_SCREW.boss_t <= FRAME.board_size[2] - 2,
        "ZRIB mount wood screws would reach through the baseboard",
    )
    yield (
        WOOD_SCREW.boss_t > zm.rail_t and -zm.board_z - WOOD_SCREW.boss_t >= 1,
        "ZRIB mount boss hits the board",
    )
    # --- PSU mount (T3.31)
    pm = PSU_MOUNT
    table_z = -FRAME.board_size[2] - BASEBOARD.runner_h
    yield (
        3 <= pm.psu_screw_depth <= PSU.max_screw_depth
        and 2.5 <= pm.hood_screw_depth <= PSU.max_screw_depth,
        f"PSU screws enter the case {pm.psu_screw_depth:g} (bracket) and "
        f"{pm.hood_screw_depth:g} mm (hood): too shallow to hold, or deeper than "
        f"{PSU.max_screw_depth:g}",
    )
    yield (
        pm.low_z - pm.clearance - pm.wall_t - table_z >= 5,
        "The PSU's hood hangs less than 5 mm above the table",
    )
    yield (
        PSU.bottom_hole_x[1] + pm.counterbore[0] / 2 <= pm.board_x[1]
        and pm.board_x[0] > PSU.bottom_hole_x[0] + pm.counterbore[0] / 2,
        "PSU bracket: the lower M4's counterbore runs into the flange, or the upper one is not "
        "above the board",
    )
    yield (
        pm.origin[0] + pm.edge_z - pm.flange_reach > BASEBOARD.runner_x[1] + 5
        and all(
            math.hypot(x - LOOM.hole_x, y - LOOM.hole_y)
            >= (LOOM.hole_d + WOOD_SCREW.boss_d) / 2 + 2
            for x, y in pm.pilot_xy
        ),
        "PSU bracket flange reaches a runner, or a wood screw lands on the loom hole",
    )
    yield (
        pm.origin[0] + pm.brace_z - (LOOM.hole_x + LOOM.d / 2) >= 1.5,
        "PSU bracket: the brace over the board's top comes within 1.5 mm of the Y loom",
    )
    cl, cs = C14_INLET.cutout  # long side along x, short along y
    flange_l, flange_w = C14_INLET.flange  # across the flats (x), across the points (y)
    ox0, ix0, ix1, ox1 = pm.hood_x
    yield (
        ix0 + 0.5 <= pm.inlet_x - cl / 2
        and pm.inlet_x + cl / 2 <= ix1 - 0.5
        and -pm.depth + pm.wall_t + 0.5 <= pm.inlet_y - cs / 2
        and pm.inlet_y + cs / 2 <= -0.5,
        "PSU hood: the inlet's cutout is not inside the hood in front of the PSU",
    )
    yield (
        ox0 <= pm.inlet_x - flange_l / 2
        and pm.inlet_x + flange_l / 2 <= ox1
        and -pm.depth <= pm.inlet_y - flange_w / 2
        and pm.inlet_y + flange_w / 2 <= pm.sleeve_fan,
        "PSU hood: the inlet's flange runs off the outer wall",
    )
    pocket_x, pocket_y = pm.xt60_pocket
    window_x, window_y = pm.xt60_window
    xt_x0 = pm.xt60_x - pocket_x / 2 - pm.wall_t
    xt_x1 = pm.xt60_x + pocket_x / 2 + pm.wall_t
    xt_y0 = pm.xt60_y - pocket_y / 2 - pm.wall_t - pm.xt60_sleeve
    xt_y1 = pm.xt60_y + pocket_y / 2 + pm.xt60_pocket_relief + pm.wall_t
    yield (
        pm.inlet_x + cl / 2 + 2 <= xt_x0,
        "PSU hood: the inlet is over the XT60, which reaches far into the hood",
    )
    yield (
        ix0 <= xt_x0
        and xt_x1 <= ix1
        and -pm.depth + pm.wall_t <= xt_y0
        and xt_y1 <= -(PSU.crimp_reach + 2),
        "PSU hood: the XT60's sleeve runs into a wall or the wire lugs",
    )
    yield (
        (XT60.collar[0] - window_y) / 2 - pm.xt60_window_relief >= 0.4
        and (XT60.collar[1] - window_x) / 2 >= 0.5
        and pm.xt60_sleeve > 0
        and pm.xt60_grip <= XT60.collar_len - 0.5,
        "PSU hood: the XT60's collar does not stop on the lip, or the pocket reaches its rim",
    )
    yield (
        pm.xt60_x - XT60.front[1] / 2 - pm.xt60_plug_margin >= pm.board_x[1] + 2
        and pm.low_z - pm.clearance - pm.wall_t - table_z >= 0,  # the plug clears the table
        "PSU hood: the XT60's plug would hit the board's underside",
    )
    yield (
        pm.sleeve_bottom <= PSU.hole_y[0] - pm.bracket_w / 2 - 1
        and PSU.hole_y[0] + 5 <= pm.sleeve_side < PSU.selector_y[0]
        and pm.sleeve_fan >= PSU.cover_setback + 3,
        "PSU hood sleeves: one reaches a bracket or the 115/230 V selector, misses the M4 "
        "holes, or leaves the open strip in front of the cover",
    )
    # --- baseboard layout (T3.7)
    bb = BASEBOARD
    bx, by, _ = FRAME.board_size
    yield (
        bb.runner_x[0] >= 0
        and bb.runner_x[1] <= bx
        and bb.runner_y[0] - bb.runner_w / 2 >= 0
        and bb.runner_y[2] + bb.runner_w / 2 <= by,
        "A runner hangs over the baseboard edge",
    )
    zrib_half_v = abs(zm.plate_v[0])
    yield (
        bb.runner_pitch / 2 - bb.runner_w / 2 - zrib_half_v >= 5
        and bb.zrib_center[0] + zm.leg_u[1] <= bx,
        "The ZRIB mount does not fit between the runners or on the baseboard",
    )
    zx0, zx1 = bb.zrib_center[0] - zm.leg_u[1], bb.zrib_center[0] + zm.leg_u[1]
    zy0, zy1 = bb.zrib_center[1] - zrib_half_v, bb.zrib_center[1] + zrib_half_v
    head_r = m5.washer_od / 2 + 2  #: bolt head and washer under the board, plus room
    yield (
        all(abs(y - ry) >= bb.runner_w / 2 + head_r for _, y in bb.post_xy for ry in bb.runner_y),
        "A bed post bolt head sits under a runner",
    )
    yield (
        not any(
            zx0 - head_r < x < zx1 + head_r and zy0 - head_r < y < zy1 + head_r
            for x, y in bb.post_xy
        ),
        "A bed post bolt head hits the ZRIB mount",
    )
    yield (
        FRAME.steel_margin >= bb.post_inset + m5.washer_od / 2 + 1
        and bb.post_inset >= m5.washer_od / 2 + 3,
        "The bed post nuts hit the steel sheet or hang over the panel edge",
    )
    yield (
        FRAME.steel_size[0] >= REQ.media_a3[0] and FRAME.steel_size[1] >= REQ.media_a3[1],
        "The steel sheet is smaller than A3",
    )
    yield (
        bb.post_stud_z + bb.post_bolt_len >= bb.nut_top_z + 1
        and FRAME.bed_adjust_gap - bb.post_adjust >= 1
        and bb.spring_len >= FRAME.bed_adjust_gap + bb.post_adjust
        and bb.spring_id >= m5.m + 0.5,
        "Bed post: stud too short, panel too low, or spring too short at the highest setting",
    )
    yield (
        bb.nut_top_z + 1 <= CARRIAGE.bottom_z,
        "Bed post nuts reach into the carriage's path",
    )
    pen_x_lo = CARRIAGE.center_x_range[0] + PEN.pen_x
    pen_x_hi = CARRIAGE.center_x_range[1] + PEN.pen_x
    pen_y_lo = Y_AXIS.gantry_y_range[0] + CARRIAGE.plate_front_y - PEN.pen_axis_d(pen_hi)
    pen_y_hi = Y_AXIS.gantry_y_range[1] + CARRIAGE.plate_front_y - PEN.pen_axis_d(pen_lo)
    a3_x, a3_y = REQ.media_a3
    yield (
        pen_x_lo <= (bx - a3_x) / 2 and pen_x_hi >= (bx + a3_x) / 2,
        f"The pen cannot reach all of A3 along X ({pen_x_lo:g}…{pen_x_hi:g})",
    )
    yield (
        pen_y_lo <= (by - a3_y) / 2 and pen_y_hi >= (by + a3_y) / 2,
        f"The pen cannot reach all of A3 along Y ({pen_y_lo:g}…{pen_y_hi:g})",
    )
    # --- Y loom (T3.8)
    lm = LOOM
    yield lm.fold_width >= 2 * lm.bend_r, "The loom fold is tighter than the loom's bend radius"
    yield (
        lm.moving_x - lm.d / 2 >= lm.rail_x + 1
        and bx - (lm.hole_x + max(lm.d, lm.hole_d) / 2) >= 3,
        "The loom legs don't fit between the rail and the baseboard edge",
    )
    yield (
        lm.rail_starts[-1] + lm.rail_len <= Y_DRIVE.motor_plate_y[0] - 3
        and lm.apex_y + lm.d / 2 + 1 <= Y_DRIVE.motor_plate_y[0],
        "The loom fold or its rails reach the right Y motor mount",
    )
    yield (
        Y_AXIS.pulley_axis_z - PULLEY.pd / 2 - GT2.pitch_line_from_back >= WOOD_SCREW.boss_t + 1,
        "The Y belt's lower run hits a loom rail foot's screw boss",
    )
    yield (
        BRACKET.face_y[1] < lm.anchor_y[0]
        and lm.anchor_y[1] <= BRACKET.len_y / 2 - CLAMP.length
        and lm.anchor_x[0] >= BRACKET.x_out,
        "The loom anchor block is not within the free area of the bracket's base",
    )
    # --- pen holder (T3.6)
    pn = PEN
    yield pn.lift >= REQ.pen_lift_min, "Pen lift stroke below the requirement"
    yield pn.float_travel >= REQ.pen_float_min, "Pen float below the requirement"
    yield (
        pn.pen_axis_d(pen_hi) <= REQ.pen_axis_max_offset,
        f"Largest pen axis {pn.pen_axis_d(pen_hi):g} mm from the carriage face",
    )
    yield (
        pn.pen_x + pn.block_half_w <= TOOL_PLATE.w / 2 and pn.wall_x[0] >= -TOOL_PLATE.w / 2,
        "Pen holder wider than the tool plate",
    )
    yield (
        pn.lower_arm_bottom >= TOOL_PLATE.bottom_z,
        "Lower rod arm below the carriage bottom (media clearance)",
    )
    for pen_d in (pen_lo, pen_hi):
        reach = math.hypot(pn.pen_x - pn.rod_x, pn.pen_axis_d(pen_d) - pn.rod_d_pos)
        yield (
            reach >= max(pn.sleeve_od, pn.arm_w) / 2 + pen_d / 2 + 0.3,
            f"A {pen_d:g} mm pen hits the rod sleeve or arm",
        )
    yield pn.yoke_in >= pen_hi / 2 + 1, "Yoke arms too close to the largest pen"
    yield (
        pn.servo_x + FT90M.horn_len <= pn.rod_x - pn.sleeve_od / 2 + 0.3,
        "Servo horn tip reaches the pen slide column",
    )
    yield pn.horn_swing_deg <= 40, "Pen-lift linkage needs too large a horn swing"
    groove = (pn.key_x - TOL.slide_d(pn.key_w) / 2, pn.key_x + TOL.slide_d(pn.key_w) / 2)
    yield (
        groove[0] - pn.lug_x0 >= TOL.min_wall and pn.slot_x[0] - groove[1] >= 1.5,
        "Key groove too close to the lug edge or the pin slot",
    )


def check_design() -> None:
    """Raise :class:`cadder.checks.DesignError` listing every failed design rule."""
    run_design_checks(design_checks())


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
            f"X belt: center y {fmt(X_BELT.y)} behind beam center, back of lower run z "
            f"{fmt(X_BELT.back_z)}, motor/idler axis z {fmt(X_BELT.pulley_axis_z)}",
            f"Y belt: back of lower run z {fmt(Y_AXIS.belt_back_z)}, pulley/idler axis z "
            f"{fmt(Y_AXIS.pulley_axis_z)}, belt center {fmt(-Y_AXIS.belt_x)} "
            "outboard of each shaft",
            f"Y drive: idler axle y {fmt(Y_DRIVE.idler_y)} (slot ±{fmt(Y_DRIVE.idler_slot / 2)}), "
            f"motor axis y {fmt(Y_DRIVE.motor_y)}; endstop board front y "
            f"{fmt(Y_ENDSTOP.board_front_y)}, trigger tip y {fmt(Y_ENDSTOP.trigger_tip_y)} at the "
            f"end of travel (X: board front x {fmt(X_ENDSTOP.board_front_x)}, head x "
            f"{fmt(X_ENDSTOP.head_x_min)})",
        ]
    )
