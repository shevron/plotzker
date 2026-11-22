"""The plotter's part definitions: profiles, FEM specs and regions that actually touch the part."""

import json

import pytest
from cadder.part import (
    MaterialPart,
    part_to_dict,
)
from cadder.regions import Box
from cadder.testing import volume

from plotzker.materials import load_profile
from plotzker.parts import PARTS


def regions_of(part: MaterialPart) -> list[tuple[str, object]]:
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


PRINTED = {name: part for name, part in PARTS.items() if isinstance(part, MaterialPart)}


SPECIFIED = {name: part for name, part in PRINTED.items() if part.fem is not None}


@pytest.mark.parametrize("name", PRINTED)
def test_part_is_registered_and_serializes(name):
    part = PRINTED[name]
    assert PARTS[part.name] is part
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
    assert volume(SPECIFIED[name].analysis_geometry() & region.solid()) > 1e-6


def test_strength_only_parts_state_no_default_displacement_limit():
    data = part_to_dict(PARTS["pen_holder_body"])
    assert data["fem"]["default_displacement_limit_mm"] is None  # type: ignore[index]


def test_motor_loads_carry_pull_couple_weight_and_at_a_jam_the_stall_torque():
    from cadder.part import Force, Moment

    from plotzker.loads import MOTOR_LOADS, X_BELT_LOADS
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
