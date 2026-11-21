"""Build the pen plotter as a FreeCAD 1.x Assembly from ``freecad/stl`` + ``components.json``.

Run with the FreeCAD command-line binary, no GUI or display needed (``make freecad`` does both
steps)::

    freecadcmd freecad/build_assembly.py

The GUI-only part of the file (``GuiDocument.xml``: visibility, colors, the joints' Python view
providers) is written by :func:`add_gui_state` from the prototypes in ``gui_document.xml``.

Every component becomes an ``App::Part`` holding its STL mesh, with the part origin at the
mesh's bounding-box center. A shape used several times (V-wheels, SK10s, motors, ...) is one
hidden master part outside the assembly, and the assembly holds an ``App::Link`` per use.
Rigid groups (the "bodies" of ``components.json``) are tied to a root component with Fixed
joints; the bodies are tied to each other with the joints that give the machine its motion:

* gantry <-> Y shaft: one Slider on the left shaft (along Y, limited to the travel);
* X carriage <-> beam: Slider joint (along X, limited to the travel);
* pen slide <-> pen holder body: Slider joint (along Z, limited to the pen lift);
* Revolute joints: Y/X motor pulleys, Y/X idlers, the four V-wheels and the servo horn.

The model is in the machine frame (``params``): baseboard top face z = 0, +y toward the back.
"""
# ruff: noqa: N806

import copy
import json
import os
import struct
import sys
import zipfile

import FreeCAD as App
import Mesh
from lxml import etree  # FreeCAD's own Python ships it

sys.path.append(os.path.join(App.getResourceDir(), "Mod", "Assembly"))
import JointObject

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "PenPlotter.FCStd")


def main():
    with open(os.path.join(HERE, "components.json")) as handle:
        manifest = json.load(handle)
    AXES = manifest["axes"]
    TRAVEL = manifest["travel"]
    REF = manifest["reference_pose"]

    #: Root component of each rigid body: everything else of the body is Fixed to it.
    ROOTS = {
        "base": "baseboard",
        "gantry": "gantry_beam",
        "carriage": "x_carriage",
        "slide": "pen_slide",
    }
    #: Components that are not Fixed to their body's root because they have a joint of their own.
    MOVING = {
        "y_idler_L", "y_idler_R", "y_pulley_L", "y_pulley_R",
        "x_idler", "x_pulley", "pen_horn",
        "vwheel_L_top", "vwheel_L_bottom", "vwheel_R_top", "vwheel_R_bottom",
    }  # fmt: skip

    doc = App.newDocument("PenPlotter")
    asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
    asm.Label = "Pen plotter"
    joints = asm.newObject("Assembly::JointGroup", "Joints")

    def load_mesh(stl):
        """The STL as a mesh, repaired where needed and centered on its bounding box."""
        mesh = Mesh.Mesh(os.path.join(HERE, "stl", f"{stl}.stl"))
        if mesh.hasNonManifolds() or mesh.hasNonUniformOrientedFacets():
            mesh.harmonizeNormals()
            mesh.removeNonManifolds()
        if mesh.hasSelfIntersections():  # overlapping fasteners; FreeCAD warns about it on load
            mesh.fixSelfIntersections()
        center = mesh.BoundBox.Center
        mesh.translate(-center.x, -center.y, -center.z)
        return mesh

    def make_part(container, name, stl, rgb):
        """A part holding the mesh of ``stl``, with the display color in its ``RGB`` property."""
        if container is doc:
            part = doc.addObject("App::Part", name)
        else:
            part = container.newObject("App::Part", name)
        feature = part.newObject("Mesh::Feature", f"{name}_mesh")
        feature.Mesh = load_mesh(stl)
        part.addProperty("App::PropertyIntegerList", "RGB", "Pen plotter", "Display color (RGB)")
        part.RGB = rgb
        return part

    def placement_of(entry):
        """World placement of a component: its bounding-box center and orientation."""
        m = entry["rotation"]
        matrix = App.Matrix(
            m[0], m[1], m[2], entry["center"][0],
            m[3], m[4], m[5], entry["center"][1],
            m[6], m[7], m[8], entry["center"][2],
            0, 0, 0, 1,
        )  # fmt: skip
        return App.Placement(matrix)

    # A shape used by several components (V-wheels, SK10s, motors, ...) is one master part, kept
    # out of the assembly and hidden, and the assembly holds an App::Link to it for each use.
    uses = {}
    for entry in manifest["components"]:
        uses.setdefault(entry["stl"], []).append(entry)
    parts_group = doc.addObject("App::DocumentObjectGroup", "Parts")
    parts_group.Label = "Parts"
    masters = {
        stl: make_part(parts_group, stl, stl, entries[0]["color"])
        for stl, entries in uses.items()
        if len(entries) > 1
    }

    parts = {}
    bodies = {}
    for entry in manifest["components"]:
        name = entry["name"]
        if entry["stl"] in masters:
            part = asm.newObject("App::Link", name)
            part.LinkedObject = masters[entry["stl"]]
        else:
            part = make_part(asm, name, entry["stl"], entry["color"])
        part.Label = name
        part.Placement = placement_of(entry)
        part.addProperty(
            "App::PropertyString", "RigidBody", "Pen plotter", "Rigid body of the machine"
        )
        part.RigidBody = entry["body"]
        parts[name] = part
        bodies.setdefault(entry["body"], []).append(name)

    def frame(axis):
        """World placement of a joint frame whose z axis is the axis direction."""
        origin = App.Vector(*axis["origin"])
        rotation = App.Rotation(App.Vector(0, 0, 1), App.Vector(*axis["dir"]))
        return App.Placement(origin, rotation)

    def make_joint(kind, a, b, world, label, **props):
        """Joint of type ``kind`` between parts ``a`` and ``b`` with its frame at ``world``."""
        joint = joints.newObject("App::FeaturePython", label)
        JointObject.Joint(joint, JointObject.JointTypes.index(kind))
        joint.Detach1 = True
        joint.Detach2 = True
        joint.Reference1 = [a, ["", ""]]
        joint.Reference2 = [b, ["", ""]]
        joint.Placement1 = a.Placement.inverse() * world
        joint.Placement2 = b.Placement.inverse() * world
        for key, value in props.items():
            setattr(joint, key, value)
        return joint

    # Ground the baseboard.
    ground = joints.newObject("App::FeaturePython", "Ground baseboard")
    JointObject.GroundedJoint(ground, parts[ROOTS["base"]])

    # Fixed joints inside each rigid body.
    for body, names in bodies.items():
        root = parts[ROOTS[body]]
        for name in names:
            if name == ROOTS[body] or name in MOVING:
                continue
            make_joint("Fixed", root, parts[name], parts[name].Placement, f"Fixed {name}")

    # Gantry on the Y shafts. One Slider joint (translation along Y only) on the left shaft: the
    # right blocks are Fixed to the gantry and need no joint of their own. A second joint on the
    # right shaft would close a loop (shaft - block - gantry - block - shaft - baseboard) and
    # over-constrain the solver, which then rejects dragging ("a grounded object moved").
    # Limits are relative to the reference pose.
    y_min = TRAVEL["gantry_y"][0] - REF["gantry_y"]
    y_max = TRAVEL["gantry_y"][1] - REF["gantry_y"]
    make_joint(
        "Slider",
        parts["y_shaft_L"],
        parts["scs10uu_L0"],
        frame(AXES["y_shaft_L"]),
        "Gantry slides on Y shaft (Y)",
        EnableLengthMin=True,
        EnableLengthMax=True,
        LengthMin=y_min,
        LengthMax=y_max,
    )

    # X carriage on the beam.
    x_min = TRAVEL["carriage_x"][0] - REF["carriage_x"]
    x_max = TRAVEL["carriage_x"][1] - REF["carriage_x"]
    make_joint(
        "Slider",
        parts["gantry_beam"],
        parts["x_carriage"],
        frame(AXES["beam"]),
        "Carriage slides on beam (X)",
        EnableLengthMin=True,
        EnableLengthMax=True,
        LengthMin=x_min,
        LengthMax=x_max,
    )

    # Pen slide in the pen holder body (pen up at the reference pose, so it can only go down).
    make_joint(
        "Slider",
        parts["pen_body"],
        parts["pen_slide"],
        frame(AXES["pen_slide"]),
        "Pen slide (Z)",
        EnableLengthMin=True,
        EnableLengthMax=True,
        LengthMin=-TRAVEL["pen_lift"],
        LengthMax=0.0,
    )

    # Revolute joints: (moving part, host part, axis).
    for side in "LR":
        make_joint(
            "Revolute", parts[f"y_idler_slider_{side}"], parts[f"y_idler_{side}"],
            frame(AXES[f"y_idler_{side}"]), f"Y idler {side} turns",
        )  # fmt: skip
        make_joint(
            "Revolute", parts[f"y_motor_{side}"], parts[f"y_pulley_{side}"],
            frame(AXES[f"y_pulley_{side}"]), f"Y pulley {side} turns",
        )  # fmt: skip
    make_joint(
        "Revolute",
        parts["x_idler_slider"],  # the idler turns on the (floating) slider, T3.22
        parts["x_idler"],
        frame(AXES["x_idler"]),
        "X idler turns",
    )
    make_joint(
        "Revolute", parts["x_motor"], parts["x_pulley"], frame(AXES["x_pulley"]), "X pulley turns"
    )
    make_joint(
        "Revolute",
        parts["pen_servo"],
        parts["pen_horn"],
        frame(AXES["pen_horn"]),
        "Servo horn turns",
    )
    for side in "LR":
        for pos in ("top", "bottom"):
            make_joint(
                "Revolute", parts["x_carriage"], parts[f"vwheel_{side}_{pos}"],
                frame(AXES[f"vwheel_{side}_{pos}"]), f"V-wheel {side} {pos} turns",
            )  # fmt: skip

    doc.recompute()
    status = asm.solve()
    print(
        f"solve() -> {status}; {len(parts)} components ({len(masters)} shared shapes), "
        f"{len(joints.Group)} joints"
    )

    doc.saveAs(OUT)
    add_gui_state(OUT, doc, masters, parts_group)
    print(f"wrote {OUT}", flush=True)


def isometric_camera(corners):
    """Coin camera settings: FreeCAD's isometric view (``0``) fitted to the points (``V, F``).

    Looks from +x, -y, +z toward the model with z up on the screen. Orthographic, with a
    square viewport (aspect 1) sized to the projected extent, so the whole model is visible
    in a window of any shape.
    """
    look = App.Vector(-1, 1, -1).normalize()
    up = (App.Vector(0, 0, 1) - look * look.z).normalize()
    right = look.cross(up)
    # camera x = right, y = up, z = backward
    rotation = App.Rotation(App.Matrix(
        right.x, up.x, -look.x, 0, right.y, up.y, -look.y, 0, right.z, up.z, -look.z, 0, 0, 0, 0, 1
    ))  # fmt: skip
    xs = [p.dot(right) for p in corners]
    ys = [p.dot(up) for p in corners]
    zs = [p.dot(look) for p in corners]
    center = right * ((min(xs) + max(xs)) / 2) + up * ((min(ys) + max(ys)) / 2)
    size = 1.02 * max(max(xs) - min(xs), max(ys) - min(ys))
    depth = max(zs) - min(zs)
    distance = depth  # eye position in front of the nearest point
    position = center + look * (min(zs) - distance)
    ax, ay, az = rotation.Axis
    return (
        "OrthographicCamera {\n  viewportMapping ADJUST_CAMERA\n"
        f"  position {position.x:.6g} {position.y:.6g} {position.z:.6g}\n"
        f"  orientation {ax:.8g} {ay:.8g} {az:.8g}  {rotation.Angle:.8g}\n"
        f"  nearDistance {distance - depth * 0.05:.6g}\n"
        f"  farDistance {distance + depth * 1.05:.6g}\n"
        f"  aspectRatio 1\n  focalDistance {distance + depth / 2:.6g}\n  height {size:.6g}\n\n}}\n"
    )


def assembly_corners(asm):
    """Bounding-box corners (world frame) of every component in the assembly."""
    corners = []
    for item in asm.Group:
        if item.TypeId not in ("App::Part", "App::Link"):
            continue
        source = item.LinkedObject if item.TypeId == "App::Link" else item
        box = source.Group[0].Mesh.BoundBox
        for x in (box.XMin, box.XMax):
            for y in (box.YMin, box.YMax):
                for z in (box.ZMin, box.ZMax):
                    corners.append(item.Placement.multVec(App.Vector(x, y, z)))
    return corners


def add_gui_state(path, doc, masters, parts_group):
    """Add ``GuiDocument.xml`` (visibility, colors, joint view providers) to the saved file.

    Only the GUI writes it, and without it the file opens with everything hidden and the
    joints failing to recompute. It is built here from the prototypes in ``gui_document.xml``
    (copied, then name, visibility and color filled in) so the build runs headless. Shown: the
    assembly, its parts, links and their meshes (and the meshes of the masters, which the links
    draw). Hidden: joints, the "Parts" group, the masters, and every origin (objects without an
    entry open hidden).
    """
    tree = etree.parse(
        os.path.join(HERE, "gui_document.xml"), etree.XMLParser(remove_comments=True)
    )
    data = tree.getroot().find("ViewProviderData")
    prototypes = {vp.get("template"): vp for vp in data.findall("ViewProvider")}
    for vp in prototypes.values():
        data.remove(vp)
    appearances = {}  # file name -> bytes

    def add(kind, obj, visible, rgb=None, transparency=0):
        vp = copy.deepcopy(prototypes[kind])
        del vp.attrib["template"]
        vp.set("name", obj.Name)
        vp.find('.//Property[@name="Visibility"]/Bool').set("value", str(visible).lower())
        if rgb is not None:
            name = f"ShapeAppearance{len(appearances) + 1000}"
            vp.find('.//Property[@name="ShapeAppearance"]/MaterialList').set("file", name)
            vp.find('.//Property[@name="Transparency"]/Integer').set("value", str(transparency))
            r, g, b = rgb
            appearances[name] = struct.pack(
                "<i4I2f3i",
                1,
                0x555555FF,  # ambient, diffuse, specular, emissive as RGBA, then shininess,
                (r << 24) | (g << 16) | (b << 8) | 0xFF,  # transparency and three empty strings
                0x888888FF,
                0x000000FF,
                0.9,
                transparency / 100,
                0,
                0,
                0,
            )
        data.append(vp)

    kinds = {
        "Assembly::AssemblyObject": "assembly",
        "Assembly::JointGroup": "group",
        "App::DocumentObjectGroup": "group",
        "App::Part": "part",
        "App::Link": "link",
    }
    master_objects = list(masters.values())
    for obj in doc.Objects:
        if obj.TypeId == "Mesh::Feature":
            owner = obj.getParentGeoFeatureGroup()
            transparency = 60 if owner.Name in ("baseboard", "bed_panel") else 0
            kind = "master_mesh" if owner in master_objects else "mesh"
            add(kind, obj, True, tuple(owner.RGB), transparency)
        elif obj.TypeId == "App::FeaturePython":  # joints (grounded or regular)
            add("ground" if hasattr(obj, "ObjectToGround") else "joint", obj, False)
        elif obj in master_objects:
            add("master", obj, False)
        elif obj.TypeId in kinds:
            add(kinds[obj.TypeId], obj, kinds[obj.TypeId] != "group")
    data.set("Count", str(len(data)))
    asm = doc.getObject("Assembly")
    tree.getroot().find("Camera").set("settings", isometric_camera(assembly_corners(asm)))
    etree.indent(tree.getroot(), space="    ")
    xml = etree.tostring(tree, xml_declaration=True, encoding="utf-8")

    temp = path + ".tmp"
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        dst.writestr("GuiDocument.xml", xml)
        for name, data_bytes in appearances.items():
            dst.writestr(name, data_bytes)
    os.replace(temp, path)


try:
    main()
except Exception:
    import traceback

    traceback.print_exc()
    sys.stdout.flush()
    raise
