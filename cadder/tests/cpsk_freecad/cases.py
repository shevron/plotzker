"""FreeCAD sketch cases, one or more per constraint form of the CPSK plugin plan (§4.2).

Checked in phase 0 (cadder/docs/cpsk/freecad-conventions.md); the corpus for the plugin's
tests. Plain data, readable by FreeCAD's Python 3.11 and by cadder.
Geometry: ("point", x, y), ("line", x1, y1, x2, y2), ("circle", cx, cy, r),
("arc", cx, cy, r, start_deg, end_deg), optionally with "block" appended to fix it.
Constraints: (type, args, value, driving) in FreeCAD's form; GeoId -1 = H axis, -2 = V axis,
root point = (-1, 1). PosId: 0 edge, 1 start (point: itself), 2 end, 3 center.
Values: lengths in mm, angles in degrees. Seeds are deliberately off the solution.
"""

C: list[dict] = []


def case(name, geometry, constraints, note=""):
    C.append({"name": name, "geometry": geometry, "constraints": constraints, "note": note})


# ----- points -----
case(
    "coincident",
    [("point", 2, 3, "block"), ("point", 2.4, 2.7)],
    [("Coincident", [1, 1, 0, 1], None, True)],
)
case(
    "point_on_line_extension",
    [("line", 0, 0, 10, 5, "block"), ("point", -3, -1)],
    [("PointOnObject", [1, 1, 0], None, True), ("DistanceX", [1, 1], -4, True)],
    "point on the line's extension; DistanceX of a single point is its x",
)
case(
    "point_on_circle",
    [("circle", 0, 0, 5, "block"), ("point", 3, 3.5)],
    [("PointOnObject", [1, 1, 0], None, True), ("DistanceX", [1, 1], 3, True)],
)
case(
    "point_on_arc_outside_sweep",
    [("arc", 0, 0, 5, 0, 90, "block"), ("point", 4, -3.3)],
    [("PointOnObject", [1, 1, 0], None, True), ("DistanceX", [1, 1], 4, True)],
    "is point-on-arc the full circle?",
)
case(
    "distance_y_point_negative",
    [("point", 1, -2.5)],
    [("DistanceX", [0, 1], 1, True), ("DistanceY", [0, 1], -3, True)],
)

# ----- lines -----
case(
    "horizontal_line",
    [("point", 1, 2, "block"), ("line", 1.2, 2.1, 9, 3)],
    [
        ("Coincident", [1, 1, 0, 1], None, True),
        ("Horizontal", [1], None, True),
        ("Distance", [1], 7, True),
    ],
)
case(
    "horizontal_points",
    [("point", 1, 2, "block"), ("point", 5, 3)],
    [("Horizontal", [0, 1, 1, 1], None, True), ("DistanceX", [1, 1], 5, True)],
)
case(
    "vertical_line",
    [("point", 1, 2, "block"), ("line", 1.2, 2.1, 2, 9)],
    [
        ("Coincident", [1, 1, 0, 1], None, True),
        ("Vertical", [1], None, True),
        ("Distance", [1], 7, True),
    ],
)
case(
    "vertical_points",
    [("point", 1, 2, "block"), ("point", 2, 5)],
    [("Vertical", [0, 1, 1, 1], None, True), ("DistanceY", [1, 1], 5, True)],
)
case(
    "parallel",
    [("line", 0, 0, 10, 2, "block"), ("point", 0, 5, "block"), ("line", 0.2, 5.1, 4, 7)],
    [
        ("Coincident", [2, 1, 1, 1], None, True),
        ("Parallel", [0, 2], None, True),
        ("Distance", [2], 5, True),
    ],
)
case(
    "perpendicular",
    [("line", 0, 0, 10, 2, "block"), ("point", 0, 5, "block"), ("line", 0.2, 5.1, -1, 9)],
    [
        ("Coincident", [2, 1, 1, 1], None, True),
        ("Perpendicular", [0, 2], None, True),
        ("Distance", [2], 5, True),
    ],
)
case(
    "equal_lines",
    [("line", 0, 0, 10, 0, "block"), ("point", 0, 5, "block"), ("line", 0.2, 5.1, 6, 5.5)],
    [
        ("Coincident", [2, 1, 1, 1], None, True),
        ("Horizontal", [2], None, True),
        ("Equal", [0, 2], None, True),
    ],
)
case(
    "distance_points",
    [("point", 0, 0, "block"), ("point", 3.3, 3.5)],
    [("DistanceY", [1, 1], 4, True), ("Distance", [0, 1, 1, 1], 5, True)],
)
case(
    "distance_point_line_below",
    [("line", 0, 0, 10, 0, "block"), ("point", 3, -2.5)],
    [("DistanceX", [1, 1], 3, True), ("Distance", [1, 1, 0], 2, True)],
    "unsigned: the seed below the line stays below",
)
case(
    "distance_x_line_positive",
    [("point", 1, 1, "block"), ("line", 1.1, 0.9, 4, 1.5)],
    [
        ("Coincident", [1, 1, 0, 1], None, True),
        ("Horizontal", [1], None, True),
        ("DistanceX", [1], 4, True),
    ],
)
case(
    "distance_x_line_negative",
    [("point", 1, 1, "block"), ("line", 1.1, 0.9, -2, 1.5)],
    [
        ("Coincident", [1, 1, 0, 1], None, True),
        ("Horizontal", [1], None, True),
        ("DistanceX", [1], -4, True),
    ],
    "signed: end.x - start.x = -4?",
)
case(
    "distance_x_points_negative",
    [("point", 5, 1, "block"), ("point", 2.5, 1.2)],
    [("Horizontal", [0, 1, 1, 1], None, True), ("DistanceX", [0, 1, 1, 1], -2, True)],
    "signed: b.x - a.x = -2?",
)
case(
    "distance_y_points",
    [("point", 5, 1, "block"), ("point", 5.2, 3.5)],
    [("Vertical", [0, 1, 1, 1], None, True), ("DistanceY", [0, 1, 1, 1], 3, True)],
)
case(
    "angle_line_30",
    [("line", 0.1, -0.1, 8, 4)],
    [
        ("Coincident", [0, 1, -1, 1], None, True),
        ("Angle", [0], 30, True),
        ("Distance", [0], 10, True),
    ],
)
case(
    "angle_line_minus_30",
    [("line", 0.1, -0.1, 8, -4)],
    [
        ("Coincident", [0, 1, -1, 1], None, True),
        ("Angle", [0], -30, True),
        ("Distance", [0], 10, True),
    ],
)
case(
    "angle_line_150",
    [("line", 0.1, -0.1, -8, 4)],
    [
        ("Coincident", [0, 1, -1, 1], None, True),
        ("Angle", [0], 150, True),
        ("Distance", [0], 10, True),
    ],
)
case(
    "angle_lines",
    [("line", 0, 0, 10, 0, "block"), ("line", 0.1, 0.1, 8, 4)],
    [
        ("Coincident", [1, 1, 0, 1], None, True),
        ("Angle", [0, 1], 30, True),
        ("Distance", [1], 10, True),
    ],
)
case(
    "angle_lines_reversed_first",
    [("line", 10, 0, 0, 0, "block"), ("line", 0.1, 0.1, -8, -4)],
    [
        ("Coincident", [1, 1, 0, 2], None, True),
        ("Angle", [0, 1], 30, True),
        ("Distance", [1], 10, True),
    ],
    "first line points -x: is the angle measured from its direction?",
)
case(
    "angle_lines_negative",
    [("line", 0, 0, 10, 0, "block"), ("line", 0.1, 0.1, 8, -4)],
    [
        ("Coincident", [1, 1, 0, 1], None, True),
        ("Angle", [0, 1], -30, True),
        ("Distance", [1], 10, True),
    ],
)

# ----- circles and arcs -----
case(
    "radius_circle",
    [("point", 1, 1, "block"), ("circle", 1.2, 0.9, 2)],
    [("Coincident", [1, 3, 0, 1], None, True), ("Radius", [1], 3, True)],
)
case(
    "diameter_arc",
    [("point", 1, 1, "block"), ("arc", 1.2, 0.9, 2, 10, 100)],
    [
        ("Coincident", [1, 3, 0, 1], None, True),
        ("Diameter", [1], 6, True),
        ("Angle", [1], 90, True),
        ("Horizontal", [1, 3, 1, 1], None, True),
    ],
)
case(
    "arc_sweep",
    [("point", 0, 0, "block"), ("point", 5, 0, "block"), ("arc", 0.1, 0.1, 5.2, 5, 70)],
    [
        ("Coincident", [2, 3, 0, 1], None, True),
        ("Coincident", [2, 1, 1, 1], None, True),
        ("Angle", [2], 60, True),
    ],
)
case(
    "equal_circle_arc",
    [
        ("circle", 0, 0, 4, "block"),
        ("point", 10, 0, "block"),
        (
            "arc",
            10.1,
            0.1,
            3,
            0,
            90,
        ),
    ],
    [
        ("Coincident", [2, 3, 1, 1], None, True),
        ("Equal", [0, 2], None, True),
        ("Angle", [2], 90, True),
        ("Horizontal", [2, 3, 2, 1], None, True),
    ],
)
case(
    "tangent_line_circle",
    [("circle", 0, 0, 3, "block"), ("line", -5, 3.4, 5, 3.2)],
    [
        ("Horizontal", [1], None, True),
        ("Tangent", [1, 0], None, True),
        ("DistanceX", [1, 1], -5, True),
        ("DistanceX", [1, 2], 5, True),
    ],
)
case(
    "tangent_line_arc",
    [("arc", 0, 0, 3, 0, 180, "block"), ("line", -5, 3.4, 5, 3.2)],
    [
        ("Horizontal", [1], None, True),
        ("Tangent", [1, 0], None, True),
        ("DistanceX", [1, 1], -5, True),
        ("DistanceX", [1, 2], 5, True),
    ],
)
case(
    "tangent_circles",
    [("circle", 0, 0, 3, "block"), ("circle", 4.6, 0.2, 2)],
    [
        ("PointOnObject", [1, 3, -1], None, True),
        ("Radius", [1], 2, True),
        ("Tangent", [0, 1], None, True),
    ],
    "external tangency from the seed (center 5)",
)
case(
    "tangent_circles_internal",
    [("circle", 0, 0, 3, "block"), ("circle", 1.2, 0.2, 2)],
    [
        ("PointOnObject", [1, 3, -1], None, True),
        ("Radius", [1], 2, True),
        ("Tangent", [0, 1], None, True),
    ],
    "internal tangency from the seed (center 1)",
)
case(
    "tangent_endpoints_line_arc",
    [("line", 0, 0, 10, 0, "block"), ("arc", 10.2, 3.2, 3.1, -85, 20)],
    [("Tangent", [0, 2, 1, 1], None, True), ("Radius", [1], 3, True), ("Angle", [1], 90, True)],
)
case(
    "tangent_endpoints_arc_line_reverse",
    [("line", 0, 0, 10, 0, "block"), ("arc", 10.2, -3.2, 3.1, 85, 175)],
    [("Tangent", [0, 2, 1, 2], None, True), ("Radius", [1], 3, True), ("Angle", [1], 90, True)],
    "joint at the arc's end; arc below the line",
)

# ----- symmetric, block, measured -----
case(
    "symmetric_line",
    [("line", 0, 0, 10, 10, "block"), ("point", 2, 6, "block"), ("point", 5, 3)],
    [("Symmetric", [1, 1, 2, 1, 0], None, True)],
)
case(
    "symmetric_point",
    [("point", 1, 1, "block"), ("point", 3, 2, "block"), ("point", 4.5, 3.3)],
    [("Symmetric", [0, 1, 2, 1, 1, 1], None, True)],
)
case(
    "symmetric_line_ends_about_point",
    [("point", 3, 2, "block"), ("line", 0.5, 0.2, 5.3, 4)],
    [
        ("Symmetric", [1, 1, 1, 2, 0, 1], None, True),
        ("Horizontal", [1], None, True),
        ("Distance", [1], 6, True),
    ],
)
case(
    "measured_distance",
    [("line", 0, 0, 3, 4, "block")],
    [("Distance", [0], None, False)],
    "reference (non-driving) value",
)
case(
    "lock_point",
    [("point", 3.5, -1.5)],
    [("DistanceX", [0, 1], 3, True), ("DistanceY", [0, 1], -2, True)],
    "FreeCAD Lock",
)
