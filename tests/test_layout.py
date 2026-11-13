"""The drilling layout matches the CAD: the holes are where the fasteners are."""

import itertools
import math
import xml.etree.ElementTree as ET

from plotter_cad import build, layout
from plotter_cad.assemblies import baseboard
from plotter_cad.params import FRAME
from solids import flatten, volume


def test_holes_are_on_the_board_and_apart():
    holes = layout.board_holes()
    bx, by, _ = FRAME.board_size
    assert all(h.d / 2 < h.x < bx - h.d / 2 and h.d / 2 < h.y < by - h.d / 2 for h in holes)
    for a, b in itertools.combinations(holes, 2):
        assert math.dist((a.x, a.y), (b.x, b.y)) > (a.d + b.d) / 2 + 3, "holes too close"


def test_fasteners_pass_through_their_holes():
    """Screws, bolts and studs sit in clear holes (the wood screws cut their own thread)."""
    board = baseboard.baseboard()
    fasteners = [*baseboard.runners()[1:], *baseboard.shafts_and_supports(), *baseboard.bed()]
    # the extrusions and the supports themselves are not fasteners but never touch the board
    # holes either; the only expected overlap is none at all
    overlap = sum(volume(board & item) for item in flatten(fasteners))
    assert overlap < 5, f"{overlap:g} mm³ of fasteners inside the plywood"


def test_layout_files_are_written(tmp_path):
    svg, table = build.export_layout(tmp_path)
    root = ET.parse(svg).getroot()
    assert root.get("width") == "700mm" and root.get("height") == "900mm"
    assert table.read_text().count("\n| ") >= len(layout.board_holes())
