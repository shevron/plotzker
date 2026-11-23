"""Export cases for the CPSK FreeCAD plugin, beyond the constraint forms in ``cases.py``.

Plain data, readable by FreeCAD's Python 3.11 and by cadder. Same format as ``cases.py``, plus:

- a constraint tuple may have a fifth item, a dict with ``name``, ``expression`` (FreeCAD
  syntax) and ``active``;
- ``varsets``: (name, label, [(property, FreeCAD type, value, expression, description)]);
- ``external``: external geometry, ("line", x1, y1, x2, y2), built from a ``Part::Line``;
- ``formulas``: constraint or variable id → the expected CPSK ``value``;
- ``refused``: the labels the export must refuse (constraint names, ``Constraint<n>``,
  primitive ids or ``<VarSet label>.<property>``); the case exports when it is empty.
"""

X: list[dict] = []


def xcase(name, geometry, constraints, **extra):
    X.append({"name": name, "geometry": geometry, "constraints": constraints, **extra})


xcase(
    "expressions",
    [("line", 0.1, 0.1, 30, 1), ("line", 30, 1, 31, 15), ("line", 0, 0, 5, 4)],
    [
        ("Coincident", [0, 1, -1, 1], None, True),
        ("Horizontal", [0], None, True),
        ("Distance", [0], 40, True, {"name": "w", "expression": "Vars.width * 2"}),
        ("Coincident", [1, 1, 0, 2], None, True),
        ("Vertical", [1], None, True),
        (
            "Distance",
            [1],
            20,
            True,
            {"name": "height", "expression": ".Constraints.w * <<Plate>>.ratio"},
        ),
        ("Coincident", [2, 1, -1, 1], None, True),
        # FreeCAD: (-2)^2 * 10 = 40°, (2^3)^2 / 8 mm = 8 mm
        ("Angle", [2], 40, True, {"name": "tilt", "expression": "-2^2 * 10"}),
        ("Distance", [2], 8, True, {"name": "d", "expression": "2^3^2 / 8 mm"}),
    ],
    varsets=[
        (
            "Vars",
            "Plate",
            [
                ("width", "App::PropertyDistance", 20, None, "Plate width"),
                ("ratio", "App::PropertyFloat", 0.5, "width / 40", ""),
                ("unused", "App::PropertyAngle", 30, None, ""),
            ],
        )
    ],
    formulas={
        "w": "width * 2",
        "height": "w * ratio",
        "tilt": "(-2)^2 * 10",
        "d": "(2^3)^2 / 8mm",
        "width": "20",
        "ratio": "width / 40",
        "unused": "30",
    },
)
xcase(
    "external_line",
    [("line", -2.7, 1.2, 4, 0.3)],
    [
        ("Coincident", [0, 1, -3, 1], None, True),
        ("Horizontal", [0], None, True),
        ("Distance", [0], 5, True),
    ],
    external=[("line", -3, 1, 7, 1)],
)
xcase(
    "inactive_constraint",
    [("point", 0, 0, "block"), ("line", 0.2, 0.1, 5, 1)],
    [
        ("Coincident", [1, 1, 0, 1], None, True),
        ("Horizontal", [1], None, True),
        ("Distance", [1], 7, True, {"name": "old", "active": False}),
        ("Distance", [1], 5, True, {"name": "length"}),
    ],
)
xcase(
    "refused",
    [("line", 0, 0, 10, 0, "block"), ("line", 0, 1, 10, 1), ("circle", 5, 5, 2, "block")],
    [
        ("Tangent", [0, 1], None, True),
        ("Distance", [1], 10, True, {"name": "my width"}),
        ("Distance", [1, 1, 2], 2, True),
        ("Distance", [1], 10, True, {"name": "m", "active": False}),
    ],
    refused=["Constraint3", "my width", "Constraint5", "m"],
)
xcase(
    "refused_expression",
    [("line", 0, 0, 10, 0, "block"), ("line", 0, 1, 10, 1)],
    [
        ("Distance", [1], 5, True, {"name": "a", "expression": "1 > 0 ? 5 : 6"}),
        ("Distance", [1, 1, 0], 1, True, {"name": "b", "expression": "floor(1.5)"}),
    ],
    refused=["a", "b"],
)
