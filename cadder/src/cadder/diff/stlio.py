"""Read STL files (ASCII or binary) and measure the mesh. Units: mm."""

import hashlib
import re
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

#: Triangles as an (n, 3, 3) array: triangle, vertex, x/y/z.
Triangles = npt.NDArray[np.float64]

_VERTEX = re.compile(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)")
#: Coordinates are rounded to this many decimals before hashing (0.1 µm).
HASH_DECIMALS = 4


@dataclass(frozen=True)
class MeshStats:
    """Measurements of a closed triangle mesh."""

    triangles: int
    volume: float  #: mm³ (signed volume of the closed surface)
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    centroid: tuple[float, float, float]  #: volume centroid, mm
    hash: str  #: hash of the rounded triangle set, independent of facet order

    @property
    def size(self) -> tuple[float, float, float]:
        """Bounding-box extents (x, y, z)."""
        lo, hi = self.bbox_min, self.bbox_max
        return (hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])


def read_stl(path: Path) -> Triangles:
    """Read an ASCII or binary STL into an (n, 3, 3) array of triangles."""
    data = path.read_bytes()
    if data[:5].lower() == b"solid" and b"vertex" in data[:2000] + data[-2000:]:
        values = np.array(_VERTEX.findall(data), dtype=np.float64)
        return values.reshape(-1, 3, 3)
    if len(data) < 84:
        raise ValueError(f"{path}: not an STL file")
    (count,) = struct.unpack_from("<I", data, 80)
    if len(data) < 84 + 50 * count:
        raise ValueError(f"{path}: truncated binary STL")
    record = np.dtype([("normal", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")])
    return np.frombuffer(data, dtype=record, count=count, offset=84)["v"].astype(np.float64)


def _canonical(tris: Triangles) -> npt.NDArray[np.int64]:
    """Triangles as integer vertex triples: vertices rotated so the smallest comes first, and
    triangles sorted. Two meshes of the same surface give the same array whatever the facet
    order; a different triangulation of the same surface does not (a design change or a new
    tessellation both count as a change at this level)."""
    ints = np.round(tris * 10**HASH_DECIMALS).astype(np.int64)
    out = np.empty_like(ints)
    for i in range(len(ints)):
        tri = ints[i]
        keys = [tuple(v) for v in tri]
        first = keys.index(min(keys))
        out[i] = np.roll(tri, -first, axis=0)
    order = np.lexsort(out.reshape(len(out), 9).T[::-1])
    result: npt.NDArray[np.int64] = out[order]
    return result


def measure(tris: Triangles) -> MeshStats:
    """Volume, bounding box, centroid and hash of a mesh."""
    if len(tris) == 0:
        raise ValueError("empty mesh")
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    tet = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0  # signed tetrahedra from the origin
    volume = float(tet.sum())
    if abs(volume) > 1e-9:
        centers = (a + b + c) / 4.0
        centroid = tuple(float(x) for x in (centers * tet[:, None]).sum(axis=0) / volume)
    else:
        centroid = tuple(float(x) for x in tris.reshape(-1, 3).mean(axis=0))
    flat = tris.reshape(-1, 3)
    digest = hashlib.sha256(_canonical(tris).tobytes()).hexdigest()[:16]
    return MeshStats(
        triangles=len(tris),
        volume=abs(volume),
        bbox_min=(float(flat[:, 0].min()), float(flat[:, 1].min()), float(flat[:, 2].min())),
        bbox_max=(float(flat[:, 0].max()), float(flat[:, 1].max()), float(flat[:, 2].max())),
        centroid=(centroid[0], centroid[1], centroid[2]),
        hash=digest,
    )


def same_surface(a: Triangles, b: Triangles, tolerance: float) -> bool:
    """True if two meshes have the same triangle centroids within ``tolerance`` (mm).

    Absorbs float noise and facet reordering that change the exact hash. A different
    triangulation of the same shape is reported as changed; that is rare and harmless.
    """
    if len(a) != len(b):
        return False
    ca = np.round(a.mean(axis=1) / tolerance).astype(np.int64)
    cb = np.round(b.mean(axis=1) / tolerance).astype(np.int64)
    ca = ca[np.lexsort(ca.T[::-1])]
    cb = cb[np.lexsort(cb.T[::-1])]
    return bool(np.abs(ca - cb).max() <= 1)


def surface_area(tris: Triangles) -> float:
    """Total area of the triangles, mm²."""
    cross = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    return float(np.linalg.norm(cross, axis=1).sum() / 2.0)


def shape_hash(tris: Triangles) -> str:
    """Hash of the triangle set at its place in space, ignoring facet order and winding.

    Vectorized (assemblies hold hundreds of thousands of triangles): vertices are rounded,
    numbered in sorted order, and every triangle becomes its sorted vertex numbers.
    """
    ints = np.round(tris.reshape(-1, 3) * 10**HASH_DECIMALS).astype(np.int64)
    verts, inverse = np.unique(ints, axis=0, return_inverse=True)
    faces = np.sort(inverse.reshape(-1, 3), axis=1)
    faces = faces[np.lexsort(faces.T[::-1])]
    digest = hashlib.sha256(verts.tobytes() + faces.astype(np.int64).tobytes())
    return digest.hexdigest()[:16]
