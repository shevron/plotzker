"""Every printable part renders, sits flat on the bed, and matches its reference geometry.

The reference (volume and bounding box per part) lives in ``reference_parts.json``.
After an intentional design change, review the new STLs and regenerate it with
``pytest --update-reference``.
"""

import dataclasses
import json
from pathlib import Path

import pytest
from pythonscad import export

from plotter_cad.params import Preload
from plotter_cad.parts import PRINTABLE_PARTS

REFERENCE = Path(__file__).with_name("reference_parts.json")


@pytest.fixture(scope="module")
def part_stats(tmp_path_factory, mesh_stats) -> dict[str, dict]:
    out = tmp_path_factory.mktemp("stl")
    stats = {}
    for name, build in PRINTABLE_PARTS.items():
        path = out / f"{name}.stl"
        export(build(), str(path))
        stats[name] = mesh_stats(path)
    return stats


@pytest.mark.parametrize("name", PRINTABLE_PARTS)
def test_part_is_solid_and_on_the_bed(part_stats, name):
    stats = part_stats[name]
    assert stats["volume"] > 0
    assert stats["bbox"][0][2] == pytest.approx(0, abs=1e-6), "print face must lie on z = 0"


def test_parts_match_reference(part_stats, update_reference):
    if update_reference:
        REFERENCE.write_text(json.dumps(part_stats, indent=2, sort_keys=True) + "\n")
        pytest.skip("reference updated")
    reference = json.loads(REFERENCE.read_text())
    assert sorted(reference) == sorted(part_stats), "part list changed: --update-reference"
    for name, ref in reference.items():
        got = part_stats[name]
        assert got["volume"] == pytest.approx(ref["volume"], abs=0.05), name
        for corner_got, corner_ref in zip(got["bbox"], ref["bbox"], strict=True):
            assert corner_got == pytest.approx(corner_ref, abs=1e-3), name


def test_carriage_slot_preload_fallback(monkeypatch, tmp_path, mesh_stats):
    """The D21 fallback (slotted bottom axles + push screws) still builds."""
    import plotter_cad.parts.x_carriage as module

    eccentric = tmp_path / "eccentric.stl"
    export(module.x_carriage(), str(eccentric))
    slotted_params = dataclasses.replace(module.CARRIAGE, preload=Preload.SLOT)
    monkeypatch.setattr(module, "CARRIAGE", slotted_params)
    slot = tmp_path / "slot.stl"
    export(module.x_carriage(), str(slot))
    assert 0 < mesh_stats(slot)["volume"] < mesh_stats(eccentric)["volume"]
