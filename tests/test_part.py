"""Part definitions: profiles, materials, FEM specs and regions that actually touch the part."""

import json

import pytest

from plotzker.materials import load_material
from plotzker.part import (
    FemSpec,
    LoadCase,
    Part,
    Support,
    effective_properties,
    part_to_dict,
)
from plotzker.parts import PARTS, PRINTABLE_PARTS
from plotzker.print_profile import load_profile
from plotzker.regions import Box, Cylinder, select_faces
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


SPECIFIED = {name: part for name, part in PARTS.items() if part.fem is not None}


@pytest.mark.parametrize("name", PARTS)
def test_part_is_registered_and_serializes(name):
    part = PARTS[name]
    assert part.name in PRINTABLE_PARTS
    data = json.loads(json.dumps(part_to_dict(part)))
    if part.mirror_of:
        assert part.mirror_of in SPECIFIED
        assert data["fem_status"] == f"mirror of {part.mirror_of}"
    elif not part.structural:
        assert data["fem_status"] == "not structural"
    else:
        assert data["fem_status"] == "specified"
        assert data["fem"]["load_cases"] and data["fem"]["supports"]


@pytest.mark.parametrize(
    ("name", "label", "region"),
    [
        pytest.param(name, label, region, id=f"{name}-{label}")
        for name, part in SPECIFIED.items()
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
    data = part_to_dict(next(iter(SPECIFIED.values())))
    kinds = {
        load["type"]
        for case in data["fem"]["load_cases"]  # type: ignore[index]
        for load in case["loads"]
    }
    assert kinds <= {"force", "moment", "acceleration"}


def test_strength_only_parts_state_no_default_displacement_limit():
    data = part_to_dict(PARTS["pen_holder_body"])
    assert data["fem"]["default_displacement_limit_mm"] is None  # type: ignore[index]


def test_motor_loads_carry_pull_couple_weight_and_at_a_jam_the_stall_torque():
    from plotzker.loads import MOTOR_LOADS, X_BELT_LOADS
    from plotzker.part import Force, Moment
    from plotzker.parts.motor_fem import motor_loads

    region = Box((0, 0, 0), (1, 1, 1))
    args = (region, X_BELT_LOADS)
    rest = ((0.0, -20.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0))
    preload = motor_loads(*args, False, *rest)
    jam = motor_loads(*args, True, *rest)
    assert [type(load) for load in preload] == [Force, Moment, Force]
    assert len(jam) == 4
    pull = preload[0].vector[0]
    assert pull == pytest.approx(2 * X_BELT_LOADS.preload_n)
    assert jam[0].vector[0] == pytest.approx(2 * X_BELT_LOADS.peak_n)
    assert preload[1].vector[2] == pytest.approx(-20.0 * -pull)  # lever 20 mm × pull, about z
    assert jam[3].vector[1] == pytest.approx(-MOTOR_LOADS.stall_torque)
    forces_only = motor_loads(*args, True, *rest, couples=False)
    assert [type(load) for load in forces_only] == [Force, Force]
