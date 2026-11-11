"""The parameter set satisfies every design rule and keeps the README §5 key numbers."""

import dataclasses

import pytest

from plotter_cad import params
from plotter_cad.params import BEAM, CARRIAGE, DRIVE, X_BELT, Y_AXIS


def test_design_checks_pass():
    failures = [message for passed, message in params.design_checks() if not passed]
    assert failures == []


def test_check_design_raises_on_violation(monkeypatch):
    monkeypatch.setattr(params, "REQ", dataclasses.replace(params.REQ, y_travel=600))
    with pytest.raises(params.DesignError, match="Y travel too short"):
        params.check_design()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (lambda: Y_AXIS.scs_top_z, 33.5),
        (lambda: BEAM.bottom_z, 58),
        (lambda: BEAM.top_z, 98),
        (lambda: Y_AXIS.shaft_spacing, 520),
        (lambda: CARRIAGE.travel_avail, 426),
        (lambda: Y_AXIS.travel_avail, 543),
        (lambda: DRIVE.steps_per_mm, 80),
        (lambda: CARRIAGE.wheel_pitch_x, 64),
        (lambda: CARRIAGE.bottom_z, 33.15),
        (lambda: CARRIAGE.top_z, 122.85),
        (lambda: CARRIAGE.plate_front_y, -21.3),
        (lambda: X_BELT.y, 23),
    ],
)
def test_key_numbers_match_readme(value, expected):
    """README §5 quotes these; update the README if one of them changes."""
    assert value() == pytest.approx(expected)


def test_belt_line_heights():
    assert Y_AXIS.pulley_axis_z == pytest.approx(27.8, abs=0.05)
    assert X_BELT.pulley_axis_z == pytest.approx(94.8, abs=0.05)


def test_report_mentions_every_topic():
    text = params.report()
    for topic in ("Stack-up", "Beam bottom", "Travel available", "Steps/mm", "Carriage", "X belt"):
        assert topic in text
