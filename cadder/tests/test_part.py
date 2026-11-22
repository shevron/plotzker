"""Parts: classes, materials, profiles, FEM specs and regions."""

import pytest
from demo.project import BLOCK, LIBRARY

from cadder.part import (
    FemSpec,
    LoadCase,
    MaterialPart,
    Support,
    effective_properties,
    part_to_dict,
)
from cadder.regions import Box, Cylinder, select_faces


def test_unknown_profile_and_material_are_reported():
    with pytest.raises(KeyError, match="Unknown print profile"):
        LIBRARY.profile("nope")
    with pytest.raises(KeyError, match="Unknown material"):
        LIBRARY.material("nope")


def test_effective_properties_apply_the_knockdowns():
    material, profile = LIBRARY.material("petg"), LIBRARY.profile()
    eff = effective_properties(material, profile)
    assert eff["e_in_plane_mpa"] == pytest.approx(
        material.e_in_plane_mpa * profile.stiffness_factor
    )
    assert eff["sustained_strength_build_mpa"] == pytest.approx(
        material.strength_build_mpa * profile.strength_factor * material.sustained_factor
    )


def test_load_cases_are_unique_and_a_support_is_required():
    case = LoadCase("a", "", (), "test")
    support = Support("s", Box((0, 0, 0), (1, 1, 1)), "")
    with pytest.raises(ValueError, match="unique"):
        FemSpec((case, case), (support,))
    with pytest.raises(ValueError, match="support"):
        FemSpec((case,), ())


def test_non_structural_part_cannot_have_a_fem_spec():
    spec = FemSpec((LoadCase("a", "", (), "test"),), (Support("s", Box((0,) * 3, (1,) * 3), ""),))
    with pytest.raises(ValueError, match="non-structural"):
        MaterialPart(
            name="p",
            description="",
            build=lambda: None,  # type: ignore[arg-type, return-value]
            material=LIBRARY.material("petg"),
            structural=False,
            fem=spec,
        )


def test_facing_filter_selects_by_outward_normal():
    points = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]
    up, down = [0, 1, 2, 3], [3, 2, 1, 0]
    region = Box((-1, -1, -1), (2, 2, 1), facing=(0, 0, 1))
    assert select_faces(region, points, [up, down]) == [0]


def test_cylinder_ring_excludes_the_hole():
    ring = Cylinder((0, 0, 0), (0, 0, 1), radius=4, inner_radius=2, half_length=1)
    assert ring.contains((3, 0, 0)) and not ring.contains((1, 0, 0))
    assert not ring.contains((3, 0, 2))


def test_moment_load_is_a_plain_dataclass_in_json():
    data = part_to_dict(BLOCK)
    kinds = {
        load["type"]
        for case in data["fem"]["load_cases"]  # type: ignore[index]
        for load in case["loads"]
    }
    assert kinds <= {"force", "moment", "acceleration"}
