"""Tests for the design diff (``plotzker.diff``): STL reading, measuring, part comparison."""

import struct
import subprocess
import zlib
from pathlib import Path

import numpy as np
import pytest

from plotzker.diff.compare import Status, compare_snapshots, format_report
from plotzker.diff.snapshot import PartFile, Snapshot, take_snapshot
from plotzker.diff.stlio import measure, read_stl, same_surface

# Corner indices of a box's 12 triangles, outward facing.
_FACES = [
    (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
    (2, 3, 7), (2, 7, 6), (1, 2, 6), (1, 6, 5), (3, 0, 4), (3, 4, 7),
]  # fmt: skip


def box(x: float, y: float, z: float, at: float = 0.0) -> np.ndarray:
    """Triangles of a box with one corner at (at, 0, 0)."""
    c = np.array(
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]
    )
    c = c * np.array([x, y, z]) + np.array([at, 0, 0])
    return np.array([[c[i], c[j], c[k]] for i, j, k in _FACES], dtype=np.float64)


def write_ascii(path: Path, tris: np.ndarray) -> Path:
    lines = ["solid t"]
    for t in tris:
        lines.append("facet normal 0 0 0\nouter loop")
        lines += [f"vertex {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}" for v in t]
        lines.append("endloop\nendfacet")
    lines.append("endsolid t")
    path.write_text("\n".join(lines))
    return path


def write_binary(path: Path, tris: np.ndarray) -> Path:
    body = b"".join(
        struct.pack("<3f", 0, 0, 0) + struct.pack("<9f", *t.flatten()) + b"\0\0" for t in tris
    )
    path.write_bytes(b"\0" * 80 + struct.pack("<I", len(tris)) + body)
    return path


def snap(label: str, **parts: Path | None) -> Snapshot:
    return Snapshot(label, label, {n: PartFile(p) for n, p in parts.items()})


def test_measure_box(tmp_path: Path) -> None:
    stats = measure(read_stl(write_ascii(tmp_path / "a.stl", box(2, 3, 4))))
    assert stats.volume == pytest.approx(24)
    assert stats.size == pytest.approx((2, 3, 4))
    assert stats.centroid == pytest.approx((1, 1.5, 2))


def test_binary_and_ascii_agree(tmp_path: Path) -> None:
    t = box(2, 3, 4)
    a = measure(read_stl(write_ascii(tmp_path / "a.stl", t)))
    b = measure(read_stl(write_binary(tmp_path / "b.stl", t)))
    assert a.hash == b.hash


def test_hash_ignores_facet_order_and_start_vertex() -> None:
    t = box(2, 3, 4)
    shuffled = np.roll(t[::-1], 1, axis=1)
    assert measure(t).hash == measure(shuffled).hash
    assert measure(t).hash != measure(box(2, 3, 4.1)).hash


def test_same_surface_tolerates_noise() -> None:
    t = box(2, 3, 4)
    assert same_surface(t, t + 1e-5, 1e-3)
    assert not same_surface(t, box(2, 3, 4.1), 1e-3)


def test_compare_statuses(tmp_path: Path) -> None:
    f = {n: write_ascii(tmp_path / f"{n}.stl", t) for n, t in {
        "same": box(1, 1, 1), "taller": box(1, 1, 1), "taller2": box(1, 1, 2),
        "gone": box(1, 1, 1), "new": box(2, 2, 2), "moved": box(1, 1, 1, at=5),
    }.items()}  # fmt: skip
    a = snap("A", same=f["same"], taller=f["taller"], gone=f["gone"], moved=f["same"])
    b = snap("B", same=f["same"], taller=f["taller2"], new=f["new"], moved=f["moved"])
    got = {c.name: c for c in compare_snapshots(a, b)}
    assert {n: c.status for n, c in got.items()} == {
        "same": Status.UNCHANGED, "taller": Status.CHANGED, "gone": Status.REMOVED,
        "new": Status.ADDED, "moved": Status.CHANGED,
    }  # fmt: skip
    assert got["taller"].volume_delta == pytest.approx(1)
    assert got["taller"].size_delta == pytest.approx((0, 0, 1))
    assert got["moved"].shift == pytest.approx((5, 0, 0))
    text = format_report(a, b, list(got.values()), show_all=False)
    assert "same" not in text.split("\n\n", 1)[1]
    assert "taller" in text


def test_part_without_stl_is_an_error(tmp_path: Path) -> None:
    ok = write_ascii(tmp_path / "ok.stl", box(1, 1, 1))
    a = snap("A", p=ok)
    b = Snapshot("B", "B", {"p": PartFile(None, "Traceback\nValueError: boom")})
    (change,) = compare_snapshots(a, b)
    assert change.status is Status.ERROR
    assert "boom" in change.note


def test_snapshot_of_a_commit_leaves_no_worktree(tmp_path: Path) -> None:
    """A snapshot of a revision without the package reports a build error, not a crash."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run = ["git", "-C", str(repo)]
    subprocess.run([*run, "init", "-q"], check=True)
    (repo / "f.txt").write_text("x")
    subprocess.run([*run, "add", "."], check=True)
    subprocess.run(
        [*run, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"], check=True
    )
    result = take_snapshot(repo, "HEAD", tmp_path / "cache")
    assert result.parts == {}
    assert result.error
    worktrees = subprocess.run(
        [*run, "worktree", "list"], capture_output=True, text=True, check=True
    ).stdout
    assert len(worktrees.strip().splitlines()) == 1


def test_report_embeds_changed_meshes_only(tmp_path: Path) -> None:
    import base64
    import json
    import re

    from plotzker.diff.report import write_report

    same = write_ascii(tmp_path / "same.stl", box(1, 1, 1))
    tall = write_ascii(tmp_path / "tall.stl", box(1, 1, 2))
    a = snap("A", same=same, tall=same)
    b = snap("B", same=same, tall=tall)
    changes = compare_snapshots(a, b)
    path = write_report(a, b, changes, tmp_path / "out")
    html = path.read_text()
    assert "__DIFF_DATA__" not in html
    match = re.search(r"const DATA = (\{.*?\});\n", html)
    assert match
    data = json.loads(match.group(1))
    parts = {p["name"]: p for p in data["parts"]}
    assert parts["same"]["meshA"] is None
    raw = zlib.decompress(base64.b64decode(data["meshes"][parts["tall"]["meshB"]]))
    assert len(raw) == 12 * 9 * 4  # 12 triangles, float32
    assert parts["tall"]["volume_delta"] == pytest.approx(1)


def test_solid_diff_of_boxes() -> None:
    from plotzker.diff.boolean import solid_diff

    # A 1×1×1 box grows to 1×1×2 and loses nothing; a box shifted by 0.5 in x gains and loses
    # a 0.5×1×1 slab.
    grown = solid_diff(box(1, 1, 1), box(1, 1, 2))
    assert grown.added_volume == pytest.approx(1)
    assert grown.removed is None
    moved = solid_diff(box(1, 1, 1), box(1, 1, 1, at=0.5))
    assert moved.added_volume == pytest.approx(0.5)
    assert moved.removed_volume == pytest.approx(0.5)
    same = solid_diff(box(1, 1, 1), box(1, 1, 1))
    assert same.added is None
    assert same.removed is None


def test_solid_diff_ignores_slivers() -> None:
    from plotzker.diff.boolean import solid_diff

    result = solid_diff(box(10, 10, 10), box(10, 10, 10.00005))  # 0.005 mm³
    assert result.added is None
    assert result.removed is None


def _asm(tmp_path: Path, name: str, items: list[np.ndarray]) -> Path:
    path = tmp_path / f"{name}.npz"
    np.savez(path, **{f"i{k}": t.astype(np.float32) for k, t in enumerate(items)})
    return path


def test_assembly_instances_matched_by_geometry(tmp_path: Path) -> None:
    from plotzker.diff.assembly import InstanceStatus, compare_assembly

    a = _asm(
        tmp_path,
        "a",
        [box(1, 1, 1), box(2, 1, 1), box(3, 3, 3, at=50), box(4, 1, 1, at=-40)],
    )
    b = _asm(
        tmp_path,
        "b",
        [
            box(1, 1, 1),  # unchanged
            box(2, 1, 1, at=10),  # moved
            box(3, 3, 3.5, at=50),  # modified (taller)
            box(1, 1, 1, at=90),  # added; the 4 mm box is removed
        ],
    )
    change = compare_assembly("asm", a, b, {box(2, 1, 1)[:, :, 0].size * 0 + 2.0: "bar"})
    by = {i.status: i for i in change.instances}
    assert change.status == "changed"
    assert [i.status for i in change.instances].count(InstanceStatus.UNCHANGED) == 1
    assert by[InstanceStatus.MOVED].shift == pytest.approx((10, 0, 0))
    assert by[InstanceStatus.MOVED].label == "bar"  # labelled by the part with the same volume
    assert by[InstanceStatus.MODIFIED].after is not None
    assert by[InstanceStatus.ADDED].before is None
    assert by[InstanceStatus.REMOVED].after is None


def test_identical_assemblies_are_unchanged(tmp_path: Path) -> None:
    from plotzker.diff.assembly import compare_assembly

    items = [box(1, 1, 1), box(1, 1, 1, at=5), box(2, 2, 2)]
    change = compare_assembly("asm", _asm(tmp_path, "a", items), _asm(tmp_path, "b", items), {})
    assert change.status == "unchanged"


def _git_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """A repository with two commits: params.py and a part module changed, FEM verdict re-run."""
    repo = tmp_path / "gitrepo"
    (repo / "src/plotzker/parts").mkdir(parents=True)
    (repo / "fem").mkdir()
    run = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run([*run, "init", "-q"], check=True)

    def commit(msg: str) -> str:
        subprocess.run([*run, "add", "."], check=True)
        subprocess.run([*run, "commit", "-qm", msg], check=True)
        return subprocess.run(
            [*run, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()

    (repo / "src/plotzker/params.py").write_text("W = 1\n")
    (repo / "src/plotzker/parts/p.py").write_text("T = 2\n")
    (repo / "fem/verdicts.toml").write_text('[p]\nverdict = "PASS"\n[q]\nverdict = "PASS"\n')
    first = commit("first")
    (repo / "src/plotzker/params.py").write_text("W = 2\n")
    (repo / "src/plotzker/parts/p.py").write_text("T = 3\n")
    (repo / "fem/verdicts.toml").write_text('[p]\nverdict = "FAIL"\n[q]\nverdict = "PASS"\n')
    return repo, first, commit("second")


def test_source_info_between_commits(tmp_path: Path) -> None:
    from plotzker.diff.source import changed_files, commit_log, fem_hints, file_diff

    repo, first, second = _git_repo(tmp_path)
    assert commit_log(repo, first, second) == [f"{second[:7]} second"]
    files = {f.path: f for f in changed_files(repo, first, second)}
    assert set(files) == {"src/plotzker/params.py", "src/plotzker/parts/p.py"}
    diff = file_diff(repo, first, second, "src/plotzker/parts/p.py")
    assert "-T = 2" in diff
    assert "+T = 3" in diff
    assert "diff --git" not in diff
    hints = fem_hints(repo, first, second, ["p", "q", "none"])
    assert hints["p"] == "re-checked PASS → FAIL"
    assert "not re-run" in hints["q"]
    assert "none" not in hints


def test_source_info_against_worktree(tmp_path: Path) -> None:
    from plotzker.diff.snapshot import WORKTREE
    from plotzker.diff.source import changed_files

    repo, _, second = _git_repo(tmp_path)
    (repo / "src/plotzker/params.py").write_text("W = 3\n")
    files = changed_files(repo, second, WORKTREE)
    assert [f.path for f in files] == ["src/plotzker/params.py"]
    assert changed_files(repo, WORKTREE, WORKTREE) == []
