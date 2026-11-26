"""PSU bracket: hangs the 24 V supply beside the baseboard's right edge (T3.31, D38). Print ×2.

Purpose: one of two identical L-shaped brackets, one on each line of the PSU's M4 holes
(y = 32 and 182). The upright sits between the PSU's bottom face and the board's edge and takes
two M4 into the PSU; the flange runs in under the board and takes two wood screws up into it.
Above the board the upright grows 4 mm inward and rests on the board's top (a brace: the board's
edge is clamped between it and the flange), and a 1 mm fillet fills the upright/flange corner;
the board's underside edge is eased 1 mm × 45° on the right side to make room for it (T3.31).
The PSU hangs from the board, clear of the table, with its fan face out in free air.

  section along the hole line (PSU frame: x down the PSU, z out of the bottom face)

        z = -15   z = 0
      ▒▒▒▒▒▒▒▒▒▒▒▒│ ░░░░░░░   x = 23.5   upright top
      ▒▒▒▒▒ ◎═══════░ PSU     M4 (head in a counterbore on the board side)
  ════▒▒▒▒▒▒▒▒▒▒▒▒│ ░░░░░░░   board top (x = 69): the brace rests on it
  ═ board ▒ ◎═══════░         lower M4, in front of the board's edge
  ════════▒▒▒▒▒▒▒▒│ ░░░░░░░   board underside (x = 87)
  ▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒│ ░░░░░░░   flange: 2 wood screws up into the board (x = 87..96)

Frame: the PSU frame (``hardware/psu.py``), the bracket centered on y = 0; place it on a hole
line with ``translate([0, y, 0])``. :func:`psu_bracket_installed` returns it there;
:func:`psu_bracket` in print orientation (lying on its side).

Hardware per bracket:
  2 × M4×15 ISO 4762 into the PSU's bottom face (they enter the case 4.4 mm; fit them before
      the bracket goes on the board: the lower head faces the board's edge)
  2 × 4×25 countersunk wood screws up into the baseboard (pilot holes in the drilling layout)

Print: default profile (``profiles/default.toml``); on its side (the L flat on the bed), so the
bending stresses run along the layers; no supports (the holes are teardrops).

FEM: the PSU's weight (sustained) and an abuse case (pushed down and pulled out) act on the
upright's PSU face; held by the two wood screws and the board's underside at the flange's inner
end (the PSU pries the bracket about it). The board's edge and top hold nothing: the upright and
the brace lift away from them (FEM, T3.31); the brace still stiffens the upright. Limits: 0.5 mm
at the PSU face under its weight, 1 mm when leant on (agreed with the user).
"""

from typing import TYPE_CHECKING

from cadder.geometry import FN_HOLE, box, teardrop
from cadder.handles import handle, set_handles
from cadder.part import DisplacementLimit, FemSpec, LoadCase, Moment, PrintedPart, Support
from cadder.part import Force as FemForce
from cadder.regions import BOND_RADIUS, Box, Cylinder
from cadder.types import Matrix
from pythonscad import circle, cylinder, linear_extrude, square

from plotzker.hardware import PSU
from plotzker.materials import DEFAULT_MATERIAL, DEFAULT_PRINT
from plotzker.params import PSU_MOUNT, TOL, WOOD_SCREW

if TYPE_CHECKING:
    from pythonscad import Solid

G = 9.81
#: the printed hood and the XT60 add to the supply's weight (ASSUMED; the inlet is weighed
#: with the PSU)
HOOD_MASS_KG = 0.08
#: distance of the PSU's center of mass from its bottom face (half its height)
CG_Z = PSU.size[2] / 2


def _hole_x(d: float, x0: float, x1: float, z: float) -> Solid:
    """Hole along x from ``x0`` to ``x1`` at (y = 0, z): teardrop pointing +y (up in print)."""
    return linear_extrude(teardrop(d), height=x1 - x0).rotate([0, 90, 0]).translate([x0, 0, z])


def _hole_z(d: float, x: float, z0: float, z1: float) -> Solid:
    """Hole along z from ``z0`` to ``z1`` at (x, y = 0): teardrop pointing +y."""
    return linear_extrude(teardrop(d), height=z1 - z0).translate([x, 0, z0])


def _corner_fillet() -> Solid:
    """Fillet in the corner between the upright and the flange (the board's eased edge sits in
    it), as a solid along y."""
    r, x0, z0 = PSU_MOUNT.corner_r, PSU_MOUNT.board_x[1], PSU_MOUNT.edge_z
    profile = square([r, r]).translate([x0 - r, z0 - r]) - circle(r=r, fn=FN_HOLE).translate([x0 - r, z0 - r])
    w = PSU_MOUNT.bracket_w
    return linear_extrude(profile, height=w).rotate([90, 0, 0]).translate([0, w / 2, 0])


def _handles() -> dict[str, Matrix | list[Matrix]]:
    """Fastener handles (PSU frame, bracket at y = 0)."""
    return {
        #: M4 heads on the counterbore floors, shanks toward +z (into the PSU)
        "psu_screws": [
            handle([x, 0, PSU_MOUNT.edge_z + PSU_MOUNT.counterbore[1]], [180, 0, 0]) for x in PSU.bottom_hole_x
        ],
        #: wood screw heads flush with the flange's underside, shanks toward -x (up)
        "wood_screws": [handle([PSU_MOUNT.upright_x[1], 0, z], [0, 90, 0]) for z in PSU_MOUNT.wood_screw_z],
    }


def psu_bracket_installed() -> Solid:
    """The bracket in the PSU frame, centered on y = 0."""
    w = PSU_MOUNT.bracket_w
    x_top, x_bot = PSU_MOUNT.upright_x
    flange_x0 = PSU_MOUNT.board_x[1]
    upright = box(x_top, -w / 2, PSU_MOUNT.edge_z, x_bot, w / 2, 0)
    flange = box(flange_x0, -w / 2, PSU_MOUNT.edge_z - PSU_MOUNT.flange_reach, x_bot, w / 2, PSU_MOUNT.edge_z)
    # above the board the upright grows inward and rests on the board's top
    brace = box(x_top, -w / 2, PSU_MOUNT.brace_z, PSU_MOUNT.board_x[0], w / 2, PSU_MOUNT.edge_z)
    body = upright | flange | brace | _corner_fillet()
    cb_d, cb_h = PSU_MOUNT.counterbore
    for x in PSU.bottom_hole_x:
        body = body - _hole_z(TOL.bolt_hole_d(PSU.hole_m), x, PSU_MOUNT.edge_z - 1, 1)
        body = body - _hole_z(cb_d, x, PSU_MOUNT.edge_z - 1, PSU_MOUNT.edge_z + cb_h)
    for z in PSU_MOUNT.wood_screw_z:
        body = body - _hole_x(WOOD_SCREW.hole_d, flange_x0 - 1, x_bot + 1, z)
        # 90° countersink, wide end on the flange's underside (x = x_bot)
        body = body - cylinder(d1=WOOD_SCREW.hole_d, d2=WOOD_SCREW.sink_d, h=WOOD_SCREW.sink_h, fn=FN_HOLE).rotate(
            [0, 90, 0]
        ).translate([x_bot - WOOD_SCREW.sink_h, 0, z])
        body = body - cylinder(d=WOOD_SCREW.sink_d, h=1, fn=FN_HOLE).rotate([0, 90, 0]).translate([x_bot, 0, z])
    return set_handles(body, **_handles())


def psu_bracket() -> Solid:
    """The bracket in print orientation: on its side, the L flat on the bed."""
    return psu_bracket_installed().rotate([90, 0, 0]).translate([0, 0, PSU_MOUNT.bracket_w / 2])


# --- FEM (PSU frame, bracket at y = 0)

_M = PSU_MOUNT
_W = _M.bracket_w
PSU_FACE = Box(lo=(_M.upright_x[0], -_W / 2, -0.3), hi=(_M.upright_x[1], _W / 2, 0.3), facing=(0, 0, 1))
#: The PSU hangs outboard, so the bracket pries about the flange's inner end: the board can only
#: push there (the upright pulls away from the board's edge, which holds nothing)
PRY_STRIP = 8
BOARD_UNDERSIDE = Box(
    lo=(_M.board_x[1] - 0.3, -_W / 2, _M.edge_z - _M.flange_reach),
    hi=(_M.board_x[1] + 0.3, _W / 2, _M.edge_z - _M.flange_reach + PRY_STRIP),
    facing=(-1, 0, 0),
)
SCREW_SEATS = [
    Cylinder(
        center=(_M.upright_x[1] - WOOD_SCREW.sink_h / 2, 0, z),
        axis=(1, 0, 0),
        radius=WOOD_SCREW.sink_d / 2,
        inner_radius=WOOD_SCREW.hole_d / 2,
        half_length=WOOD_SCREW.sink_h / 2 + 0.3,
        facing=(1, 0, 0),
        facing_tol_deg=60,
    )
    for z in _M.wood_screw_z
]
#: Friction round each wood screw: the flange is clamped to the board's underside
BOND_ZONES = [Cylinder((_M.board_x[1], 0, z), (1, 0, 0), BOND_RADIUS, 0.3, facing=(-1, 0, 0)) for z in _M.wood_screw_z]

#: Each bracket carries half the PSU and hood; x is down (machine -z)
_WEIGHT_N = (PSU.mass_kg + HOOD_MASS_KG) * G / 2
#: ASSUMED abuse: someone leans on the PSU (50 N down) and yanks a cable (30 N out), shared
_PUSH_N = 50 / 2
_PULL_N = 30 / 2


def _hang(down: float, out: float) -> tuple[FemForce | Moment, ...]:
    """The PSU's share on the upright: the forces, and the couple of the downward force acting
    at the PSU's center of mass (half the PSU's height out from the face)."""
    return (
        FemForce(PSU_FACE, (down, 0, out)),
        Moment(PSU_FACE, (0, CG_Z * down, 0)),
    )


PART = PrintedPart(
    name="psu_bracket",
    description="PSU bracket: hangs the supply beside the board's right edge (×2)",
    build=psu_bracket,
    analysis=psu_bracket_installed,
    frame="installed",
    build_direction=(0, 1, 0),
    profile=DEFAULT_PRINT,
    material=DEFAULT_MATERIAL,
    fem=FemSpec(
        load_cases=(
            LoadCase(
                "weight",
                "Half the PSU and hood hang on the upright, out from its face (sustained)",
                _hang(_WEIGHT_N, 0),
                "hardware.PSU.mass_kg (0.77 kg weighed, with the inlet) + HOOD_MASS_KG (ASSUMED)",
                sustained=True,
            ),
            LoadCase(
                "abuse",
                "The PSU is pushed down (50 N) and a cable pulls it out (30 N), shared",
                (*_hang(_WEIGHT_N + _PUSH_N, _PULL_N),),
                "ASSUMED handling loads",
            ),
        ),
        supports=(
            Support("wood_screw_inner", SCREW_SEATS[1], "Inner wood screw: countersink, fixed"),
            Support("wood_screw_outer", SCREW_SEATS[0], "Outer wood screw: countersink, fixed"),
            Support(
                "board_underside",
                BOARD_UNDERSIDE,
                "Flange's inner end bearing on the board's underside (the pivot of the pry): held in x (machine z)",
                constrain=(True, False, False),
            ),
            Support("screw_zone_inner", BOND_ZONES[1], "Friction round the inner screw: bonded"),
            Support("screw_zone_outer", BOND_ZONES[0], "Friction round the outer screw: bonded"),
        ),
        displacement_limits=(
            # the PSU only has to stay put: half a millimeter is invisible
            DisplacementLimit("psu_face", PSU_FACE, 0.5, load_cases=("weight",)),
            # leant on, it may give a little more and spring back (agreed with the user, T3.31)
            DisplacementLimit("psu_face_abuse", PSU_FACE, 1.0, load_cases=("abuse",)),
        ),
        default_displacement_limit_mm=None,
    ),
)
