"""Added and removed material between two versions of a part (exact mesh booleans).

``added = B − A`` and ``removed = A − B``, computed with manifold3d. Slivers left by float noise
on coincident faces are dropped: connected pieces smaller than :data:`MIN_PIECE_MM3` are ignored.
"""

from dataclasses import dataclass

import manifold3d
import numpy as np

from cadder.diff.stlio import Triangles

#: Pieces of added/removed material below this volume are noise, mm³.
MIN_PIECE_MM3 = 0.01


@dataclass(frozen=True)
class SolidDiff:
    """The material that differs between two meshes."""

    added: Triangles | None  #: in B only (None: nothing)
    removed: Triangles | None  #: in A only (None: nothing)
    added_volume: float  #: mm³
    removed_volume: float  #: mm³


def _manifold(tris: Triangles) -> manifold3d.Manifold:
    verts = tris.reshape(-1, 3).astype(np.float32)
    faces = np.arange(len(verts), dtype=np.uint32).reshape(-1, 3)
    mesh = manifold3d.Mesh(vert_properties=verts, tri_verts=faces)
    mesh.merge()  # weld the triangle soup into a closed surface
    solid = manifold3d.Manifold(mesh)
    if solid.status() != manifold3d.Error.NoError or solid.is_empty():
        raise ValueError(f"mesh is not a closed solid ({solid.status()})")
    return solid


def _pieces(solid: manifold3d.Manifold) -> tuple[Triangles | None, float]:
    """The significant pieces of ``solid`` as triangles, and their volume."""
    if solid.is_empty():
        return None, 0.0
    kept = [p for p in solid.decompose() if p.volume() >= MIN_PIECE_MM3]
    if not kept:
        return None, 0.0
    mesh = manifold3d.Manifold.compose(kept).to_mesh()
    verts = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    faces = np.asarray(mesh.tri_verts, dtype=np.int64)
    return verts[faces], float(sum(p.volume() for p in kept))


def solid_diff(a: Triangles, b: Triangles) -> SolidDiff:
    """Added and removed material going from mesh ``a`` to mesh ``b``.

    Raises ``ValueError`` if either mesh is not a closed solid.
    """
    manifold_a, manifold_b = _manifold(a), _manifold(b)
    added, added_volume = _pieces(manifold_b - manifold_a)
    removed, removed_volume = _pieces(manifold_a - manifold_b)
    return SolidDiff(added, removed, added_volume, removed_volume)
