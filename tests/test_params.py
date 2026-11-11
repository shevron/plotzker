"""The design rules hold for the current parameters, and a broken rule is reported."""

import dataclasses

import pytest

from plotter_cad import params


def test_design_checks_pass():
    failures = [message for passed, message in params.design_checks() if not passed]
    assert failures == []


def test_check_design_raises_on_violation(monkeypatch):
    impossible = dataclasses.replace(params.REQ, y_travel=params.Y_AXIS.travel_avail + 1)
    monkeypatch.setattr(params, "REQ", impossible)
    with pytest.raises(params.DesignError, match="Y travel too short"):
        params.check_design()
