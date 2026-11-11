"""Spacer between the X idler and its mount plate (README §8 T3.4). Print ×1.

Purpose: holds the X idler on the belt line. Slides on the M5 axle; bears on the
idler's inner bearing ring. Length = ``X_DRIVE.idler_spacer_len``.
Hardware: none. Print: PETG or PLA; 0.2 mm; 100 % infill; upright; no supports.
Alternative: stack M5 nuts and washers to the same length.
"""

from pythonscad import cylinder

from plotter_cad.geometry import FN_HOLE
from plotter_cad.params import TOL, X_DRIVE

OUTER_D = 8  #: bears on the idler's inner ring


def x_idler_spacer():
    length = X_DRIVE.idler_spacer_len
    body = cylinder(d=OUTER_D, h=length, fn=48)
    bore = cylinder(d=TOL.bolt_hole_d(5), h=length + 2, fn=FN_HOLE).translate([0, 0, -1])
    return body - bore
