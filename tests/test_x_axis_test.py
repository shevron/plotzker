"""The guided X-axis test (``firmware/x_axis_test.py``) against a simulated Marlin board."""

from itertools import pairwise
from typing import Any

import pytest
import typer
import x_axis_test as xat


class FakeMarlin:
    """Replies like Marlin 2.1.2.5 to the commands the test sends."""

    def __init__(self, steps: float = 80.0, true_steps: float = 80.0) -> None:
        self.steps = steps
        self.true_steps = true_steps  # what the mechanics need for exact distances
        self.x = 200.0
        self.pressed = False
        self.relative = False
        self.limits = True
        self.sent: list[str] = []
        self.replies: list[str] = []

    def write(self, data: bytes) -> int:
        command = data.decode().strip()
        self.sent.append(command)
        word, _, rest = command.partition(" ")
        reply: list[str] = []
        if word == "M115":
            reply = ["FIRMWARE_NAME:Marlin 2.1.2.5 (test) MACHINE_TYPE:Creality3D"]
        elif word == "M503":
            reply = [f"echo:  M92 X{self.steps:.2f} Y80.00 Z400.00"]
        elif word == "M119":
            state = "TRIGGERED" if self.pressed or self.x <= 0 else "open"
            reply = ["Reporting endstop status", f"x_min: {state}", "y_min: TRIGGERED"]
        elif word == "M114":
            reply = [f"X:{self.x:.2f} Y:0.00 Z:0.00 Count X:0 Y:0 Z:0"]
        elif word == "M92":
            self.steps = float(rest.removeprefix("X"))
        elif word in ("G90", "G91"):
            self.relative = word == "G91"
        elif word == "M211":
            self.limits = rest == "S1"
        elif word == "G28":
            self.x, self.pressed = 0.0, False
            reply = ["echo:busy: processing"]
        elif word == "G1":
            target = float(rest.split()[0].removeprefix("X"))
            self.x = self.x + target if self.relative else target
            if self.limits:
                self.x = min(self.x, xat.X_MAX)
        self.replies = [*reply, "ok"]
        return len(data)

    def readline(self) -> bytes:
        return f"{self.replies.pop(0)}\n".encode() if self.replies else b""

    def reset_input_buffer(self) -> None:
        self.replies = []


class User:
    """Answers the prompts and does the hand work on the fake machine."""

    def __init__(self, machine: FakeMarlin, click_gap: float = 7.0) -> None:
        self.machine = machine
        self.click_gap = click_gap  # bracket face to carriage plate where the switch clicks

    def prompt(self, text: str, **kwargs: Any) -> Any:
        if "Hold the endstop" in text or "just hear" in text:
            self.machine.pressed = True
        elif "Release" in text or "back to mid-beam" in text:
            self.machine.pressed = False
        elif "where it clicked" in text:
            return self.click_gap
        elif text.startswith("Gap"):
            return self.click_gap + self.machine.x * self.machine.steps / self.machine.true_steps
        return kwargs.get("default", "")

    def confirm(self, text: str, **kwargs: Any) -> bool:
        return True


def run(
    monkeypatch: pytest.MonkeyPatch,
    machine: FakeMarlin,
    user: User,
    steps: list[xat.Step] | None = None,
) -> xat.Report:
    monkeypatch.setattr(typer, "prompt", user.prompt)
    monkeypatch.setattr(typer, "confirm", user.confirm)
    report = xat.Report()
    xat.run_tests(xat.Board(machine), report, cycles=3, steps=steps)
    return report


def test_full_run_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    machine = FakeMarlin()
    report = run(monkeypatch, machine, User(machine))
    assert not report.failed, report.lines
    assert "- PASS Soft limit: asked 430, stopped at 410" in report.lines
    assert "M500" not in machine.sent  # nothing to correct
    assert machine.sent[-2:] == ["M84 S120", "M18"]
    assert machine.limits and not machine.relative


def test_wrong_steps_are_corrected_and_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    machine = FakeMarlin(steps=80.0, true_steps=81.0)
    report = run(monkeypatch, machine, User(machine))
    assert not report.failed, report.lines
    assert machine.steps == pytest.approx(81.0, abs=0.01)
    assert "M500" in machine.sent


def test_repeatability_reports_the_spread_of_the_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    machine = FakeMarlin()
    user = User(machine)
    answer = user.prompt

    def drifting(text: str, **kwargs: Any) -> Any:
        value = answer(text, **kwargs)
        return value + 0.3 if "cycle 2/" in text else value

    user.prompt = drifting  # type: ignore[method-assign]
    report = run(monkeypatch, machine, user)
    assert report.failed
    assert "- FAIL Repeatability: spread 0.3 mm (27, 27.3, 27)" in report.lines


def test_stops_before_moving_when_the_endstop_reads_wrong(monkeypatch: pytest.MonkeyPatch) -> None:
    machine = FakeMarlin()
    machine.pressed = True  # stuck, or wired normally open
    with pytest.raises(xat.BoardError, match="released reads open"):
        run(monkeypatch, machine, User(machine))
    assert not any(c.startswith(("G1", "G28")) for c in machine.sent)


def test_short_trigger_margin_stops_before_moving(monkeypatch: pytest.MonkeyPatch) -> None:
    machine = FakeMarlin()
    with pytest.raises(xat.BoardError, match="Trigger margin"):
        run(monkeypatch, machine, User(machine, click_gap=4.0))  # only 1 mm before the wheel
    assert not any(c.startswith(("G1", "G28")) for c in machine.sent)


def test_travel_prompts_name_the_current_position_and_the_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    machine = FakeMarlin()
    user = User(machine)
    moves: list[tuple[str, float]] = []

    def confirm(text: str, **kwargs: Any) -> bool:
        if text.startswith("Next move"):
            moves.append((text.split("X = ")[1].split(".")[0], machine.x))
        return True

    user.confirm = confirm  # type: ignore[method-assign]
    run(monkeypatch, machine, user)
    # when each question is asked, the carriage is still at the previous target
    assert moves == [(str(t), float(p)) for p, t in pairwise((0, *xat.TRAVEL_STEPS))]


def test_select_steps() -> None:
    assert xat.select_steps(None, None) == list(xat.Step)
    assert xat.select_steps(xat.Step.REPEAT, None) == [xat.Step.REPEAT, xat.Step.TRAVEL]
    only = [xat.Step.TRAVEL, xat.Step.STEPS]
    assert xat.select_steps(None, only) == [xat.Step.STEPS, xat.Step.TRAVEL]
    with pytest.raises(typer.BadParameter):
        xat.select_steps(xat.Step.STEPS, only)


def test_only_one_step_still_warns_before_moving(monkeypatch: pytest.MonkeyPatch) -> None:
    machine = FakeMarlin()
    user = User(machine)
    asked: list[tuple[str, int]] = []
    answer = user.prompt

    def prompt(text: str, **kwargs: Any) -> Any:
        asked.append((text, sum(c.startswith(("G1", "G28")) for c in machine.sent)))
        return answer(text, **kwargs)

    user.prompt = prompt  # type: ignore[method-assign]
    report = run(monkeypatch, machine, user, [xat.Step.TRAVEL])
    assert not report.failed, report.lines
    assert "hand on the PSU switch" in asked[0][0] and asked[0][1] == 0
    assert "M119" not in machine.sent and "M17" not in machine.sent


class Broken(FakeMarlin):
    """A board that answers every command with one fixed line, or not at all."""

    def __init__(self, answer: str | None) -> None:
        super().__init__()
        self.answer = answer

    def write(self, data: bytes) -> int:
        self.replies = [self.answer] if self.answer else []
        return len(data)


def test_board_errors_are_raised() -> None:
    board = xat.Board(Broken("Error:Printer halted. kill() called!"))
    with pytest.raises(xat.BoardError, match="halted"):
        board.send("M115")


def test_silence_times_out() -> None:
    ticks = iter(range(1000))
    board = xat.Board(Broken(None), clock=lambda: float(next(ticks)))
    with pytest.raises(xat.BoardError, match="no answer"):
        board.send("M115", timeout=3)
