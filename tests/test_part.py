"""Part definitions: profiles, materials, FEM specs and regions that actually touch the part."""

import json

import pytest

from plotter_cad.materials import load_material
from plotter_cad.part import (
    FemSpec,
    LoadCase,
    Part,
    Support,
    effective_properties,
    part_to_dict,
)
from plotter_cad.parts import PARTS, PRINTABLE_PARTS
from plotter_cad.print_profile import load_profile
from plotter_cad.regions import Box, Cylinder, select_faces
from solids import volume


def regions_of(part: Part) -> list[tuple[str, object]]:
    """Every region of a part's FEM spec, labeled for test ids."""
    spec = part.fem
    assert spec is not None
    loads = [
        (f"{case.name}/load", load.region)
        for case in spec.load_cases
        for load in case.loads
        if hasattr(load, "region")
    ]
    supports = [(f"support/{s.name}", s.region) for s in spec.supports]
    limits = [(f"limit/{lim.name}", lim.region) for lim in spec.displacement_limits]
    return [*loads, *supports, *limits]


def test_default_profile_is_the_agreed_print_setup():
    profile = load_profile()
    assert (profile.nozzle_mm, profile.layer_height_mm, profile.perimeters) == (0.6, 0.3, 3)
    assert (profile.infill_percent, profile.infill_pattern) == (20, "gyroid")
    assert profile.material == "petg"


def test_unknown_profile_and_material_are_reported():
    with pytest.raises(KeyError, match="Unknown print profile"):
        load_profile("nope")
    with pytest.raises(KeyError, match="Unknown material"):
        load_material("nope")


def test_effective_properties_apply_the_knockdowns():
    material, profile = load_material("petg"), load_profile()
    eff = effective_properties(material, profile)
    assert eff["e_in_plane_mpa"] == pytest.approx(
        material.e_in_plane_mpa * profile.stiffness_factor
    )
    assert eff["sustained_strength_build_mpa"] == pytest.approx(
        material.strength_build_mpa * profile.strength_factor * material.sustained_factor
    )


@pytest.mark.parametrize("name", PARTS)
def test_part_is_registered_and_serializes(name):
    part = PARTS[name]
    assert part.name in PRINTABLE_PARTS
    data = json.loads(json.dumps(part_to_dict(part)))
    assert data["fem_status"] == "specified"
    assert data["fem"]["load_cases"] and data["fem"]["supports"]


@pytest.mark.parametrize(
    ("name", "label", "region"),
    [
        pytest.param(name, label, region, id=f"{name}-{label}")
        for name, part in PARTS.items()
        for label, region in regions_of(part)
    ],
)
def test_region_touches_the_part(name, label, region):
    assert volume(PARTS[name].build() & region.solid()) > 1e-6


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
        Part("p", "", lambda: None, "print", (0, 0, 1), structural=False, fem=spec)  # type: ignore[arg-type, return-value]


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
    data = part_to_dict(next(iter(PARTS.values())))
    kinds = {
        load["type"]
        for case in data["fem"]["load_cases"]  # type: ignore[index]
        for load in case["loads"]
    }
    assert kinds <= {"force", "moment", "acceleration"}
