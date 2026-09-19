"""Explicit, serializable experiment settings."""

import math
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class Window:
    start: str
    end: str

    def __post_init__(self):
        for value in (self.start, self.end):
            if datetime.strptime(value, "%H:%M").strftime("%H:%M") != value:
                raise ValueError("Window times must use HH:MM")
        if self.start >= self.end:
            raise ValueError("Window start must be before end")
        if not (
            ("09:30" <= self.start < self.end <= "11:30")
            or ("13:00" <= self.start < self.end <= "15:00")
        ):
            raise ValueError("Windows must stay inside one daytime trading session")

    @property
    def label(self):
        return f"{self.start}–{self.end}"


def parse_windows(value: str) -> tuple[Window, ...]:
    try:
        windows = tuple(Window(*part.strip().split("-")) for part in value.split(","))
    except (TypeError, ValueError) as exc:
        raise ValueError("Expected windows like 10:15-10:45,13:40-14:00") from exc
    for left, right in zip(
        sorted(windows, key=lambda w: w.start), sorted(windows, key=lambda w: w.start)[1:]
    ):
        if left.end >= right.start:
            raise ValueError("Windows in a set must not overlap or share inclusive endpoints")
    return windows


@dataclass(frozen=True)
class Config:
    primary: tuple[Window, ...] = (Window("10:15", "10:45"), Window("13:40", "14:00"))
    control: tuple[Window, ...] = (Window("11:00", "11:30"), Window("13:00", "13:20"))
    mode: str = "retrospective"
    base_threshold: float = 0.4
    event_threshold: float = 8.0
    lookback: int = 15
    context_days: int = 5

    def __post_init__(self):
        if self.mode not in {"retrospective", "asof_close"}:
            raise ValueError("mode must be retrospective or asof_close")
        if not self.primary or not self.control:
            raise ValueError("Both window sets must be nonempty")
        for windows in (self.primary, self.control):
            ordered = sorted(windows, key=lambda w: w.start)
            if any(a.end >= b.start for a, b in zip(ordered, ordered[1:])):
                raise ValueError("Windows within a set must not overlap")
        for value in (self.base_threshold, self.event_threshold):
            if not math.isfinite(value) or value < 0:
                raise ValueError("Thresholds must be finite and nonnegative")
        for value in (self.lookback, self.context_days):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("Lookback lengths must be positive integers")

    def to_dict(self):
        return asdict(self)
