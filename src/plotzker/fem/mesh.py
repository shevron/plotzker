"""Tetrahedral meshing of a cleaned STL with gmsh, and selecting mesh entities by region."""

import math
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from plotzker.fem.tools import find_tool
from plotzker.regions import Region
from plotzker.types import Vec3

#: Nodes closer than this (mm) are the same node.
MERGE_TOL = 5e-4
#: Seconds gmsh may take on one attempt.
GMSH_TIMEOUT_S = 120


@dataclass(frozen=True)
class TriFace:
    """A boundary triangle (6-node), with its outward unit normal."""

    nodes: tuple[int, ...]  #: 3 corners, then 3 mid-edge nodes
    centroid: Vec3
    normal: Vec3
    area: float


@dataclass
class Mesh:
    """A quadratic tetrahedral mesh (CalculiX C3D10 node order) with its boundary faces."""

    nodes: dict[int, Vec3]
    tets: list[tuple[int, ...]]
    faces: list[TriFace]
    size: float
    strategy: int = 0  #: index into STRATEGIES that produced it

    def min_tet_volume(self) -> float:
        """Smallest signed volume of a tetrahedron (≤ 0 means an inverted or flat element)."""
        return min(self._signed_volume(tet) for tet in self.tets)

    def _signed_volume(self, tet: tuple[int, ...]) -> float:
        """Signed volume of one tetrahedron (corner nodes)."""
        p0, p1, p2, p3 = (self.nodes[n] for n in tet[:4])
        ux, uy, uz = (p1[i] - p0[i] for i in range(3))
        vx, vy, vz = (p2[i] - p0[i] for i in range(3))
        wx, wy, wz = (p3[i] - p0[i] for i in range(3))
        return (ux * (vy * wz - vz * wy) - uy * (vx * wz - vz * wx) + uz * (vx * wy - vy * wx)) / 6

    def volume(self) -> float:
        """Sum of the tetrahedra volumes (corner nodes only)."""
        total = 0.0
        for tet in self.tets:
            p0, p1, p2, p3 = (self.nodes[n] for n in tet[:4])
            ux, uy, uz = (p1[i] - p0[i] for i in range(3))
            vx, vy, vz = (p2[i] - p0[i] for i in range(3))
            wx, wy, wz = (p3[i] - p0[i] for i in range(3))
            total += abs(
                ux * (vy * wz - vz * wy) - uy * (vx * wz - vz * wx) + uz * (vx * wy - vy * wx)
            )
        return total / 6


#: (3D algorithm, size factor) tried in turn: gmsh occasionally crashes or hangs on a combination.
STRATEGIES = ((1, 1.0), (4, 1.0), (10, 1.0), (1, 1.1), (4, 1.1))


@dataclass(frozen=True)
class SizeField:
    """Element size: ``near`` inside the boxes (and a transition around them), ``far`` elsewhere."""

    near: float
    far: float
    boxes: tuple[tuple[Vec3, Vec3], ...] = ()
    transition: float = 0.0

    def scaled(self, factor: float) -> SizeField:
        """The same field with every size multiplied by ``factor``."""
        return SizeField(self.near * factor, self.far * factor, self.boxes, self.transition)


def write_geo(stl: Path, field: SizeField, geo: Path, algorithm: int = 1) -> None:
    """The gmsh script: keep the STL triangles as the boundary, straight-sided tet10."""
    lines = [
        f'Merge "{stl}";',
        "ClassifySurfaces{40*Pi/180, 1, 0, Pi};",
        "CreateGeometry;",
        "s[] = Surface{:};",
        "Surface Loop(1) = s[];",
        "Volume(1) = {1};",
        "Mesh.MeshSizeExtendFromBoundary = 0;",
        "Mesh.MeshSizeFromPoints = 0;",
        "Mesh.MeshSizeFromCurvature = 0;",
        f"Mesh.MeshSizeMax = {field.far};",
        f"Mesh.MeshSizeMin = {field.near / 2};",
    ]
    if field.boxes:
        for i, (lo, hi) in enumerate(field.boxes, start=1):
            lines += [
                f"Field[{i}] = Box;",
                f"Field[{i}].VIn = {field.near};",
                f"Field[{i}].VOut = {field.far};",
                f"Field[{i}].XMin = {lo[0]}; Field[{i}].XMax = {hi[0]};",
                f"Field[{i}].YMin = {lo[1]}; Field[{i}].YMax = {hi[1]};",
                f"Field[{i}].ZMin = {lo[2]}; Field[{i}].ZMax = {hi[2]};",
                f"Field[{i}].Thickness = {field.transition};",
            ]
        last = len(field.boxes) + 1
        ids = ", ".join(str(i) for i in range(1, last))
        lines += [f"Field[{last}] = Min;", f"Field[{last}].FieldsList = {{{ids}}};"]
        lines.append(f"Background Field = {last};")
    lines += [
        f"Mesh.Algorithm3D = {algorithm};",
        "Mesh.ElementOrder = 2;",
        "Mesh.SecondOrderLinear = 1;",
        "Mesh.MshFileVersion = 2.2;",
    ]
    geo.write_text("\n".join(lines) + "\n")


def mesh_stl(
    stl: Path, field: SizeField, workdir: Path, name: str, first_strategy: int = 0
) -> Mesh:
    """Mesh ``stl`` to the size field, retrying other settings if gmsh fails."""
    geo, msh = workdir / f"{name}.geo", workdir / f"{name}.msh"
    last = ""
    for index, (algorithm, factor) in enumerate(STRATEGIES):
        if index < first_strategy:
            continue
        used = field.scaled(factor)
        write_geo(stl.resolve(), used, geo, algorithm)
        msh.unlink(missing_ok=True)
        try:
            result = subprocess.run(
                [str(find_tool("gmsh")), "-3", "-nopopup", str(geo), "-o", str(msh), "-v", "1"],
                capture_output=True,
                text=True,
                timeout=GMSH_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            last = f"timed out after {GMSH_TIMEOUT_S} s (is the STL too fine? use PLOTTER_FN=20)"
            continue
        if result.returncode == 0 and msh.is_file():
            mesh = read_msh(msh, used.near)
            if mesh.min_tet_volume() > 0:
                mesh.strategy = index
                return mesh
            last = "mesh has inverted elements"
            continue
        tail = (result.stdout + result.stderr).strip().splitlines()[-3:]
        last = f"exit {result.returncode} {' '.join(tail)}"
    raise RuntimeError(f"gmsh failed on {stl.name} with every setting; last: {last}")


def read_msh(path: Path, size: float) -> Mesh:
    """Read a gmsh 2.2 ASCII file with 10-node tets and 6-node triangles."""
    lines = path.read_text().split("\n")
    i = lines.index("$Nodes") + 1
    count = int(lines[i])
    nodes: dict[int, Vec3] = {}
    for line in lines[i + 1 : i + 1 + count]:
        a = line.split()
        nodes[int(a[0])] = (float(a[1]), float(a[2]), float(a[3]))
    i = lines.index("$Elements") + 1
    tets: list[tuple[int, ...]] = []
    tris: list[tuple[int, ...]] = []
    for line in lines[i + 1 : i + 1 + int(lines[i])]:
        a = line.split()
        kind, ntags = int(a[1]), int(a[2])
        conn = [int(x) for x in a[3 + ntags :]]
        if kind == 11:
            conn[8], conn[9] = conn[9], conn[8]  # gmsh → CalculiX node order
            tets.append(tuple(conn))
        elif kind == 9:
            tris.append(tuple(conn))
    if not tets:
        raise RuntimeError(f"{path.name}: gmsh produced no tetrahedra")
    nodes, tets, tris = _merge_coincident_nodes(nodes, tets, tris)
    return Mesh(nodes, tets, _oriented_faces(nodes, tets, tris), size)


def _merge_coincident_nodes(
    nodes: dict[int, Vec3], tets: list[tuple[int, ...]], tris: list[tuple[int, ...]]
) -> tuple[dict[int, Vec3], list[tuple[int, ...]], list[tuple[int, ...]]]:
    """Merge nodes at the same place and drop the elements that collapse (gmsh leaves such
    zero-length edges in a few meshes; CalculiX rejects them as non-positive Jacobians)."""
    cell = 2 * MERGE_TOL
    grid: dict[tuple[int, int, int], list[int]] = {}
    remap: dict[int, int] = {}
    for n, p in nodes.items():
        key = (int(p[0] // cell), int(p[1] // cell), int(p[2] // cell))
        target = n
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for m in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        q = nodes[m]
                        if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (
                            p[2] - q[2]
                        ) ** 2 <= MERGE_TOL**2:
                            target = m
        remap[n] = target
        if target == n:
            grid.setdefault(key, []).append(n)
    kept = {n: p for n, p in nodes.items() if remap[n] == n}

    def fix(elements: list[tuple[int, ...]], corners: int) -> list[tuple[int, ...]]:
        out = []
        for e in elements:
            mapped = tuple(remap[n] for n in e)
            if len(set(mapped)) == len(mapped):
                out.append(mapped)
        return out

    return kept, fix(tets, 4), fix(tris, 3)


def _oriented_faces(
    nodes: dict[int, Vec3], tets: list[tuple[int, ...]], tris: list[tuple[int, ...]]
) -> list[TriFace]:
    """Boundary triangles with outward normals (flipped away from the tetrahedron behind)."""
    opposite: dict[frozenset[int], int] = {}
    for tet in tets:
        a, b, c, d = tet[:4]
        for face, apex in (((a, b, c), d), ((a, b, d), c), ((a, c, d), b), ((b, c, d), a)):
            opposite[frozenset(face)] = apex
    faces = []
    for tri in tris:
        corners = tri[:3]
        behind = opposite.get(frozenset(corners))
        if behind is None:
            continue
        apex = behind
        p0, p1, p2 = (nodes[n] for n in corners)
        nx, ny, nz = _cross(p0, p1, p2)
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length == 0:
            continue
        inward = nx * (nodes[apex][0] - p0[0]) + ny * (nodes[apex][1] - p0[1])
        inward += nz * (nodes[apex][2] - p0[2])
        sign = -1.0 if inward > 0 else 1.0
        centroid = (
            (p0[0] + p1[0] + p2[0]) / 3,
            (p0[1] + p1[1] + p2[1]) / 3,
            (p0[2] + p1[2] + p2[2]) / 3,
        )
        faces.append(
            TriFace(
                tri,
                centroid,
                (sign * nx / length, sign * ny / length, sign * nz / length),
                length / 2,
            )
        )
    return faces


def _cross(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    """Cross product of the edges ab and ac."""
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


#: Sub-divisions per triangle edge when sampling how much of a face a region covers.
SAMPLES = 6


@dataclass(frozen=True)
class Cover:
    """A boundary face partly or wholly inside a region, with the covered sample points."""

    face: TriFace
    samples: tuple[tuple[Vec3, float], ...]  #: (barycentric coordinates, area) of each point


def _sub_triangles(n: int) -> list[Vec3]:
    """Barycentric centroids of the n² sub-triangles of a triangle."""
    points = []
    for i in range(n):
        for j in range(n - i):
            u, v = (i + 1 / 3) / n, (j + 1 / 3) / n
            points.append((1 - u - v, u, v))
            if i + j < n - 1:
                u, v = (i + 2 / 3) / n, (j + 2 / 3) / n
                points.append((1 - u - v, u, v))
    return points


def cover_region(mesh: Mesh, region: Region, n: int = SAMPLES) -> list[Cover]:
    """The boundary faces a region touches, with the sample points of each face it covers.

    Sampling each face (instead of testing its centroid) makes the covered area, and so the
    loads and supports built from it, nearly independent of the element size.
    """
    lo, hi = region.bounds()
    bary = _sub_triangles(n)
    covers = []
    for face in mesh.faces:
        a, b, c = (mesh.nodes[k] for k in face.nodes[:3])
        if any(
            max(a[i], b[i], c[i]) < lo[i] - 1e-6 or min(a[i], b[i], c[i]) > hi[i] + 1e-6
            for i in range(3)
        ):
            continue
        samples = tuple(
            ((la, lb, lc), face.area / (n * n))
            for la, lb, lc in bary
            if region.matches(
                (
                    la * a[0] + lb * b[0] + lc * c[0],
                    la * a[1] + lb * b[1] + lc * c[1],
                    la * a[2] + lb * b[2] + lc * c[2],
                ),
                face.normal,
            )
        )
        if samples:
            covers.append(Cover(face, samples))
    return covers


def shape_functions(bary: Vec3) -> tuple[float, ...]:
    """Quadratic triangle shape functions (3 corners, then the edges ab, bc, ca) at ``bary``."""
    la, lb, lc = bary
    return (
        la * (2 * la - 1),
        lb * (2 * lb - 1),
        lc * (2 * lc - 1),
        4 * la * lb,
        4 * lb * lc,
        4 * lc * la,
    )


def covered_weights(
    covers: Sequence[Cover], face_weight: Callable[[TriFace], float] | None = None
) -> dict[int, float]:
    """Consistent nodal share of the covered area (sums to the covered area).

    ``face_weight`` scales each face's share (a bearing load is heaviest where the surface
    faces the load head-on).
    """
    weights: dict[int, float] = {}
    for cover in covers:
        scale = face_weight(cover.face) if face_weight else 1.0
        for bary, area in cover.samples:
            for node, shape in zip(cover.face.nodes, shape_functions(bary), strict=True):
                weights[node] = weights.get(node, 0.0) + shape * area * scale
    return weights


def covered_nodes(covers: Sequence[Cover], threshold: float = 0.2) -> set[int]:
    """Nodes close to the covered area (shape function above ``threshold`` at a sample)."""
    nodes: set[int] = set()
    for cover in covers:
        for bary, _ in cover.samples:
            for node, shape in zip(cover.face.nodes, shape_functions(bary), strict=True):
                if shape >= threshold:
                    nodes.add(node)
    return nodes


def nodes_in_region(mesh: Mesh, region: Region) -> list[int]:
    """The mesh nodes inside ``region`` (displacement limits look at these)."""
    return [n for n, p in mesh.nodes.items() if region.contains(p)]


def patch_edge_nodes(faces: Sequence[TriFace]) -> set[int]:
    """Nodes on the outline of a patch of faces (where loads and supports start and stop)."""
    count: dict[frozenset[int], int] = {}
    mids: dict[frozenset[int], int] = {}
    for f in faces:
        a, b, c, ab, bc, ca = f.nodes
        for pair, mid in (((a, b), ab), ((b, c), bc), ((c, a), ca)):
            key = frozenset(pair)
            count[key] = count.get(key, 0) + 1
            mids[key] = mid
    edge: set[int] = set()
    for key, n in count.items():
        if n == 1:
            edge |= key | {mids[key]}
    return edge
