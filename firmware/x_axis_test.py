"""Guided X-axis test and steps/mm calibration over the board's USB serial port.

Runs the tests of docs/x-axis-bringup.md §5 in order, pausing wherever you have to look, press
or measure something, and writes a report to ``build/``. Nothing moves without a prompt first.
Distances are measured with calipers as the gap between the left gantry bracket and the carriage
plate (``WHERE_TO_MEASURE``; picture: docs/x-axis-measure.svg).

The software can't be relied on to stop a move: keep a hand on the PSU switch.

Usage: ``uv run firmware/x_axis_test.py`` (close any serial monitor first). To repeat only part of
it, ``--from travel`` runs from that step on and ``--only steps --only repeat`` just those.
"""

import contextlib
import re
import time
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Protocol

import serial
import typer
from serial.tools import list_ports

BAUDRATE = 115200
#: USB vendor ID of the board's CH340 serial chip
CH340_VID = 0x1A86
#: X steps/mm by design: GT2, 20 teeth, 1/16 microstepping
DESIGN_STEPS = 80.0
#: Planned X travel (``X_BED_SIZE`` in apply_config.py)
X_MAX = 410
#: Steps along the travel test, mm
TRAVEL_STEPS = (100, 200, 300, 350, 380, 400, X_MAX)
#: The steps/mm test measures the gap at these two positions (both within 150 mm calipers)
CAL_FROM, CAL_TO = 20.0, 120.0
CAL_DISTANCE = CAL_TO - CAL_FROM
#: The error above which a correction is offered, mm
CAL_TOLERANCE = 0.3
#: A measurement further than this from the target is taken as a typing or setup mistake
CAL_LIMIT = 10.0
#: How far the V-wheels stick out beyond the carriage plate's side (``params.Carriage``), mm:
#: the wheel reaches the bracket first, so the travel left is the plate gap minus this
WHEEL_OVERHANG = 3.0
MIN_MARGIN = 3.0
MAX_SPREAD = 0.1
WHERE_TO_MEASURE = """
  THE GAP: seen from the front, at the LEFT end of the beam, with the calipers' inside jaws,
  held level and parallel to the beam, at about the middle of the beam's height.

     left bracket                carriage's front plate
     ##########|                 |----------------
     ##########| <---- GAP ----> | (the flat printed
     ##########|                 |  side edge, 8 mm thick)
     ##########|              (  |----------------
                |             ^ V-wheel behind the plate: NOT this

  FROM: the flat inner face of the bracket's upright plate (the one the beam end bolts to).
  TO:   the left side edge of the carriage's front plate, not the V-wheel behind it.
  Use the same two spots every time, and don't push the carriage with the jaws.
  Picture: docs/x-axis-measure.svg
"""
REPORT_DIR = Path(__file__).resolve().parents[1] / "build"


class Step(StrEnum):
    """The parts of the test, in the order they run (the connection check always runs)."""

    ENDSTOP_SPEC = "endstop"
    MARGIN = "margin"
    DIRECTION = "direction"
    HOMING = "homing"
    STEPS = "steps"
    REPEAT = "repeat"
    TRAVEL = "travel"


#: Steps that move the carriage with the motor
POWERED = (Step.DIRECTION, Step.HOMING, Step.STEPS, Step.REPEAT, Step.TRAVEL)


class BoardError(Exception):
    """The board reported an error or stopped answering."""


class Port(Protocol):
    """The part of ``serial.Serial`` that ``Board`` uses."""

    def write(self, data: bytes, /) -> int | None: ...
    def readline(self) -> bytes: ...
    def reset_input_buffer(self) -> None: ...


class Board:
    """Marlin on a serial port: send a command, collect the reply up to its ``ok``."""

    def __init__(self, port: Port, clock: Callable[[], float] = time.monotonic) -> None:
        self.port = port
        self.clock = clock

    def send(self, command: str, timeout: float = 10.0) -> list[str]:
        """Send ``command``; return the reply lines before ``ok``.

        ``timeout`` is the longest silence: Marlin's "busy" lines restart it, so long moves
        don't time out.
        """
        self.port.write(f"{command}\n".encode())
        lines: list[str] = []
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            line = self.port.readline().decode(errors="replace").strip()
            if not line:
                continue
            deadline = self.clock() + timeout
            if line.startswith("Error:") or line.startswith("!!"):
                raise BoardError(f"{command}: {line}")
            if line == "ok" or line.startswith("ok "):
                return lines
            if "busy:" not in line:
                lines.append(line)
        raise BoardError(f"{command}: no answer")

    def move(self, command: str) -> None:
        """Send a motion command and wait until the motion has finished."""
        self.send(command, timeout=30)
        self.send("M400", timeout=60)

    def x_triggered(self) -> bool:
        """The state of the X endstop."""
        for line in self.send("M119"):
            if line.startswith("x_min:"):
                return "TRIGGERED" in line
        raise BoardError("M119: no x_min in the reply")

    def x_position(self) -> float:
        for line in self.send("M114"):
            if match := re.match(r"X:(-?[\d.]+)", line):
                return float(match[1])
        raise BoardError("M114: no X position in the reply")

    def x_steps(self) -> float:
        """Current X steps/mm."""
        for line in self.send("M503"):
            if match := re.search(r"\bM92 X([\d.]+)", line):
                return float(match[1])
        raise BoardError("M503: no M92 line in the reply")


class Report:
    """The results, echoed as they come and saved as Markdown."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed = False

    def add(self, name: str, passed: bool | None, detail: str = "") -> None:
        """``passed`` None: a value recorded, not judged."""
        mark = {True: "PASS", False: "FAIL", None: "NOTE"}[passed]
        color = {True: typer.colors.GREEN, False: typer.colors.RED, None: None}[passed]
        self.failed |= passed is False
        text = f"{name}: {detail}" if detail else name
        typer.secho(f"  {mark}  {text}", fg=color)
        self.lines.append(f"- {mark} {text}")

    def save(self, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        path = folder / f"x-axis-test-{now:%Y%m%d-%H%M%S}.md"
        path.write_text(f"# X-axis test, {now:%Y-%m-%d %H:%M}\n\n" + "\n".join(self.lines) + "\n")
        return path


def step(title: str) -> None:
    typer.secho(f"\n== {title}", bold=True)


def pause(message: str) -> None:
    typer.prompt(f"{message} [Enter]", default="", show_default=False, prompt_suffix=" ")


def ask_gap(position: str) -> float:
    """The gap between the bracket and the carriage plate, as read from the calipers."""
    text = f"Gap from the bracket face to the carriage plate's edge {position}, mm"
    return float(typer.prompt(text, type=float))


def require(report: Report, name: str, passed: bool, detail: str = "") -> None:
    """Record a check that the later, moving tests depend on; stop if it fails."""
    report.add(name, passed, detail)
    if not passed:
        raise BoardError(f"stopping: '{name}' failed (docs/x-axis-bringup.md §6)")


def check_firmware(board: Board, report: Report) -> None:
    step("Connection")
    info = " ".join(board.send("M115"))
    match = re.search(r"FIRMWARE_NAME:(Marlin \S+)", info)
    require(report, "Firmware", match is not None, match[1] if match else info or "no M115 reply")
    report.add("X steps/mm", None, f"{board.x_steps():g}")


def check_endstop(board: Board, report: Report) -> None:
    step("Endstop switch")
    pause("Move the carriage to mid-beam and don't touch the endstop.")
    require(report, "Endstop released reads open", not board.x_triggered())
    pause("Hold the endstop lever pressed.")
    require(report, "Endstop pressed reads TRIGGERED", board.x_triggered())
    pause("Release the lever.")


def check_margin(board: Board, report: Report) -> None:
    step("Trigger margin (motor off)")
    board.send("M18")
    typer.echo(WHERE_TO_MEASURE)
    pause("Push the carriage slowly left by hand until you just hear the switch click.")
    require(report, "Carriage trips the endstop", board.x_triggered())
    gap = ask_gap("where it clicked")
    margin = gap - WHEEL_OVERHANG
    detail = f"gap {gap:g} mm, so {margin:g} mm left before the wheel touches (need {MIN_MARGIN:g})"
    require(report, "Trigger margin", margin >= MIN_MARGIN, detail)
    pause("Push the carriage back to mid-beam.")


def check_direction(board: Board, report: Report) -> None:
    step("Motor and direction")
    pause("24 V on, carriage mid-beam, hand on the PSU switch.")
    board.send("M17")
    require(report, "Motor holds", typer.confirm("Is the carriage hard to move by hand?"))
    pause("The carriage will move 10 mm to the right (toward the motor).")
    board.send("M211 S0")  # soft limits off: nothing is homed yet
    try:
        board.send("G91")
        board.move("G1 X10 F1200")
    finally:
        board.send("G90")
        board.send("M211 S1")
    require(report, "Direction", typer.confirm("Did it move about 10 mm to the right?"))


def home(board: Board) -> None:
    board.send("G28 X", timeout=60)
    board.send("M400", timeout=60)


def check_homing(board: Board, report: Report) -> None:
    step("Homing")
    pause("The carriage will move left until it hits the endstop.")
    home(board)
    x = board.x_position()
    require(report, "Homing", abs(x) < 0.01, f"X = {x:g} after G28 X")


def measure_distance(board: Board) -> float:
    """The real distance of a ``CAL_DISTANCE`` move: the difference of two gap readings."""
    home(board)
    board.move(f"G1 X{CAL_FROM:g} F3000")
    first = ask_gap(f"now (X = {CAL_FROM:g})")
    board.move(f"G1 X{CAL_TO:g} F3000")
    second = ask_gap(f"now (X = {CAL_TO:g})")
    return round(second - first, 3)


def calibrate(board: Board, report: Report) -> None:
    step("Steps/mm")
    typer.echo(WHERE_TO_MEASURE)
    for attempt in range(1, 3):
        pause(f"The carriage will home, then move right to X = {CAL_FROM:g}.")
        measured = measure_distance(board)
        error = measured - CAL_DISTANCE
        if abs(error) > CAL_LIMIT:
            report.add("Distance", False, f"{measured:g} mm: too far off to correct, check setup")
            return
        report.add("Distance", None, f"{measured:g} mm for {CAL_DISTANCE:g} mm commanded")
        if abs(error) <= CAL_TOLERANCE or attempt == 2:
            break
        old = board.x_steps()
        new = old * CAL_DISTANCE / measured
        question = f"Change X steps/mm from {old:g} to {new:.2f} (design: {DESIGN_STEPS:g}) and save?"
        if not typer.confirm(question):
            break
        board.send(f"M92 X{new:.2f}")
        board.send("M500")
        report.add("X steps/mm saved", None, f"{old:g} -> {new:.2f}")
    report.add("Distance within 1 mm", abs(error) <= 1.0, f"error {error:+.2f} mm")


def check_repeatability(board: Board, report: Report, cycles: int) -> None:
    step(f"Homing repeatability ({cycles} cycles)")
    typer.echo(f"After each homing the carriage stops at X = {CAL_FROM:g}: measure the same gap.")
    pause(f"The carriage will go to X = 200, home and return to X = {CAL_FROM:g}, every cycle.")
    gaps = []
    for cycle in range(1, cycles + 1):
        board.move("G1 X200 F3000")
        home(board)
        board.move(f"G1 X{CAL_FROM:g} F3000")
        gaps.append(ask_gap(f"(cycle {cycle}/{cycles})"))
    spread = round(max(gaps) - min(gaps), 3)
    readings = ", ".join(f"{g:g}" for g in gaps)
    report.add("Repeatability", spread <= MAX_SPREAD, f"spread {spread:g} mm ({readings})")


def check_travel(board: Board, report: Report) -> None:
    step("Travel and soft limit")
    pause("The carriage will first home (move left to X = 0).")
    home(board)
    reached = 0
    for target in TRAVEL_STEPS:
        typer.echo(f"The carriage is now at X = {reached}.")
        if not typer.confirm(f"Next move: right, to X = {target}. Is there room? Move now?"):
            break
        board.move(f"G1 X{target} F3000")
        reached = target
    report.add("Travel", reached == X_MAX, f"reached X = {reached} of {X_MAX}")
    if reached == X_MAX:
        pause(f"Soft limit: asking for X = {X_MAX + 20}; the carriage should not move.")
        board.move(f"G1 X{X_MAX + 20} F600")  # the soft limit must clamp this
        x = board.x_position()
        report.add("Soft limit", abs(x - X_MAX) < 0.01, f"asked {X_MAX + 20}, stopped at {x:g}")
    pause("The carriage will return home (X = 0).")
    home(board)


def select_steps(start: Step | None, only: list[Step] | None) -> list[Step]:
    """The steps to run, in test order."""
    if start is not None and only:
        raise typer.BadParameter("use --from or --only, not both")
    every = list(Step)
    if only:
        return [s for s in every if s in only]
    return every[every.index(start) :] if start else every


def run_tests(board: Board, report: Report, cycles: int, steps: list[Step] | None = None) -> None:
    steps = steps or list(Step)
    checks: dict[Step, Callable[[], None]] = {
        Step.ENDSTOP_SPEC: lambda: check_endstop(board, report),
        Step.MARGIN: lambda: check_margin(board, report),
        Step.DIRECTION: lambda: check_direction(board, report),
        Step.HOMING: lambda: check_homing(board, report),
        Step.STEPS: lambda: calibrate(board, report),
        Step.REPEAT: lambda: check_repeatability(board, report, cycles),
        Step.TRAVEL: lambda: check_travel(board, report),
    }
    check_firmware(board, report)
    if len(steps) < len(Step):
        report.add("Only these steps", None, ", ".join(steps))
    # No idle release during the pauses: a free carriage would lose its position
    board.send("M84 S0")
    try:
        # The direction step asks for this itself
        if Step.DIRECTION not in steps and any(s in POWERED for s in steps):
            pause("24 V on, carriage free to move, hand on the PSU switch.")
        for name in steps:
            checks[name]()
    finally:
        # Best effort: after an error the board may not answer
        with contextlib.suppress(BoardError, serial.SerialException):
            board.send("M84 S120")
            board.send("M18")


def find_port() -> str:
    ports = [p.device for p in list_ports.comports() if p.vid == CH340_VID]
    if len(ports) != 1:
        found = ", ".join(ports) or "none"
        raise BoardError(f"need exactly one CH340 port, found {found}; use --port")
    return str(ports[0])


def wait_for_board(board: Board) -> None:
    """Opening the port may reset the board: ask until it answers."""
    for _ in range(5):
        time.sleep(2)
        board.port.reset_input_buffer()
        try:
            board.send("M115", timeout=3)
            return
        except BoardError:
            continue
    raise BoardError("the board doesn't answer: USB cable, port, or a monitor still open?")


def main(
    port: Annotated[str | None, typer.Option(help="Serial port; found if omitted.")] = None,
    cycles: Annotated[int, typer.Option(min=1, help="Homing repeatability cycles.")] = 10,
    start: Annotated[Step | None, typer.Option("--from", help="Skip the steps before this one.")] = None,
    only: Annotated[list[Step] | None, typer.Option(help="Run just this step; repeat for several.")] = None,
) -> None:
    """Test and calibrate the X axis, step by step."""
    steps = select_steps(start, only)
    report = Report()
    try:
        name = port or find_port()
        typer.echo(f"Port {name}. Ctrl-C quits; to stop a move, cut the power.")
        with serial.Serial(name, BAUDRATE, timeout=1) as link:
            board = Board(link)
            wait_for_board(board)
            run_tests(board, report, cycles, steps)
    except (BoardError, serial.SerialException) as error:
        typer.secho(f"\n{error}", fg=typer.colors.RED, err=True)
        report.failed = True
    except KeyboardInterrupt, typer.Abort:
        typer.secho("\nAborted. Cut the power if anything is still moving.", fg=typer.colors.RED)
        report.failed = True
    if report.lines:
        typer.echo(f"\nReport: {report.save(REPORT_DIR)}")
    raise typer.Exit(1 if report.failed else 0)


if __name__ == "__main__":
    typer.run(main)
