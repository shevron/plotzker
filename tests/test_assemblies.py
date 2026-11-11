"""Every assembly builds and exports."""

import pytest
from pythonscad import export

from plotter_cad.assemblies import ASSEMBLIES
from plotter_cad.assemblies.skeleton import carriage_x_at, gantry_y_at
from plotter_cad.params import FRAME


@pytest.mark.parametrize("name", ASSEMBLIES)
def test_assembly_exports(name, tmp_path, mesh_stats):
    path = tmp_path / f"{name}.stl"
    export(ASSEMBLIES[name](), str(path))
    assert mesh_stats(path)["volume"] > 0


def test_travel_stays_on_the_board():
    for position in (0, 1):
        assert 0 < gantry_y_at(position) < FRAME.board_size[1]
        assert 0 < carriage_x_at(position) < FRAME.board_size[0]
