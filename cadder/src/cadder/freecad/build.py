"""Build a FreeCAD 1.x Assembly from a cadder manifest (:mod:`cadder.freecad.export`).

Runs inside FreeCAD's command-line binary, with only FreeCAD's Python (no cadder import), no
GUI or display needed::

    CADDER_FREECAD_MANIFEST=freecad/<name>/manifest.json freecadcmd .../cadder/freecad/build.py

(``cadder freecad`` does both steps.) The manifest names the output file.

Every component becomes an ``App::Part`` holding its STL mesh, with the part origin at the
mesh's bounding-box center. A shape used several times (wheels, motors, ...) is one hidden
master part outside the assembly, and the assembly holds an ``App::Link`` per use. The grounded
body's root gets a Grounded joint; every component is Fixed to its body's root, except the
second end of an explicit joint inside its own body; then the explicit joints (Slider,
Revolute, ...) are added, with their limits.

The GUI-only part of the file (``GuiDocument.xml``: visibility, colors, the joints' Python view
providers) is written by :func:`add_gui_state` from the prototypes in ``gui_document.xml``.
"""

import copy
import json
import os
import struct
import sys
import traceback
import zipfile

import FreeCAD as App
import Mesh
from lxml import etree  # FreeCAD's own Python ships it

sys.path.append(os.path.join(App.getResourceDir(), "Mod", "Assembly"))
import JointObject

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_mesh(stl_dir, stl):
    """The STL as a mesh, repaired where needed and centered on its bounding box."""
    mesh = Mesh.Mesh(os.path.join(stl_dir, f"{stl}.stl"))
    if mesh.hasNonManifolds() or mesh.hasNonUniformOrientedFacets():
        mesh.harmonizeNormals()
        mesh.removeNonManifolds()
    if mesh.hasSelfIntersections():  # overlapping fasteners; FreeCAD warns about it on load
        mesh.fixSelfIntersections()
    center = mesh.BoundBox.Center
    mesh.translate(-center.x, -center.y, -center.z)
    return mesh


def _make_part(doc, container, name, entry, stl_dir, label):
    """A part holding the mesh of ``entry``, with its display color and transparency."""
    part = doc.addObject("App::Part", name) if container is doc else container.newObject("App::Part", name)
    feature = part.newObject("Mesh::Feature", f"{name}_mesh")
    feature.Mesh = _load_mesh(stl_dir, entry["stl"])
    part.addProperty("App::PropertyIntegerList", "RGB", label, "Display color (RGB)")
    part.RGB = entry["color"]
    part.addProperty("App::PropertyInteger", "Transparency", label, "Transparency (%)")
    part.Transparency = entry.get("transparency", 0)
    return part


def _placement_of(entry):
    """World placement of a component: its bounding-box center and orientation."""
    rotation_matrix = entry["rotation"]
    matrix = App.Matrix(
        rotation_matrix[0], rotation_matrix[1], rotation_matrix[2], entry["center"][0],
        rotation_matrix[3], rotation_matrix[4], rotation_matrix[5], entry["center"][1],
        rotation_matrix[6], rotation_matrix[7], rotation_matrix[8], entry["center"][2],
        0, 0, 0, 1,
    )  # fmt: skip
    return App.Placement(matrix)


def _joint_frame(origin, direction):
    """World placement of a joint frame whose z axis is the axis direction."""
    rotation = App.Rotation(App.Vector(0, 0, 1), App.Vector(*direction))
    return App.Placement(App.Vector(*origin), rotation)


def _make_joint(joint_group, kind, a, b, world, label, **props):
    """Joint of type ``kind`` between parts ``a`` and ``b`` with its frame at ``world``."""
    joint = joint_group.newObject("App::FeaturePython", label)
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


def main():
    path = os.environ["CADDER_FREECAD_MANIFEST"]
    with open(path) as handle:
        manifest = json.load(handle)
    stl_dir = os.path.join(os.path.dirname(path), "stl")
    out = manifest["output"]
    label = manifest["label"]
    roots = {b["name"]: b["root"] for b in manifest["bodies"]}
    grounded = next(b["root"] for b in manifest["bodies"] if b["grounded"])
    body_of = {c["name"]: c["body"] for c in manifest["components"]}
    #: second ends of explicit joints inside their own body: they move, so they are not Fixed
    moving = {j["b"] for j in manifest["joints"] if j["kind"] != "Fixed" and body_of[j["a"]] == body_of[j["b"]]}

    doc = App.newDocument(manifest["name"])
    asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
    asm.Label = label
    joints = asm.newObject("Assembly::JointGroup", "Joints")

    # A shape used by several components is one master part, kept out of the assembly and
    # hidden, and the assembly holds an App::Link to it for each use.
    uses = {}
    for entry in manifest["components"]:
        uses.setdefault(entry["stl"], []).append(entry)
    parts_group = doc.addObject("App::DocumentObjectGroup", "Parts")
    parts_group.Label = "Parts"
    masters = {
        stl: _make_part(doc, parts_group, stl, entries[0], stl_dir, label)
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
            part = _make_part(doc, asm, name, entry, stl_dir, label)
        part.Label = name
        part.Placement = _placement_of(entry)
        part.addProperty("App::PropertyString", "RigidBody", label, "Rigid body it moves with")
        part.RigidBody = entry["body"]
        parts[name] = part
        bodies.setdefault(entry["body"], []).append(name)

    ground = joints.newObject("App::FeaturePython", f"Ground {grounded}")
    JointObject.GroundedJoint(ground, parts[grounded])

    # Fixed joints inside each rigid body.
    for body, names in bodies.items():
        root = parts[roots[body]]
        for name in names:
            if name == roots[body] or name in moving:
                continue
            _make_joint(joints, "Fixed", root, parts[name], parts[name].Placement, f"Fixed {name}")

    # The joints that give the assembly its motion, with limits relative to the modeled pose.
    for j in manifest["joints"]:
        props = {}
        if j["limits"] is not None:
            low, high = j["limits"]
            prefix = "Angle" if j["kind"] == "Revolute" else "Length"
            props = {
                f"Enable{prefix}Min": True,
                f"Enable{prefix}Max": True,
                f"{prefix}Min": low,
                f"{prefix}Max": high,
            }
        _make_joint(
            joints,
            j["kind"],
            parts[j["a"]],
            parts[j["b"]],
            _joint_frame(j["origin"], j["direction"]),
            j["label"],
            **props,
        )

    doc.recompute()
    status = asm.solve()
    print(f"solve() -> {status}; {len(parts)} components ({len(masters)} shared shapes), {len(joints.Group)} joints")

    doc.saveAs(out)
    add_gui_state(out, doc, masters)
    print(f"wrote {out}", flush=True)


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


class _ViewProviders:
    """The view providers of ``GuiDocument.xml``, filled in from its prototypes."""

    def __init__(self, data):
        self.data = data
        self.prototypes = {provider.get("template"): provider for provider in data.findall("ViewProvider")}
        for provider in self.prototypes.values():
            data.remove(provider)
        self.appearances = {}  # file name -> bytes

    def add(self, kind, obj, visible, rgb=None, transparency=0):
        """Add the entry of ``obj``, made from the prototype of its ``kind``."""
        provider = copy.deepcopy(self.prototypes[kind])
        del provider.attrib["template"]
        provider.set("name", obj.Name)
        provider.find('.//Property[@name="Visibility"]/Bool').set("value", str(visible).lower())
        if rgb is not None:
            name = f"ShapeAppearance{len(self.appearances) + 1000}"
            provider.find('.//Property[@name="ShapeAppearance"]/MaterialList').set("file", name)
            provider.find('.//Property[@name="Transparency"]/Integer').set("value", str(transparency))
            red, green, blue = rgb
            self.appearances[name] = struct.pack(
                "<i4I2f3i",
                1,
                0x555555FF,  # ambient, diffuse, specular, emissive as RGBA, then shininess,
                (red << 24) | (green << 16) | (blue << 8) | 0xFF,  # transparency and three empty strings
                0x888888FF,
                0x000000FF,
                0.9,
                transparency / 100,
                0,
                0,
                0,
            )
        self.data.append(provider)


def add_gui_state(path, doc, masters):
    """Add ``GuiDocument.xml`` (visibility, colors, joint view providers) to the saved file.

    Only the GUI writes it, and without it the file opens with everything hidden and the
    joints failing to recompute. It is built here from the prototypes in ``gui_document.xml``
    (copied, then name, visibility and color filled in) so the build runs headless. Shown: the
    assembly, its parts, links and their meshes (and the meshes of the masters, which the links
    draw). Hidden: joints, the "Parts" group, the masters, and every origin (objects without an
    entry open hidden).
    """
    tree = etree.parse(os.path.join(HERE, "gui_document.xml"), etree.XMLParser(remove_comments=True))
    data = tree.getroot().find("ViewProviderData")
    providers = _ViewProviders(data)

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
            kind = "master_mesh" if owner in master_objects else "mesh"
            providers.add(kind, obj, True, tuple(owner.RGB), owner.Transparency)
        elif obj.TypeId == "App::FeaturePython":  # joints (grounded or regular)
            providers.add("ground" if hasattr(obj, "ObjectToGround") else "joint", obj, False)
        elif obj in master_objects:
            providers.add("master", obj, False)
        elif obj.TypeId in kinds:
            providers.add(kinds[obj.TypeId], obj, kinds[obj.TypeId] != "group")
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
        for name, data_bytes in providers.appearances.items():
            dst.writestr(name, data_bytes)
    os.replace(temp, path)


# freecadcmd runs a script as a module named after the file, not as __main__
if __name__ in ("__main__", "build"):
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.exit(1)  # an uncaught exception would exit 0 and run the script again
