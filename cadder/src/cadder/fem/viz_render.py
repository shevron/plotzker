"""Renders one load case with VTK. Runs in FreeCAD's Python, not in the project environment.

Usage: python viz_render.py DATA.json OUT_DIR   (prints the file names it wrote)

Writes <case>_utilization.png (and _rear), <case>_displacement.png, <case>_hotspot.png (and
_rear) and <case>.vtu (the undeformed mesh with displacement and utilization fields).
Shapes are drawn deformed (scale printed on the image) over a faint ghost of the original.
"""

import json
import math
import sys
from functools import partial
from pathlib import Path

import vtk

UTIL_RANGE = (0.0, 2.0)


def load(path):
    """The exported fields."""
    with open(path) as f:
        return json.load(f)


def make_points(xyz, u, scale):
    """Points displaced by ``scale`` times the displacement."""
    pts = vtk.vtkPoints()
    for point, displacement in zip(xyz, u, strict=True):
        pts.InsertNextPoint(
            point[0] + scale * displacement[0], point[1] + scale * displacement[1], point[2] + scale * displacement[2]
        )
    return pts


def surface(points, tris, util, disp):
    """The boundary surface with nodal scalar fields."""
    cells = vtk.vtkCellArray()
    for t in tris:
        cells.InsertNextCell(3, t)
    poly = vtk.vtkPolyData()
    poly.SetPoints(points)
    poly.SetPolys(cells)
    for name, values in (("utilization", util), ("displacement_mm", disp)):
        arr = vtk.vtkFloatArray()
        arr.SetName(name)
        for v in values:
            arr.InsertNextValue(v)
        poly.GetPointData().AddArray(arr)
    normals = vtk.vtkPolyDataNormals()
    normals.SetInputData(poly)
    normals.SetFeatureAngle(50)
    normals.SplittingOn()
    normals.ConsistencyOff()
    normals.Update()
    return normals.GetOutput()


def utilization_colors():
    """Blue → green → yellow (85 % of the limit) → orange (at it) → red → dark red."""
    ctf = vtk.vtkColorTransferFunction()
    for value, rgb in (
        (0.0, (0.20, 0.40, 0.90)),
        (0.5, (0.20, 0.75, 0.40)),
        (0.85, (1.00, 0.90, 0.20)),
        (1.0, (1.00, 0.50, 0.10)),
        (1.3, (0.90, 0.10, 0.10)),
        (2.0, (0.40, 0.00, 0.30)),
    ):
        ctf.AddRGBPoint(value, *rgb)
    return ctf


def displacement_colors(top):
    """Blue → cyan → yellow → red."""
    ctf = vtk.vtkColorTransferFunction()
    for f, rgb in (
        (0.0, (0.20, 0.30, 0.90)),
        (0.35, (0.20, 0.80, 0.85)),
        (0.7, (1.00, 0.90, 0.20)),
        (1.0, (0.90, 0.10, 0.10)),
    ):
        ctf.AddRGBPoint(f * top, *rgb)
    return ctf


def render(poly, ghost, colors, rng, field, bar_title, text, camera, marker, out, size=(1200, 850)):
    """One image."""
    poly.GetPointData().SetActiveScalars(field)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(poly)
    mapper.SetLookupTable(colors)
    mapper.SetScalarRange(*rng)
    mapper.SetScalarModeToUsePointData()
    mapper.ScalarVisibilityOn()
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    ghost_mapper = vtk.vtkPolyDataMapper()
    ghost_mapper.SetInputData(ghost)
    ghost_mapper.ScalarVisibilityOff()
    ghost_actor = vtk.vtkActor()
    ghost_actor.SetMapper(ghost_mapper)
    ghost_actor.GetProperty().SetColor(0.6, 0.6, 0.6)
    ghost_actor.GetProperty().SetOpacity(0.12)
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(1, 1, 1)
    renderer.AddActor(ghost_actor)
    renderer.AddActor(actor)
    for position, radius, rgb in marker:
        sphere = vtk.vtkSphereSource()
        sphere.SetCenter(*position)
        sphere.SetRadius(radius)
        sphere.SetThetaResolution(16)
        sphere.SetPhiResolution(16)
        slab_mapper = vtk.vtkPolyDataMapper()
        slab_mapper.SetInputConnection(sphere.GetOutputPort())
        slab_actor = vtk.vtkActor()
        slab_actor.SetMapper(slab_mapper)
        slab_actor.GetProperty().SetColor(*rgb)
        renderer.AddActor(slab_actor)
    bar = vtk.vtkScalarBarActor()
    bar.SetLookupTable(colors)
    bar.SetTitle(bar_title)
    bar.SetNumberOfLabels(5)
    bar.SetWidth(0.08)
    bar.SetHeight(0.6)
    bar.SetPosition(0.9, 0.2)
    bar.GetTitleTextProperty().SetColor(0, 0, 0)
    bar.GetLabelTextProperty().SetColor(0, 0, 0)
    renderer.AddActor2D(bar)
    label = vtk.vtkTextActor()
    label.SetInput(text)
    label.SetPosition(12, 12)
    label.GetTextProperty().SetColor(0, 0, 0)
    label.GetTextProperty().SetFontSize(15)
    label.GetTextProperty().SetLineSpacing(1.2)
    renderer.AddActor2D(label)
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetMultiSamples(4)
    window.AddRenderer(renderer)
    window.SetSize(*size)
    cam = renderer.GetActiveCamera()
    focal, direction, distance = camera
    cam.SetFocalPoint(*focal)
    cam.SetPosition(*(focal[i] + direction[i] * distance for i in range(3)))
    cam.SetViewUp(0, 0, 1)
    renderer.ResetCameraClippingRange()
    window.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(window)
    grab.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(out))
    writer.SetInputConnection(grab.GetOutputPort())
    writer.Write()


def write_vtu(data, path, disp, util):
    """The undeformed volume mesh with the result fields, for ParaView or FreeCAD."""
    grid = vtk.vtkUnstructuredGrid()
    pts = vtk.vtkPoints()
    for point in data["xyz"]:
        pts.InsertNextPoint(*point)
    grid.SetPoints(pts)
    for tet in data["tets"]:
        ids = vtk.vtkIdList()
        for i in tet:
            ids.InsertNextId(i)
        grid.InsertNextCell(24, ids)  # quadratic tetrahedron; CalculiX and VTK node order agree
    vec = vtk.vtkFloatArray()
    vec.SetName("displacement_mm")
    vec.SetNumberOfComponents(3)
    for displacement in data["u"]:
        vec.InsertNextTuple3(*displacement)
    grid.GetPointData().AddArray(vec)
    arr = vtk.vtkFloatArray()
    arr.SetName("utilization")
    for value in util:
        arr.InsertNextValue(value)
    grid.GetPointData().AddArray(arr)
    mag = vtk.vtkFloatArray()
    mag.SetName("displacement_magnitude_mm")
    for value in disp:
        mag.InsertNextValue(value)
    grid.GetPointData().AddArray(mag)
    writer = vtk.vtkXMLUnstructuredGridWriter()
    writer.SetFileName(str(path))
    writer.SetInputData(grid)
    writer.Write()


def normalize(v):
    """Unit vector."""
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def _render_into(names, out, name, *args):
    """Render the picture ``name`` into ``out`` and note it in ``names``."""
    render(*args, out / name)
    names.append(name)


def main():
    """Render every picture of the case."""
    data = load(sys.argv[1])
    out = Path(sys.argv[2])
    case = data["case"]
    xyz, displacements, util = data["xyz"], data["u"], data["util"]
    disp = [math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) for d in displacements]
    lower = [min(p[i] for p in xyz) for i in range(3)]
    upper = [max(p[i] for p in xyz) for i in range(3)]
    center = [(lower[i] + upper[i]) / 2 for i in range(3)]
    diag = math.sqrt(sum((upper[i] - lower[i]) ** 2 for i in range(3)))
    top = max(disp) or 1e-9
    scale = 0.05 * diag / top
    deformed = surface(make_points(xyz, displacements, scale), data["tris"], util, disp)
    ghost = surface(make_points(xyz, displacements, 0.0), data["tris"], util, disp)
    head = "\n".join(data["lines"])
    note = f"deformation x{scale:.0f}, ghost = undeformed   max displacement {top:.3f} mm"
    names = []

    put = partial(_render_into, names, out)

    view = normalize((1, -1.1, 0.8))
    back = normalize((-1, 1.1, 0.8))
    util_args = (
        utilization_colors(),
        UTIL_RANGE,
        "utilization",
        "utilization = failure index x safety factor (1.0 = at the allowable)",
    )
    hot = xyz[data["hotspot"]]
    hot_def = [hot[i] + scale * displacements[data["hotspot"]][i] for i in range(3)]
    mark = [(hot_def, 0.012 * diag, (0.85, 0.0, 0.85))]
    for name, direction in (
        (f"{case}_utilization.png", view),
        (f"{case}_utilization_rear.png", back),
    ):
        put(
            name,
            deformed,
            ghost,
            util_args[0],
            util_args[1],
            "utilization",
            util_args[2],
            f"{head}\n{util_args[3]}\n{note}",
            (center, direction, 1.9 * diag),
            mark,
        )
    put(
        f"{case}_displacement.png",
        deformed,
        ghost,
        displacement_colors(top),
        (0, top),
        "displacement_mm",
        "|u| [mm]",
        f"{head}\ndisplacement magnitude\n{note}",
        (center, view, 1.9 * diag),
        mark,
    )
    for name, direction in ((f"{case}_hotspot.png", view), (f"{case}_hotspot_rear.png", back)):
        put(
            name,
            deformed,
            ghost,
            util_args[0],
            util_args[1],
            "utilization",
            "utilization",
            f"{head}\nmagenta ball = governing strength point (zoomed)\n{note}",
            (hot_def, direction, 0.7 * diag),
            mark,
        )
    write_vtu(data, out / f"{case}.vtu", disp, util)
    names.append(f"{case}.vtu")
    print(" ".join(names))


if __name__ == "__main__":
    main()
