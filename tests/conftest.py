import struct
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--update-reference",
        action="store_true",
        help="rewrite tests/reference_parts.json from the current geometry",
    )


@pytest.fixture
def update_reference(request) -> bool:
    return request.config.getoption("--update-reference")


def read_stl(path: Path) -> list[tuple[tuple[float, float, float], ...]]:
    """Triangles of an ASCII or binary STL file."""
    data = path.read_bytes()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        vertices = [
            tuple(float(v) for v in line.split()[1:4])
            for line in data.decode().splitlines()
            if line.strip().startswith("vertex")
        ]
    else:
        (count,) = struct.unpack_from("<I", data, 80)
        vertices = []
        for i in range(count):
            values = struct.unpack_from("<12f", data, 84 + 50 * i)
            vertices += [values[3:6], values[6:9], values[9:12]]
    return [tuple(vertices[i : i + 3]) for i in range(0, len(vertices), 3)]


def stl_stats(path: Path) -> dict:
    """Volume (signed, from the triangles) and bounding box of an STL file."""
    triangles = read_stl(path)
    volume = 0.0
    for (ax, ay, az), (bx, by, bz), (cx, cy, cz) in triangles:
        volume += (
            ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
        ) / 6
    points = [p for tri in triangles for p in tri]
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    return {"volume": volume, "bbox": [lo, hi]}


@pytest.fixture(scope="session")
def mesh_stats():
    """Function returning the volume and bounding box of an STL file."""
    return stl_stats
